"""Agent that proposes quality targets and derives software requirements per system requirement."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..models import DecisionRecord, ReviewResult
from ..prd.digest import prd_digest
from ..prd.models import ProductRequirementsDocument
from ..review_loop import ArtifactAuthor
from ..sysrs.digest import sysrs_digest
from ..sysrs.models import SystemRequirementsDocument
from .models import QualityTarget, QualityTargetSet, SoftwareRequirementSet, SoftwareRequirementsAnalysis, SrsContext


class SrsAuthorAgent(BaseAgent, ArtifactAuthor[SrsContext, SoftwareRequirementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "SrsAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a business analyst and engineering lead. You define exactly what the software must "
            "do and its quality attributes as precise, testable 'The system shall ...' requirements. "
            "Respond only with JSON matching the given schema."
        )

    def analyze(
        self,
        prd: ProductRequirementsDocument,
        sysrs: SystemRequirementsDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[SoftwareRequirementsAnalysis],
    ) -> SoftwareRequirementsAnalysis:
        prompt = (
            f"PRD:\n{prd_digest(prd)}\n\n"
            f"System requirements:\n{sysrs_digest(sysrs)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous analysis:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed analysis (keep it unless the inputs or feedback require a change):\n"
            f"{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize what the software must do.\n"
            "2. List the functional areas the software must cover.\n"
            "3. Propose system-wide measurable quality targets (availability, response time, concurrent "
            "users, security such as encryption at rest and in transit, reliability, etc.) with concrete "
            "numbers.\n"
            "4. List the interfaces needed (user, API, communication, data).\n"
            "5. Ask clarifying questions about facts that cannot be inferred, e.g. expected load (max 5; "
            "empty if none).\n"
            "6. Propose decisions where several levels or approaches are possible, e.g. the availability "
            "target (99.9% vs 99.95% vs 99.99%), data retention period, supported concurrency.\n"
            f"{DECISION_INSTRUCTIONS}"
        )
        return self._invoke(SoftwareRequirementsAnalysis, prompt)

    def reconcile_targets(
        self, analysis: SoftwareRequirementsAnalysis, clarifications: list[str], decisions: list[DecisionRecord]
    ) -> list[QualityTarget]:
        prompt = (
            f"Proposed system-wide quality targets (written before the decisions were made):\n"
            f"{analysis.model_dump_json(include={'quality_targets'})}\n\n"
            f"Confirmed decisions (they win over the proposal):\n{decided_block(decisions)}\n\n"
            f"User clarifications:\n{lines(clarifications)}\n\n"
            "Return the complete list of quality targets so that every target agrees with the confirmed "
            "decisions and clarifications (e.g. the chosen availability level). Keep metrics and categories, "
            "change a target only where a decision or clarification requires it."
        )
        return self._invoke(QualityTargetSet, prompt).quality_targets

    def create(self, context: SrsContext) -> SoftwareRequirementSet:
        return self._invoke(SoftwareRequirementSet, self._base_prompt(context) + self._instructions())

    def update(self, context: SrsContext, existing: SoftwareRequirementSet) -> SoftwareRequirementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing software requirements for this system requirement:\n{existing.model_dump_json()}\n\n"
            + "Update them so they reflect the system requirement, decisions and targets above. Keep "
            "everything still valid (including titles and wording), add what is new, change what "
            "conflicts, remove what is obsolete.\n"
            + self._instructions()
        )
        return self._invoke(SoftwareRequirementSet, prompt)

    def revise(
        self, context: SrsContext, artifact: SoftwareRequirementSet, review: ReviewResult
    ) -> SoftwareRequirementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current software requirements:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions()
        )
        return self._invoke(SoftwareRequirementSet, prompt)

    def _base_prompt(self, context: SrsContext) -> str:
        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        targets = context.analysis.model_dump_json(include={"quality_targets", "interfaces"})
        return (
            f"System requirement:\n{context.system_requirement.model_dump_json()}\n\n"
            f"Related product requirements:\n{dump(context.prd_requirements)}\n\n"
            f"Systems involved:\n{dump(context.systems)}\n\n"
            f"Integration requirements involved:\n{dump(context.integrations)}\n\n"
            f"Confirmed system-wide quality targets and interfaces:\n{targets}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _instructions() -> str:
        return (
            "Derive the software requirements for THIS system requirement only. Output functional "
            "requirements, non-functional requirements and interface requirements with local ids FR-n "
            "(sub-requirements FR-n.m), NFR-n, IFR-n (they are renumbered later). Every requirement is one "
            "testable sentence such as 'The system shall validate the file type', with acceptance "
            "criteria. A non-functional requirement needs a category, a metric and a measurable target "
            "and how it is verified; the confirmed system-wide targets are added separately, so only add "
            "non-functional requirements specific to this system requirement. Add an interface "
            "requirement for each integration requirement involved. Cover validation, audit history and "
            "security where this requirement implies them."
        )
