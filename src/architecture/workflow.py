"""Architecture workflow: decisions verified by the user, then a design per software requirement."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..models import DecisionOutcome, DecisionRecord
from ..per_item_workflow import PerItemWorkflow
from ..srs.models import SoftwareRequirementsDocument
from ..staged_workflow import StageState
from ..sysrs.models import SystemRequirementsDocument
from .assembler import ArchitectureAssembler
from .author_agent import ArchitectureAuthorAgent
from .models import (
    ArchitectureAnalysis,
    ArchitectureContext,
    ArchitectureDocument,
    ArchitectureElementSet,
)
from .reviewer_agent import ArchitectureReviewerAgent
from .sources import architecture_digest, source_requirements


class ArchitectureWorkflow(PerItemWorkflow):
    name = "architecture"
    title = "Architecture Design"

    def __init__(
        self,
        author: ArchitectureAuthorAgent,
        reviewer: ArchitectureReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        assembler: Optional[ArchitectureAssembler] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or ArchitectureAssembler()
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        srs: SoftwareRequirementsDocument,
        sysrs: SystemRequirementsDocument,
        existing: Optional[ExistingArtifact[ArchitectureDocument, ArchitectureAnalysis]] = None,
    ) -> StageState:
        return self._execute({"srs": srs, "sysrs": sysrs}, existing)

    def _analysis_call(self, state: StageState) -> ArchitectureAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        return self._author.analyze(
            inputs["srs"],
            inputs["sysrs"],
            state["clarifications"],
            state["feedback"],
            state["decisions"],
            existing.analysis if existing else None,
        )

    def _elaborate(self, state: StageState) -> ArchitectureAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        baseline = existing.analysis if existing else None
        args = (inputs["srs"], inputs["sysrs"], state["clarifications"], state["decisions"], baseline)
        landscape = self._author.design_landscape(*args)
        problems = self._tier_problems(landscape)
        if problems:  # one automatic retry, told what was wrong
            landscape = self._author.design_landscape(*args, problems)
            problems = self._tier_problems(landscape)
        for problem in problems:
            self._io.show(f"  warning: {problem}")
            self._notes.step(f"Component design problem left for the user to judge: {problem}")
        self._notes.step(
            f"Designed {len(landscape.components)} component(s) and {len(landscape.interactions)} "
            "interaction(s) consistent with the verified decisions"
        )
        return state["analysis"].model_copy(
            update={"components": landscape.components, "interactions": landscape.interactions}
        )

    @staticmethod
    def _tier_problems(landscape) -> list[str]:
        """The product is a three-tier web application, so the components must form those three tiers."""
        tiers = {c.id: c.tier.strip().lower() for c in landscape.components}
        problems = [f"there is no component in the '{t}' tier" for t in ("client", "api", "data") if t not in tiers.values()]
        for i in landscape.interactions:
            if i.source not in tiers or i.target not in tiers:
                problems.append(f"interaction {i.id} refers to an unknown component")
            elif {tiers[i.source], tiers[i.target]} == {"client", "data"}:
                problems.append(f"interaction {i.id} connects the client directly to the data tier; go through the api tier")
        return problems

    def _describe(self, analysis: ArchitectureAnalysis) -> list[str]:
        names = {c.id: c.name for c in analysis.components}
        lines = ["\nComponents:"]
        lines += [f"  - {c.id} {c.name} [{c.tier}; {c.technology}]: {c.responsibility}" for c in analysis.components]
        lines.append("\nInteractions:")
        for i in analysis.interactions:
            src, dst = names.get(i.source, i.source), names.get(i.target, i.target)
            lines.append(f"  - {src} -> {dst}: {i.description} [{i.mechanism}]")
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return architecture_digest(state["inputs"]["srs"], state["inputs"]["sysrs"])

    def _items(self, state: StageState) -> list[tuple[str, ArchitectureContext]]:
        return [
            (
                r.id,
                ArchitectureContext(
                    requirement=r,
                    analysis=state["analysis"],
                    clarifications=state["clarifications"],
                    decisions=state["decisions"],
                ),
            )
            for r in source_requirements(state["inputs"]["srs"])
        ]

    def _extract(self, document: ArchitectureDocument, source_id: str) -> ArchitectureElementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(
        self, state: StageState, results: dict[str, ArchitectureElementSet], previous: Any
    ) -> ArchitectureDocument:
        return self._assembler.assemble(
            state["inputs"]["srs"], state["analysis"], state["decisions"], results, previous
        )

    def _review_decisions(self, state: StageState, document: ArchitectureDocument) -> dict[str, str]:
        adrs = document.decisions
        if not adrs:
            return {}

        self._io.show("\nArchitecture decisions made while designing:")
        for adr in adrs:
            self._io.show(f"\n{adr.id}: {adr.title}\n  Decision: {adr.decision}\n  Why: {adr.rationale}")
            for o in adr.options:
                self._io.show(f"  - option {o.name}: +{'; '.join(o.pros)} / -{'; '.join(o.cons)}")

        flagged: list = []
        if not self._io.confirm("\nAccept these architecture decisions?"):
            wanted = {i.strip().upper() for i in self._io.ask("Which should be revisited? Enter ids, e.g. ADR-1, ADR-3").split(",")}
            flagged = [a for a in adrs if a.id.upper() in wanted]

        if not flagged:
            for adr in adrs:
                self._notes.decision(
                    DecisionRecord(
                        id=adr.id, stage=self.name, topic=adr.title, context=adr.context, options=adr.options,
                        recommended_option=adr.decision, recommendation_rationale=adr.rationale,
                        chosen=adr.decision, outcome=DecisionOutcome.ACCEPTED_AGENT_CHOICE,
                    )
                )
            self._notes.step(f"The user accepted {len(adrs)} architecture decision(s)")
            return {}

        feedback: dict[str, str] = {}
        for adr in flagged:
            text = self._io.ask(f"What is wrong with {adr.id} ({adr.title})?")
            self._notes.step(f"The user asked to revisit {adr.id} '{adr.title}': {text}")
            for requirement_id in adr.requirement_ids:
                previous = feedback.get(requirement_id, "")
                feedback[requirement_id] = f"{previous} Revisit decision '{adr.title}': {text}.".strip()
        return feedback
