"""Builds the final LLD from per-component results: ids, ownership and diagrams (no LLM)."""
from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

from ..architecture.models import ArchitectureDocument
from ..ids import assign_ids
from .diagrams import class_mermaid, er_mermaid, sequence_mermaid
from .models import ClassDiagram, DatabaseSchema, LldAnalysis, LldDocument, LldElementSet
from .sources import component_requirement_ids

M = TypeVar("M", bound=BaseModel)


def _own(items: list[M], component_id: str) -> list[M]:
    return [item.model_copy(update={"component_id": component_id}) for item in items]


def _unique_by_name(contracts: list[M]) -> list[M]:
    """One contract per owner and name; a component never redefines a shared contract, but may reuse a name of another component."""
    shared = {getattr(c, "name").strip().lower() for c in contracts if not getattr(c, "component_id")}
    seen: dict[tuple[str, str], M] = {}
    for c in contracts:
        name = getattr(c, "name").strip().lower()
        owner = getattr(c, "component_id")
        if owner and name in shared:
            continue
        seen.setdefault((owner, name), c)
    return list(seen.values())


class LldAssembler:
    def assemble(
        self,
        architecture: ArchitectureDocument,
        analysis: LldAnalysis,
        results: dict[str, LldElementSet],
        previous: Optional[LldDocument] = None,
    ) -> LldDocument:
        contracts = _own(analysis.shared_contracts, "")
        apis, tables, classes, sequences, errors, screens = [], [], [], [], [], []
        for component_id, derived in results.items():
            default_requirements = component_requirement_ids(architecture, component_id)
            contracts += _own(derived.data_contracts, component_id)
            apis += [
                a.model_copy(update={"requirement_ids": a.requirement_ids or default_requirements})
                for a in _own(derived.api_specifications, component_id)
            ]
            tables += _own(derived.tables, component_id)
            classes += _own(derived.classes, component_id)
            sequences += [
                s.model_copy(update={"requirement_ids": s.requirement_ids or default_requirements})
                for s in _own(derived.sequence_diagrams, component_id)
            ]
            errors += _own(derived.error_handling, component_id)
            screens += [
                s.model_copy(update={"requirement_ids": s.requirement_ids or default_requirements})
                for s in _own(derived.ui_screens, component_id)
            ]

        old = previous
        contracts = assign_ids(
            _unique_by_name(contracts), "CON", old.data_contracts if old else [],
            lambda c: (c.component_id, c.name.strip().lower()),
        )
        apis = assign_ids(
            apis, "API", old.api_specifications if old else [],
            lambda a: (a.component_id, a.method.upper(), a.path.strip().lower()),
        )
        tables = assign_ids(
            tables, "TBL", old.database_schema.tables if old else [],
            lambda t: (t.component_id, t.name.strip().lower()),
        )
        classes = assign_ids(
            classes, "CLS", old.classes if old else [], lambda c: (c.component_id, c.name.strip().lower())
        )
        sequences = assign_ids(
            sequences, "SEQ", old.sequence_diagrams if old else [], lambda s: (s.component_id, s.title.strip().lower())
        )
        sequences = [s.model_copy(update={"mermaid": sequence_mermaid(s)}) for s in sequences]
        errors = assign_ids(
            errors, "ERR", old.error_handling if old else [], lambda e: (e.component_id, e.scenario.strip().lower())
        )

        screens = assign_ids(
            screens, "SCR", old.ui_screens if old else [], lambda s: (s.component_id, s.name.strip().lower())
        )

        names = {c.id: c.name for c in architecture.components}
        class_diagrams = [
            ClassDiagram(
                component_id=cid,
                title=f"{names.get(cid, cid)} classes",
                mermaid=class_mermaid([c for c in classes if c.component_id == cid]),
            )
            for cid in dict.fromkeys(c.component_id for c in classes)
        ]
        return LldDocument(
            title=f"Detailed Technical Design for {architecture.title}",
            overview=analysis.summary,
            conventions=analysis.conventions,
            data_contracts=contracts,
            api_specifications=apis,
            database_schema=DatabaseSchema(tables=tables, mermaid=er_mermaid(tables)),
            classes=classes,
            class_diagrams=class_diagrams,
            sequence_diagrams=sequences,
            error_handling=errors,
            ui_screens=screens,
        )

    @staticmethod
    def extract(document: LldDocument, component_id: str) -> LldElementSet:
        """The part of an existing LLD that was derived from one component."""

        def mine(items):
            return [i for i in items if i.component_id == component_id]

        return LldElementSet(
            data_contracts=mine(document.data_contracts),
            api_specifications=mine(document.api_specifications),
            tables=mine(document.database_schema.tables),
            classes=mine(document.classes),
            sequence_diagrams=mine(document.sequence_diagrams),
            error_handling=mine(document.error_handling),
            ui_screens=mine(document.ui_screens),
        )
