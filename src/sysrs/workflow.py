"""SysRS workflow: derive system requirements per product requirement, creating or updating."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..per_item_workflow import PerItemWorkflow
from ..prd.digest import prd_digest
from ..prd.models import ProductRequirementsDocument
from ..staged_workflow import StageState
from .assembler import SysrsAssembler
from .author_agent import SysrsAuthorAgent
from .models import SysrsContext, SystemRequirementsAnalysis, SystemRequirementsDocument, SystemRequirementSet
from .reviewer_agent import SysrsReviewerAgent


class SysrsWorkflow(PerItemWorkflow):
    name = "sysrs"
    title = "System Requirements Specification"

    def __init__(
        self,
        author: SysrsAuthorAgent,
        reviewer: SysrsReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        assembler: Optional[SysrsAssembler] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or SysrsAssembler()
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        prd: ProductRequirementsDocument,
        existing: Optional[ExistingArtifact[SystemRequirementsDocument, SystemRequirementsAnalysis]] = None,
    ) -> StageState:
        return self._execute({"prd": prd}, existing)

    def _analysis_call(self, state: StageState) -> SystemRequirementsAnalysis:
        existing = state.get("existing")
        return self._author.analyze(
            state["inputs"]["prd"],
            state["clarifications"],
            state["feedback"],
            state["decisions"],
            existing.analysis if existing else None,
        )

    def _describe(self, analysis: SystemRequirementsAnalysis) -> list[str]:
        names = {s.id: s.name for s in analysis.systems}
        lines = ["\nParticipating systems:"]
        lines += [f"  - {s.id} {s.name} ({s.kind.value}): {s.responsibility}" for s in analysis.systems]
        lines.append("\nSystem interactions:")
        for i in analysis.interactions:
            src, dst = names.get(i.source, i.source), names.get(i.target, i.target)
            lines.append(f"  - {src} -> {dst}: {i.description} [{i.protocol}]")
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return prd_digest(state["inputs"]["prd"])

    def _items(self, state: StageState) -> list[tuple[str, SysrsContext]]:
        prd = state["inputs"]["prd"]
        return [
            (
                r.id,
                SysrsContext(
                    prd_requirement=r,
                    analysis=state["analysis"],
                    clarifications=state["clarifications"],
                    decisions=state["decisions"],
                ),
            )
            for r in [*prd.functional_requirements, *prd.non_functional_requirements]
        ]

    def _extract(self, document: SystemRequirementsDocument, source_id: str) -> SystemRequirementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(
        self, state: StageState, results: dict[str, SystemRequirementSet], previous: Any
    ) -> SystemRequirementsDocument:
        return self._assembler.assemble(state["inputs"]["prd"], state["analysis"], results, previous)
