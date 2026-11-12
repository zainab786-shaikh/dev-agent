from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import DecisionRecord
from ...prd.models import ProductRequirement
from .analysis import SystemRequirementsAnalysis


class SysrsContext(BaseModel):
    """Inputs for deriving system requirements from ONE product requirement."""

    prd_requirement: ProductRequirement
    analysis: SystemRequirementsAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
