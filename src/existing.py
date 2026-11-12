"""Loads the latest saved version of an artifact so a run can update it instead of starting over."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel

from .models import DecisionRecord

D = TypeVar("D", bound=BaseModel)
A = TypeVar("A", bound=BaseModel)


def fingerprint(*parts: Any) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


@dataclass
class ExistingArtifact(Generic[D, A]):
    path: Path
    document: D
    analysis: Optional[A] = None
    decisions: list[DecisionRecord] = field(default_factory=list)
    items: dict[str, dict] = field(default_factory=dict)

    def fingerprint(self, source_id: str) -> Optional[str]:
        return self.items.get(source_id, {}).get("fingerprint")


def load_existing(
    directory: Path, name: str, document_cls: type[D], analysis_cls: type[A]
) -> Optional[ExistingArtifact[D, A]]:
    files = sorted(directory.glob(f"{name}_*.json"))
    if not files:
        return None
    path = files[-1]
    data = json.loads(path.read_text(encoding="utf-8"))
    return ExistingArtifact(
        path=path,
        document=document_cls.model_validate(data[name]),
        analysis=analysis_cls.model_validate(data["analysis"]) if data.get("analysis") else None,
        decisions=[DecisionRecord.model_validate(d) for d in data.get("decisions", [])],
        items={i["source_id"]: i for i in data.get("items", [])},
    )
