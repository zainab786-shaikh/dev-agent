"""LLD workflow: conventions and shared contracts confirmed once, then a detailed design per component."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..architecture.models import ArchitectureComponent, ArchitectureDocument, GlobalDecision
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..per_item_workflow import PerItemWorkflow
from ..srs.models import SoftwareRequirementsDocument
from ..staged_workflow import StageState
from .assembler import LldAssembler
from .author_agent import LldAuthorAgent
from .models import LldAnalysis, LldContext, LldDocument, LldElementSet
from .reviewer_agent import LldReviewerAgent
from .sources import component_requirement_ids, lld_digest, related_requirements


# The data tier is designed first, then the API server, then the web client, each using the previous ones.
_TIER_ORDER = {"data": 0, "api": 1, "external": 2, "client": 3}


def _plain(item):
    """Without the ids and owners the system assigns, so a reused item looks the same as a fresh one."""
    cleared = {f: v for f, v in (("id", ""), ("component_id", ""), ("requirement_ids", [])) if f in type(item).model_fields}
    return item.model_copy(update=cleared)


class LldWorkflow(PerItemWorkflow):
    name = "lld"
    title = "Detailed Technical Design"

    def __init__(
        self,
        author: LldAuthorAgent,
        reviewer: LldReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        assembler: Optional[LldAssembler] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or LldAssembler()
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        srs: SoftwareRequirementsDocument,
        architecture: ArchitectureDocument,
        existing: Optional[ExistingArtifact[LldDocument, LldAnalysis]] = None,
    ) -> StageState:
        return self._execute({"srs": srs, "architecture": architecture}, existing)

    def _analysis_call(self, state: StageState) -> LldAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        return self._author.analyze(
            inputs["architecture"],
            inputs["srs"],
            state["clarifications"],
            state["feedback"],
            state["decisions"],
            existing.analysis if existing else None,
        )

    def _describe(self, analysis: LldAnalysis) -> list[str]:
        lines = ["\nConventions:"]
        lines += [f"  - {c}" for c in analysis.conventions]
        lines.append("\nShared data contracts:")
        for contract in analysis.shared_contracts:
            fields = ", ".join(f"{f.name}: {f.type}" for f in contract.fields)
            lines.append(f"  - {contract.name}: {fields}")
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return lld_digest(state["inputs"]["architecture"], state["inputs"]["srs"])

    def _context_for(self, state: StageState, component: ArchitectureComponent) -> LldContext:
        srs, architecture = state["inputs"]["srs"], state["inputs"]["architecture"]
        wanted = set(component_requirement_ids(architecture, component.id))
        decisions = [*architecture.solution_architecture]
        decisions += [
            GlobalDecision(topic=a.title, decision=a.decision, rationale=a.rationale)
            for a in architecture.decisions
            if wanted & set(a.requirement_ids)
        ]
        return LldContext(
            component=component,
            other_components=[c for c in architecture.components if c.id != component.id],
            interactions=[i for i in architecture.interactions if component.id in (i.source, i.target)],
            design_elements=[d for d in architecture.design_elements if component.id in d.component_ids],
            security_controls=[
                c for c in architecture.security_architecture.controls if component.id in c.component_ids
            ],
            deployment_elements=[
                d for d in architecture.deployment_architecture.elements if component.id in d.component_ids
            ],
            architecture_decisions=decisions,
            requirements=related_requirements(architecture, srs, component),
            analysis=state["analysis"],
            clarifications=state["clarifications"],
            decisions=state["decisions"],
        )

    def _items(self, state: StageState) -> list[tuple[str, LldContext]]:
        components = sorted(
            state["inputs"]["architecture"].components, key=lambda c: _TIER_ORDER.get(c.tier.strip().lower(), 2)
        )
        return [(c.id, self._context_for(state, c)) for c in components]

    def _enrich(self, source_id: str, context: LldContext, results: dict[str, LldElementSet]) -> LldContext:
        tier = context.component.tier.strip().lower()
        others = {c.id: c.tier.strip().lower() for c in context.other_components}
        done = lambda wanted: [results[cid] for cid, t in others.items() if t == wanted and cid in results]  # noqa: E731
        if tier == "client":
            servers = done("api")
            return context.model_copy(update={
                "server_apis": [_plain(a) for s in servers for a in s.api_specifications],
                "server_contracts": [_plain(c) for s in servers for c in s.data_contracts],
            })
        if tier == "api":
            return context.model_copy(update={"data_tables": [_plain(t) for s in done("data") for t in s.tables]})
        return context

    def _extract(self, document: LldDocument, source_id: str) -> LldElementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(self, state: StageState, results: dict[str, LldElementSet], previous: Any) -> LldDocument:
        return self._assembler.assemble(state["inputs"]["architecture"], state["analysis"], results, previous)
