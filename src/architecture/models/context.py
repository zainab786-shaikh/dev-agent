from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ...models import DecisionRecord
from .analysis import ArchitectureAnalysis


class SourceRequirement(BaseModel):
    """One software requirement (functional, non-functional or interface) to design for."""

    id: str
    kind: str = Field(description="functional, non_functional or interface")
    statement: str
    details: dict[str, Any] = Field(default_factory=dict)


class ArchitectureContext(BaseModel):
    """Inputs for designing the architecture for ONE software requirement."""

    requirement: SourceRequirement
    analysis: ArchitectureAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
