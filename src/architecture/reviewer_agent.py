"""Agent that reviews the architecture designed for one software requirement."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block
from ..models import ReviewResult
from ..review_loop import ArtifactReviewer
from .models import ArchitectureContext, ArchitectureElementSet


class ArchitectureReviewerAgent(BaseAgent, ArtifactReviewer[ArchitectureContext, ArchitectureElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "ArchitectureReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict architecture reviewer. You check that an architecture design satisfies its "
            "requirement, is consistent with the agreed decisions, and is secure, scalable and "
            "deployable. Respond only with JSON matching the given schema."
        )

    def review(self, context: ArchitectureContext, artifact: ArchitectureElementSet) -> ReviewResult:
        landscape = context.analysis.model_dump_json(include={"components", "interactions"})
        prompt = (
            f"Software requirement:\n{context.requirement.model_dump_json()}\n\n"
            f"Confirmed components and interactions:\n{landscape}\n\n"
            f"Confirmed solution-level decisions:\n{decided_block(context.decisions)}\n\n"
            f"Architecture design:\n{artifact.model_dump_json()}\n\n"
            "Review for: a requirement that the design does not actually satisfy; non-functional targets "
            "(users, availability, latency) with no concrete mechanism or numbers; component ids that are "
            "not in the confirmed components; decisions that contradict the confirmed decisions (style, "
            "cloud platform, security model, scalability strategy); ADRs with fewer than 2 evaluated "
            "options, options without pros and cons, a chosen option that is not one of the options, or "
            "no rationale for why it beats the others; missing security controls where data, identity or "
            "access are involved (including encryption at rest and in transit); deployment elements "
            "without scaling or resiliency; over-engineering unrelated to the requirement. Give each "
            "finding a severity (high/medium/low), the affected id, the issue, and a concrete "
            "recommendation. Set approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
