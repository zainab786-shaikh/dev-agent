"""Agent that reviews the system requirements derived from one product requirement."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block, lines
from ..models import ReviewResult
from ..review_loop import ArtifactReviewer
from .models import SysrsContext, SystemRequirementSet


class SysrsReviewerAgent(BaseAgent, ArtifactReviewer[SysrsContext, SystemRequirementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "SysrsReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict system architecture reviewer. You check system requirements for "
            "completeness, traceability to the product requirement, consistency and clear system "
            "boundaries. Respond only with JSON matching the given schema."
        )

    def review(self, context: SysrsContext, artifact: SystemRequirementSet) -> ReviewResult:
        landscape = context.analysis.model_dump_json(include={"systems", "interactions"})
        prompt = (
            f"Product requirement:\n{context.prd_requirement.model_dump_json()}\n\n"
            f"Confirmed systems and interactions:\n{landscape}\n\n"
            f"Confirmed decisions:\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
            f"Derived system requirements:\n{artifact.model_dump_json()}\n\n"
            "Review for: parts of the product requirement, its sub-requirements or acceptance criteria "
            "that no system requirement covers; no system requirements at all; system ids that are not in "
            "the confirmed systems; system requirements that ignore the confirmed interactions; external "
            "systems used without an integration requirement; integration requirements missing interface, "
            "authentication or failure handling; vague or untestable wording; duplicates. Give each "
            "finding a severity (high/medium/low), the affected id, the issue, and a concrete "
            "recommendation. Set approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
