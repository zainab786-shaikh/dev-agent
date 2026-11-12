"""Agent that reviews the software requirements derived from one system requirement."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block, lines
from ..models import ReviewResult
from ..review_loop import ArtifactReviewer
from .models import SoftwareRequirementSet, SrsContext


class SrsReviewerAgent(BaseAgent, ArtifactReviewer[SrsContext, SoftwareRequirementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "SrsReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict software requirements reviewer. You check software requirements for "
            "completeness, testability, traceability and measurable quality attributes. Respond only "
            "with JSON matching the given schema."
        )

    def review(self, context: SrsContext, artifact: SoftwareRequirementSet) -> ReviewResult:
        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        prompt = (
            f"System requirement:\n{context.system_requirement.model_dump_json()}\n\n"
            f"Related product requirements:\n{dump(context.prd_requirements)}\n\n"
            f"Systems involved:\n{dump(context.systems)}\n\n"
            f"Integration requirements involved:\n[{','.join(i.model_dump_json() for i in context.integrations)}]\n\n"
            f"Confirmed quality targets and interfaces:\n"
            f"{context.analysis.model_dump_json(include={'quality_targets', 'interfaces'})}\n\n"
            f"Confirmed decisions:\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
            f"Derived software requirements:\n{artifact.model_dump_json()}\n\n"
            "Review for: parts of the system requirement or its acceptance criteria that no software "
            "requirement covers; no functional requirements at all; statements that are vague, compound "
            "(several 'shall' in one) or not testable; missing acceptance criteria; non-functional "
            "requirements without a metric, measurable target or verification method; integration "
            "requirements without an interface requirement; conflicts or duplicates. Give each finding a "
            "severity (high/medium/low), the affected id, the issue, and a concrete recommendation. Set "
            "approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
