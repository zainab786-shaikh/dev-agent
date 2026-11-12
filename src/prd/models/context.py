from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import DecisionRecord
from .analysis import ProductRequirementsAnalysis


class ProductContext(BaseModel):
    """Confirmed inputs the PRD is written from."""

    product_requirement: str
    clarifications: list[str] = Field(default_factory=list)
    analysis: ProductRequirementsAnalysis
    decisions: list[DecisionRecord] = Field(default_factory=list)
