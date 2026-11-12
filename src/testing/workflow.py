"""Testing workflow: strategy decided with the user, then tests per software requirement linked to design and code."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..architecture.models import ArchitectureDocument
from ..dev.models import DevDocument
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..lld.models import LldDocument
from ..per_item_workflow import PerItemWorkflow
from ..prd.models import ProductRequirementsDocument
from ..srs.models import SoftwareRequirementsDocument
from ..staged_workflow import StageState
from .assembler import QaAssembler
from .author_agent import QaAuthorAgent
from .models import QaAnalysis, QaContext, QaDocument, QaElementSet
from .reviewer_agent import QaReviewerAgent
from .sources import qa_digest, requirement_contexts


class QaWorkflow(PerItemWorkflow):
    name = "testing"
    title = "Testing Artifacts"

    def __init__(
        self,
        author: QaAuthorAgent,
        reviewer: QaReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        assembler: Optional[QaAssembler] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or QaAssembler()
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        prd: ProductRequirementsDocument,
        srs: SoftwareRequirementsDocument,
        architecture: ArchitectureDocument,
        lld: LldDocument,
        dev: DevDocument,
        existing: Optional[ExistingArtifact[QaDocument, QaAnalysis]] = None,
    ) -> StageState:
        inputs = {"prd": prd, "srs": srs, "architecture": architecture, "lld": lld, "dev": dev}
        return self._execute(inputs, existing)

    def _analysis_call(self, state: StageState) -> QaAnalysis:
        existing = state.get("existing")
        i = state["inputs"]
        return self._author.analyze(
            i["prd"], i["srs"], i["architecture"], i["dev"], state["clarifications"], state["feedback"],
            state["decisions"], existing.analysis if existing else None,
        )

    def _elaborate(self, state: StageState) -> QaAnalysis:
        existing = state.get("existing")
        i = state["inputs"]
        strategy = self._author.design_strategy(
            i["prd"], i["srs"], i["architecture"], i["dev"], state["clarifications"], state["decisions"],
            existing.analysis if existing else None,
        )
        self._notes.step("Wrote the test strategy from the verified decisions")
        return state["analysis"].model_copy(update={"strategy": strategy})

    def _describe(self, analysis: QaAnalysis) -> list[str]:
        s = analysis.strategy
        lines = ["\nTest strategy objectives:"]
        lines += [f"  - {o}" for o in s.objectives]
        lines.append("\nTest levels:")
        lines += [f"  - {lvl.name}: {lvl.purpose} [{', '.join(lvl.tools)}]" for lvl in s.levels]
        lines.append(f"\nEnvironments: {', '.join(s.environments)}")
        lines.append(f"Performance: {s.performance_approach}")
        lines.append(f"Security: {s.security_approach}")
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        i = state["inputs"]
        return qa_digest(i["prd"], i["srs"], i["architecture"], i["dev"])

    def _items(self, state: StageState) -> list[tuple[str, QaContext]]:
        i = state["inputs"]
        return requirement_contexts(
            i["prd"], i["srs"], i["architecture"], i["lld"], i["dev"],
            state["analysis"], state["clarifications"], state["decisions"],
        )

    def _extract(self, document: QaDocument, source_id: str) -> QaElementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(self, state: StageState, results: dict[str, QaElementSet], previous: Any) -> QaDocument:
        i = state["inputs"]
        return self._assembler.assemble(
            i["prd"], i["srs"], i["architecture"], i["lld"], i["dev"], state["analysis"], results, previous
        )
