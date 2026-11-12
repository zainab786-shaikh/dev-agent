from __future__ import annotations

from pydantic import Field

from ...models import StageAnalysis
from .document import SystemComponent, SystemInteraction


class SystemRequirementsAnalysis(StageAnalysis):
    """Proposal the user confirms before the per-requirement derivation."""

    systems: list[SystemComponent] = Field(default_factory=list)
    interactions: list[SystemInteraction] = Field(default_factory=list)
