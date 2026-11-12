from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import DecisionRecord
from ...prd.models import ProductRequirement
from ...sysrs.models import IntegrationRequirement, SystemComponent, SystemRequirement
from .analysis import SoftwareRequirementsAnalysis


class SrsContext(BaseModel):
    """Inputs for deriving software requirements from ONE system requirement."""

    system_requirement: SystemRequirement
    prd_requirements: list[ProductRequirement] = Field(default_factory=list)
    systems: list[SystemComponent] = Field(default_factory=list, description="Systems the requirement involves")
    integrations: list[IntegrationRequirement] = Field(default_factory=list)
    analysis: SoftwareRequirementsAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
