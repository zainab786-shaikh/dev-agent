from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import StageAnalysis
from .document import ArchitectureComponent, ComponentInteraction


class ArchitectureLandscape(BaseModel):
    """Components and interactions, designed after the solution-level decisions are made."""

    components: list[ArchitectureComponent] = Field(default_factory=list)
    interactions: list[ComponentInteraction] = Field(default_factory=list)


class ArchitectureAnalysis(StageAnalysis, ArchitectureLandscape):
    """Proposal the user confirms before the per-requirement design starts."""
