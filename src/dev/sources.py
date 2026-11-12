"""Compact view of the architecture and LLD used to prompt the dev stage."""
from __future__ import annotations

import json

from ..architecture.models import ArchitectureDocument
from ..lld.models import LldDocument


def dev_digest(architecture: ArchitectureDocument, lld: LldDocument) -> str:
    return json.dumps(
        {
            "title": architecture.title,
            "architecture_decisions": [
                {"topic": d.topic, "decision": d.decision} for d in architecture.solution_architecture
            ],
            "lld_conventions": lld.conventions,
            "components": [
                {
                    "id": c.id,
                    "name": c.name,
                    "technology": c.technology,
                    "apis": [f"{a.method} {a.path}" for a in lld.api_specifications if a.component_id == c.id],
                    "tables": [t.name for t in lld.database_schema.tables if t.component_id == c.id],
                    "classes": [k.name for k in lld.classes if k.component_id == c.id],
                }
                for c in architecture.components
            ],
        }
    )
