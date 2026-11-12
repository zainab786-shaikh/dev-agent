"""Builds the final architecture document from per-requirement results (no LLM)."""
from __future__ import annotations

from typing import Callable, Optional, TypeVar

from pydantic import BaseModel

from ..ids import assign_ids
from ..mermaid import flowchart
from ..models import DecisionOutcome, DecisionRecord
from ..srs.models import SoftwareRequirementsDocument
from .models import (
    ArchitectureAnalysis,
    ArchitectureDocument,
    ArchitectureElementSet,
    ComponentDiagram,
    DeploymentArchitecture,
    GlobalDecision,
    SecurityArchitecture,
)

M = TypeVar("M", bound=BaseModel)


def _trace(items: list[M], requirement_id: str) -> list[M]:
    return [item.model_copy(update={"requirement_ids": [requirement_id]}) for item in items]


def _merge_duplicates(items: list[M], key: Callable[[M], str]) -> list[M]:
    """Several requirements often lead to the same ADR/control/element; keep one and union its links."""
    merged: dict[str, M] = {}
    for item in items:
        k = key(item).strip().lower()
        first = merged.get(k)
        if first is None:
            merged[k] = item
            continue
        update = {"requirement_ids": list(dict.fromkeys([*getattr(first, "requirement_ids"), *getattr(item, "requirement_ids")]))}
        if "component_ids" in type(first).model_fields:
            update["component_ids"] = list(
                dict.fromkeys([*getattr(first, "component_ids"), *getattr(item, "component_ids")])
            )
        merged[k] = first.model_copy(update=update)
    return list(merged.values())


def _decision_text(decisions: list[GlobalDecision], keyword: str) -> str:
    return " ".join(d.decision for d in decisions if keyword in d.topic.lower())


def _global_decision(record: DecisionRecord) -> GlobalDecision:
    rationale = record.recommendation_rationale
    if record.outcome in (DecisionOutcome.CHOSE_OTHER_OPTION, DecisionOutcome.CUSTOM):
        rationale = f"Chosen by the user instead of the recommended '{record.recommended_option}'. {rationale}"
    return GlobalDecision(topic=record.topic, decision=record.chosen, rationale=rationale.strip())


class ArchitectureAssembler:
    def assemble(
        self,
        srs: SoftwareRequirementsDocument,
        analysis: ArchitectureAnalysis,
        decisions: list[DecisionRecord],
        results: dict[str, ArchitectureElementSet],
        previous: Optional[ArchitectureDocument] = None,
    ) -> ArchitectureDocument:
        design, adrs, controls, deployment = [], [], [], []
        for requirement_id, derived in results.items():
            design += _trace(derived.design_elements, requirement_id)
            adrs += _trace(derived.decisions, requirement_id)
            controls += _trace(derived.security_controls, requirement_id)
            deployment += _trace(derived.deployment_elements, requirement_id)

        title = f"Architecture Design for {srs.title}"
        solution = [_global_decision(d) for d in decisions]
        diagram = flowchart(
            [(c.id, f"{c.name} ({c.technology})" if c.technology else c.name) for c in analysis.components],
            [(i.source, i.target, i.description) for i in analysis.interactions],
        )
        old_security = previous.security_architecture.controls if previous else []
        old_deployment = previous.deployment_architecture.elements if previous else []
        return ArchitectureDocument(
            title=title,
            overview=analysis.summary,
            solution_architecture=solution,
            components=analysis.components,
            interactions=analysis.interactions,
            component_diagram=ComponentDiagram(title=title, mermaid=diagram),
            design_elements=assign_ids(
                design, "HLD", previous.design_elements if previous else [],
                lambda d: (tuple(d.requirement_ids), d.title.strip().lower()),
            ),
            decisions=assign_ids(
                _merge_duplicates(adrs, lambda d: d.title), "ADR", previous.decisions if previous else [],
                lambda d: d.title.strip().lower(),
            ),
            security_architecture=SecurityArchitecture(
                model=_decision_text(solution, "security"),
                controls=assign_ids(
                    _merge_duplicates(controls, lambda c: c.title), "SEC", old_security,
                    lambda c: c.title.strip().lower(),
                ),
            ),
            deployment_architecture=DeploymentArchitecture(
                platform=_decision_text(solution, "cloud"),
                elements=assign_ids(
                    _merge_duplicates(deployment, lambda d: d.name), "DEP", old_deployment,
                    lambda d: d.name.strip().lower(),
                ),
            ),
        )

    @staticmethod
    def extract(document: ArchitectureDocument, requirement_id: str) -> ArchitectureElementSet:
        """The part of an existing document that was derived from one software requirement."""
        return ArchitectureElementSet(
            design_elements=[d for d in document.design_elements if requirement_id in d.requirement_ids],
            decisions=[d for d in document.decisions if requirement_id in d.requirement_ids],
            security_controls=[
                c for c in document.security_architecture.controls if requirement_id in c.requirement_ids
            ],
            deployment_elements=[
                d for d in document.deployment_architecture.elements if requirement_id in d.requirement_ids
            ],
        )
