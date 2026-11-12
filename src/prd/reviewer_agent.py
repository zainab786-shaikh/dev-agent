"""Agent that reviews the PRD and recommends improvements."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block, lines
from ..models import ReviewResult
from ..review_loop import ArtifactReviewer
from .models import ProductContext, ProductRequirementsDocument


class PrdReviewerAgent(BaseAgent, ArtifactReviewer[ProductContext, ProductRequirementsDocument]):
    @property
    def name(self) -> str:
        return "PrdReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict PRD reviewer. You check a product requirements document for completeness, "
            "clarity, testability, consistency, and good structure. Respond only with JSON "
            "matching the given schema."
        )

    def review(self, context: ProductContext, artifact: ProductRequirementsDocument) -> ReviewResult:
        prompt = (
            f"Product requirement:\n{context.product_requirement}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
            f"Confirmed decisions:\n{decided_block(context.decisions)}\n\n"
            f"PRD:\n{artifact.model_dump_json(indent=2)}\n\n"
            "Review for: missing or ambiguous requirements, unmeasurable or untestable wording, "
            "duplicates or conflicts, missing acceptance criteria, poor hierarchy between requirements "
            "and sub-requirements, wrong or duplicate ids, and uncovered abuse cases. "
            "Also check that the PRD defines users, functional scope (in/out), user stories, use cases "
            "and user journeys; that every functional requirement is covered by a user story; that every "
            "story and journey refers to a listed user; that acceptance criteria are measurable; and "
            "that no technology choices appear (business functionality only). "
            "Give each finding a severity (high/medium/low), the affected requirement id, the issue, "
            "and a concrete recommendation. Set approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
