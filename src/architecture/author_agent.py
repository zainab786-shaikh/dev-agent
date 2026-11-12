"""Agent that makes the solution-level decisions and designs the architecture per software requirement."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..models import DecisionRecord, ReviewResult
from ..review_loop import ArtifactAuthor
from ..srs.models import SoftwareRequirementsDocument
from ..sysrs.models import SystemRequirementsDocument
from .models import ArchitectureAnalysis, ArchitectureContext, ArchitectureElementSet, ArchitectureLandscape
from .sources import architecture_digest


class ArchitectureAuthorAgent(BaseAgent, ArtifactAuthor[ArchitectureContext, ArchitectureElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "ArchitectureAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a software and solution architect. You decide how requirements will be implemented: "
            "architecture style, cloud services, security model, scalability and deployment, and you "
            "record each significant choice with the options evaluated and the rationale. Respond only "
            "with JSON matching the given schema."
        )

    def analyze(
        self,
        srs: SoftwareRequirementsDocument,
        sysrs: SystemRequirementsDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[ArchitectureAnalysis],
    ) -> ArchitectureAnalysis:
        prompt = (
            f"Software requirements and systems:\n{architecture_digest(srs, sysrs)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous proposal:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed architecture (keep it unless the requirements or feedback require a "
            f"change):\n{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the architecture challenge in two or three sentences.\n"
            "2. Ask clarifying questions about constraints you cannot infer, e.g. mandated cloud, budget, "
            "team skills, compliance, expected user volume (max 5; empty if none).\n"
            "3. Propose the solution-level decisions that are still open, covering: architecture style "
            "(monolith, modular monolith, microservices), cloud platform and services, security model, "
            "scalability strategy, data storage and messaging.\n"
            f"{DECISION_INSTRUCTIONS}\n"
            "Do not list components yet; they are designed after the decisions are made."
        )
        return self._invoke(ArchitectureAnalysis, prompt)

    def design_landscape(
        self,
        srs: SoftwareRequirementsDocument,
        sysrs: SystemRequirementsDocument,
        clarifications: list[str],
        decisions: list[DecisionRecord],
        baseline: Optional[ArchitectureAnalysis],
        problems: Optional[list[str]] = None,
    ) -> ArchitectureLandscape:
        current = baseline.model_dump_json(include={"components", "interactions"}) if baseline else "none"
        prompt = (
            f"Software requirements and systems:\n{architecture_digest(srs, sysrs)}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(decisions)}\n\n"
            f"User clarifications:\n{lines(clarifications)}\n\n"
            f"Current components and interactions (keep their ids and names unless the decisions or "
            f"requirements require a change):\n{current}\n\n"
            + (f"Problems found in the previous attempt (fix them):\n{lines(problems)}\n\n" if problems else "")
            + "Design the architecture components (id COMP-n) with responsibility and technology consistent "
            "with the decisions, and how they interact (id CI-n, source and target component ids, "
            "mechanism). Every component has a tier: 'client' for the web client (the confirmed framework), "
            "'api' for the API server (layers such as controllers, services and repositories use the "
            "confirmed ORM), 'data' for the database (the confirmed engine), or 'external' for systems "
            "outside the product. There must be at least one client, one api and one data component; the "
            "client talks only to the api tier, and only the api tier talks to the data tier."
        )
        return self._invoke(ArchitectureLandscape, prompt)

    def create(self, context: ArchitectureContext) -> ArchitectureElementSet:
        return self._invoke(ArchitectureElementSet, self._base_prompt(context) + self._instructions())

    def update(self, context: ArchitectureContext, existing: ArchitectureElementSet) -> ArchitectureElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing architecture design for this requirement:\n{existing.model_dump_json()}\n\n"
            + "Update it so it reflects the requirement, decisions and components above, and any user "
            "feedback in the clarifications. Keep everything still valid (including titles and wording), "
            "add what is new, change what conflicts, remove what is obsolete.\n"
            + self._instructions()
        )
        return self._invoke(ArchitectureElementSet, prompt)

    def revise(
        self, context: ArchitectureContext, artifact: ArchitectureElementSet, review: ReviewResult
    ) -> ArchitectureElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current architecture design:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions()
        )
        return self._invoke(ArchitectureElementSet, prompt)

    def _base_prompt(self, context: ArchitectureContext) -> str:
        landscape = context.analysis.model_dump_json(include={"components", "interactions"})
        return (
            f"Software requirement:\n{context.requirement.model_dump_json()}\n\n"
            f"Confirmed components and interactions:\n{landscape}\n\n"
            f"Confirmed solution-level decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _instructions() -> str:
        return (
            "Design the architecture for THIS software requirement only, consistent with the confirmed "
            "decisions. Output design elements (high-level design, how components realize it), "
            "architecture decision records, security controls and deployment elements, with local ids "
            "HLD-n, ADR-n, SEC-n, DEP-n (renumbered later). Use only the confirmed component ids. For "
            "every ADR: state the context from the requirement, evaluate 2 to 4 options with pros and "
            "cons, choose the best one and say why it beats the others, and list consequences. Example: "
            "requirement 'Support 10 million users' gives the decision 'Scale the API tier horizontally behind a "
            "load balancer with a managed queue and a partitioned data store' with scaling numbers. Add security controls (authentication, "
            "authorization, encryption at rest and in transit, secrets, audit logging) where the "
            "requirement implies them, and deployment elements with scaling and resiliency where it "
            "affects deployment. Leave a list empty when the requirement does not need it."
        )
