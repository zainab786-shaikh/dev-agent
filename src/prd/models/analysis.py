from __future__ import annotations

from pydantic import BaseModel, Field

from ...models import ClarifyingQuestion, StageAnalysis  # noqa: F401  (ClarifyingQuestion is re-exported)
from .document import AbuseCase, UserPersona


class NonFunctionalProductRequirement(BaseModel):
    category: str = Field(description="e.g. performance, security, usability, reliability")
    description: str


class ProductRequirementsAnalysis(StageAnalysis):
    users: list[UserPersona] = Field(default_factory=list)
    non_functional_requirements: list[NonFunctionalProductRequirement] = Field(default_factory=list)
    abuse_cases: list[AbuseCase] = Field(default_factory=list)
