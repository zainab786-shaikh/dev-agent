"""Compact system-requirements view for prompts that need the whole document but little detail."""
from __future__ import annotations

import json

from .models import SystemRequirementsDocument


def sysrs_digest(sysrs: SystemRequirementsDocument) -> str:
    return json.dumps(
        {
            "title": sysrs.title,
            "overview": sysrs.overview,
            "systems": [{"id": s.id, "name": s.name, "kind": s.kind.value} for s in sysrs.systems],
            "system_requirements": [
                {"id": r.id, "title": r.title, "description": r.description} for r in sysrs.system_requirements
            ],
        }
    )
