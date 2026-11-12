"""Compact PRD view for prompts that need the whole document but little detail."""
from __future__ import annotations

import json

from .models import ProductRequirement, ProductRequirementsDocument


def _brief(requirements: list[ProductRequirement]) -> list[dict]:
    return [{"id": r.id, "title": r.title, "description": r.description} for r in requirements]


def prd_digest(prd: ProductRequirementsDocument) -> str:
    return json.dumps(
        {
            "title": prd.title,
            "overview": prd.overview,
            "users": [u.name for u in prd.users],
            "functional_requirements": _brief(prd.functional_requirements),
            "non_functional_requirements": _brief(prd.non_functional_requirements),
            "abuse_cases": [a.title for a in prd.abuse_cases],
        }
    )
