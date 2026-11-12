"""PRD workflow: a single document, created or updated, then reviewed until it passes."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..review_loop import ReviewLoop
from ..staged_workflow import StagedWorkflow, StageState
from .author_agent import PrdAuthorAgent
from .models import ProductContext, ProductRequirementsAnalysis, ProductRequirementsDocument
from .reviewer_agent import PrdReviewerAgent


class PrdWorkflow(StagedWorkflow):
    name = "prd"
    title = "Product Requirements Document"

    def __init__(
        self,
        author: PrdAuthorAgent,
        reviewer: PrdReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
    ) -> None:
        self._author = author
        self._loop: ReviewLoop[ProductContext, ProductRequirementsDocument] = ReviewLoop(
            "PRD", author, reviewer, max_iterations
        )
        super().__init__(interaction, output_dir, judge)

    def run(
        self,
        product_requirement: str,
        existing: Optional[ExistingArtifact[ProductRequirementsDocument, ProductRequirementsAnalysis]] = None,
    ) -> StageState:
        return self._execute({"product_requirement": product_requirement}, existing)

    def _analysis_call(self, state: StageState) -> ProductRequirementsAnalysis:
        existing = state.get("existing")
        return self._author.analyze(
            state["inputs"]["product_requirement"],
            state["clarifications"],
            state["feedback"],
            state["decisions"],
            existing.analysis if existing else None,
            existing.document if existing else None,
        )

    def _describe(self, analysis: ProductRequirementsAnalysis) -> list[str]:
        lines = ["\nIdentified users:"]
        lines += [f"  - {u.name}: {u.description}" for u in analysis.users]
        lines.append("\nProposed non-functional requirements:")
        lines += [f"  - [{n.category}] {n.description}" for n in analysis.non_functional_requirements]
        lines.append("\nProposed abuse cases:")
        lines += [f"  - {a.title}: {a.description} (mitigation: {a.mitigation})" for a in analysis.abuse_cases]
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return state["inputs"]["product_requirement"]

    def _derive(self, state: StageState) -> dict[str, Any]:
        existing = state.get("existing")
        context = ProductContext(
            product_requirement=state["inputs"]["product_requirement"],
            clarifications=state["clarifications"],
            analysis=state["analysis"],
            decisions=state["decisions"],
        )
        outcome = self._loop.run(context, existing=existing.document if existing else None)
        report = {
            "source_id": "PRD",
            "action": "updated" if existing else "created",
            "iterations": outcome.iterations,
            "converged": outcome.converged,
            "review": outcome.review.model_dump(mode="json"),
        }
        self._notes.item(report)
        self._io.show(f"PRD: {report['action']}, {outcome.iterations} iteration(s)")
        return {"document": outcome.artifact, "items": [report], "converged": outcome.converged}
