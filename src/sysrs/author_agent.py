"""Agent that proposes the system landscape and derives system requirements per product requirement."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..models import DecisionRecord, ReviewResult
from ..prd.digest import prd_digest
from ..prd.models import ProductRequirementsDocument
from ..review_loop import ArtifactAuthor
from .models import SysrsContext, SystemRequirementSet, SystemRequirementsAnalysis


class SysrsAuthorAgent(BaseAgent, ArtifactAuthor[SysrsContext, SystemRequirementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "SysrsAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a solution architect and system analyst. You translate product requirements into "
            "system-level requirements: which systems participate, how they interact and what external "
            "integrations are needed. Respond only with JSON matching the given schema."
        )

    def analyze(
        self,
        prd: ProductRequirementsDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[SystemRequirementsAnalysis],
    ) -> SystemRequirementsAnalysis:
        prompt = (
            f"PRD:\n{prd_digest(prd)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous analysis:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed analysis (keep its systems, ids and interactions unless the PRD or "
            f"feedback require a change):\n{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the system capabilities the PRD needs.\n"
            "2. List the participating systems (id SYS-n, internal or external) with their responsibility.\n"
            "3. List how the systems interact (id INT-n, source and target system ids, data, protocol).\n"
            "4. List clarifying questions about unknown systems, platforms, existing integrations or "
            "constraints (max 5; empty if none).\n"
            "5. Propose decisions where several approaches are possible, e.g. synchronous vs asynchronous "
            "integration, build vs buy for a capability, which external provider to use.\n"
            f"{DECISION_INSTRUCTIONS}"
        )
        return self._invoke(SystemRequirementsAnalysis, prompt)

    def create(self, context: SysrsContext) -> SystemRequirementSet:
        return self._invoke(SystemRequirementSet, self._base_prompt(context) + self._instructions())

    def update(self, context: SysrsContext, existing: SystemRequirementSet) -> SystemRequirementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing system requirements for this product requirement:\n{existing.model_dump_json()}\n\n"
            + "Update them so they reflect the product requirement, decisions and landscape above. Keep "
            "everything still valid (including titles and wording), add what is new, change what "
            "conflicts, remove what is obsolete.\n"
            + self._instructions()
        )
        return self._invoke(SystemRequirementSet, prompt)

    def revise(
        self, context: SysrsContext, artifact: SystemRequirementSet, review: ReviewResult
    ) -> SystemRequirementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current system requirements:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions()
        )
        return self._invoke(SystemRequirementSet, prompt)

    def _base_prompt(self, context: SysrsContext) -> str:
        landscape = context.analysis.model_dump_json(include={"systems", "interactions"})
        return (
            f"Product requirement:\n{context.prd_requirement.model_dump_json()}\n\n"
            f"Confirmed systems and interactions:\n{landscape}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _instructions() -> str:
        return (
            "Derive the system requirements for THIS product requirement only (including its "
            "sub-requirements and acceptance criteria). Output system requirements, system use cases and "
            "integration requirements, using local ids SR-n, SUC-n, IR-n (they are renumbered later). "
            "Each system requirement names the systems involved by id, e.g. 'Mobile App sends the document "
            "to Document Service, which stores it in the object store and triggers OCR processing', and "
            "has measurable acceptance criteria. Use only the confirmed system ids. Every external system "
            "a requirement relies on needs an integration requirement with interface, data, authentication "
            "and failure handling."
        )
