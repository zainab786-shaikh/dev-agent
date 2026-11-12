"""Turns an SRS into the list of requirements to design for, and a compact view for prompts."""
from __future__ import annotations

import json

from ..srs.models import SoftwareRequirementsDocument
from ..sysrs.models import SystemRequirementsDocument
from .models import SourceRequirement


def source_requirements(srs: SoftwareRequirementsDocument) -> list[SourceRequirement]:
    items = [
        SourceRequirement(
            id=r.id, kind="functional", statement=r.statement,
            details=r.model_dump(mode="json", exclude={"id", "statement", "source_ids"}),
        )
        for r in srs.functional_requirements
    ]
    items += [
        SourceRequirement(
            id=r.id, kind="non_functional", statement=r.statement,
            details=r.model_dump(mode="json", exclude={"id", "statement", "source_ids"}),
        )
        for r in srs.non_functional_requirements
    ]
    items += [
        SourceRequirement(
            id=r.id, kind="interface", statement=r.statement,
            details=r.model_dump(mode="json", exclude={"id", "statement", "source_ids"}),
        )
        for r in srs.interface_requirements
    ]
    return items


def architecture_digest(srs: SoftwareRequirementsDocument, sysrs: SystemRequirementsDocument) -> str:
    return json.dumps(
        {
            "title": srs.title,
            "overview": srs.overview,
            "systems": [{"name": s.name, "kind": s.kind.value, "responsibility": s.responsibility} for s in sysrs.systems],
            "functional": [{"id": r.id, "statement": r.statement} for r in srs.functional_requirements],
            "non_functional": [
                {"id": r.id, "category": r.category.value, "metric": r.metric, "target": r.target}
                for r in srs.non_functional_requirements
            ],
            "interfaces": [
                {"id": r.id, "name": r.name, "counterpart": r.counterpart, "protocol": r.protocol_or_format}
                for r in srs.interface_requirements
            ],
        }
    )
