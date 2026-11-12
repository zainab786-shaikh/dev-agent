"""Builds the final system requirements document from per-requirement results (no LLM)."""
from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

from ..ids import assign_ids
from ..mermaid import flowchart
from ..prd.models import ProductRequirementsDocument
from .models import (
    ContextDiagram,
    SystemComponent,
    SystemInteraction,
    SystemRequirementsAnalysis,
    SystemRequirementSet,
    SystemRequirementsDocument,
)

M = TypeVar("M", bound=BaseModel)


def build_context_diagram(
    title: str, systems: list[SystemComponent], interactions: list[SystemInteraction]
) -> ContextDiagram:
    mermaid = flowchart(
        [(s.id, s.name) for s in systems],
        [(i.source, i.target, i.description) for i in interactions],
    )
    return ContextDiagram(title=title, mermaid=mermaid)


def _trace(items: list[M], source_id: str) -> list[M]:
    return [item.model_copy(update={"prd_requirement_ids": [source_id]}) for item in items]


def _key(item) -> tuple:
    return (tuple(item.prd_requirement_ids), item.title.strip().lower())


class SysrsAssembler:
    def assemble(
        self,
        prd: ProductRequirementsDocument,
        analysis: SystemRequirementsAnalysis,
        results: dict[str, SystemRequirementSet],
        previous: Optional[SystemRequirementsDocument] = None,
    ) -> SystemRequirementsDocument:
        requirements, use_cases, integrations = [], [], []
        for source_id, derived in results.items():
            requirements += _trace(derived.system_requirements, source_id)
            use_cases += _trace(derived.system_use_cases, source_id)
            integrations += _trace(derived.integration_requirements, source_id)

        title = f"System Requirements for {prd.title}"
        return SystemRequirementsDocument(
            title=title,
            overview=analysis.summary,
            systems=analysis.systems,
            context_diagram=build_context_diagram(title, analysis.systems, analysis.interactions),
            interactions=analysis.interactions,
            system_requirements=assign_ids(
                requirements, "SR", previous.system_requirements if previous else [], _key
            ),
            system_use_cases=assign_ids(use_cases, "SUC", previous.system_use_cases if previous else [], _key),
            integration_requirements=assign_ids(
                integrations, "IR", previous.integration_requirements if previous else [], _key
            ),
        )

    @staticmethod
    def extract(document: SystemRequirementsDocument, source_id: str) -> SystemRequirementSet:
        """The part of an existing document that was derived from one product requirement."""
        return SystemRequirementSet(
            system_requirements=[r for r in document.system_requirements if source_id in r.prd_requirement_ids],
            system_use_cases=[u for u in document.system_use_cases if source_id in u.prd_requirement_ids],
            integration_requirements=[
                i for i in document.integration_requirements if source_id in i.prd_requirement_ids
            ],
        )
