"""SRS workflow: derive software requirements per system requirement, creating or updating."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..per_item_workflow import PerItemWorkflow
from ..prd.models import ProductRequirementsDocument
from ..staged_workflow import StageState
from ..sysrs.digest import sysrs_digest
from ..sysrs.models import SystemRequirement, SystemRequirementsDocument
from .assembler import SrsAssembler
from .author_agent import SrsAuthorAgent
from .models import SoftwareRequirementSet, SoftwareRequirementsAnalysis, SoftwareRequirementsDocument, SrsContext
from .reviewer_agent import SrsReviewerAgent


class SrsWorkflow(PerItemWorkflow):
    name = "srs"
    title = "Software Requirements Specification"

    def __init__(
        self,
        author: SrsAuthorAgent,
        reviewer: SrsReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        assembler: Optional[SrsAssembler] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or SrsAssembler()
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        prd: ProductRequirementsDocument,
        sysrs: SystemRequirementsDocument,
        existing: Optional[ExistingArtifact[SoftwareRequirementsDocument, SoftwareRequirementsAnalysis]] = None,
    ) -> StageState:
        return self._execute({"prd": prd, "sysrs": sysrs}, existing)

    def _analysis_call(self, state: StageState) -> SoftwareRequirementsAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        return self._author.analyze(
            inputs["prd"],
            inputs["sysrs"],
            state["clarifications"],
            state["feedback"],
            state["decisions"],
            existing.analysis if existing else None,
        )

    def _elaborate(self, state: StageState) -> SoftwareRequirementsAnalysis:
        analysis, existing = state["analysis"], state.get("existing")
        if not analysis.quality_targets:
            return analysis
        decided = {(d.topic, d.chosen) for d in state["decisions"]}
        if existing and existing.analysis and not state["clarifications"] and decided == {
            (d.topic, d.chosen) for d in existing.decisions
        }:
            # Nothing new since the last run: keep the reconciled targets so unchanged items stay reusable.
            return analysis.model_copy(update={"quality_targets": existing.analysis.quality_targets})
        targets = self._author.reconcile_targets(analysis, state["clarifications"], state["decisions"])
        self._notes.step("Reconciled the quality targets with the verified decisions and clarifications")
        return analysis.model_copy(update={"quality_targets": targets})

    def _describe(self, analysis: SoftwareRequirementsAnalysis) -> list[str]:
        lines = ["\nFunctional areas:"]
        lines += [f"  - {area}" for area in analysis.functional_areas]
        lines.append("\nProposed quality targets:")
        lines += [f"  - [{t.category.value}] {t.metric}: {t.target}" for t in analysis.quality_targets]
        lines.append("\nInterfaces:")
        lines += [f"  - {i}" for i in analysis.interfaces]
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return sysrs_digest(state["inputs"]["sysrs"])

    def _context_for(self, state: StageState, requirement: SystemRequirement) -> SrsContext:
        prd, sysrs = state["inputs"]["prd"], state["inputs"]["sysrs"]
        prd_items = [*prd.functional_requirements, *prd.non_functional_requirements]
        return SrsContext(
            system_requirement=requirement,
            prd_requirements=[r for r in prd_items if r.id in requirement.prd_requirement_ids],
            systems=[s for s in sysrs.systems if s.id in requirement.system_ids],
            integrations=[i for i in sysrs.integration_requirements if i.external_system in requirement.system_ids],
            analysis=state["analysis"],
            clarifications=state["clarifications"],
            decisions=state["decisions"],
        )

    def _items(self, state: StageState) -> list[tuple[str, SrsContext]]:
        return [(r.id, self._context_for(state, r)) for r in state["inputs"]["sysrs"].system_requirements]

    def _extract(self, document: SoftwareRequirementsDocument, source_id: str) -> SoftwareRequirementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(
        self, state: StageState, results: dict[str, SoftwareRequirementSet], previous: Any
    ) -> SoftwareRequirementsDocument:
        return self._assembler.assemble(
            state["inputs"]["sysrs"], state["analysis"], state["clarifications"], results, previous
        )
