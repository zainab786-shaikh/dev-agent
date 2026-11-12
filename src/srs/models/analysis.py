from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import StageAnalysis
from .document import QualityCategory


class QualityTarget(BaseModel):
    category: QualityCategory
    metric: str
    target: str = Field(description="Proposed measurable target, e.g. 99.95%, < 2 seconds")


class QualityTargetSet(BaseModel):
    quality_targets: list[QualityTarget] = Field(default_factory=list)


class SoftwareRequirementsAnalysis(StageAnalysis):
    """Proposal the user confirms before the per-requirement derivation."""

    functional_areas: list[str] = Field(default_factory=list, description="Capabilities the software must provide")
    quality_targets: list[QualityTarget] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list, description="User, API and system interfaces needed")
