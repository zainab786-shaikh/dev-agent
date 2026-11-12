from __future__ import annotations

from pydantic import BaseModel, Field

from ...architecture.models import ArchitectureComponent, DeploymentElement, DesignElement, SecurityControl, SourceRequirement
from ...lld.models import ApiEndpoint, ErrorHandlingRule
from ...models import DecisionRecord
from ...prd.models import AbuseCase, ProductRequirement, UserStory
from .analysis import QaAnalysis


class QaContext(BaseModel):
    """Inputs for the tests of ONE software requirement, with everything it traces to."""

    requirement: SourceRequirement
    prd_requirements: list[ProductRequirement] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    abuse_cases: list[AbuseCase] = Field(default_factory=list)
    design_elements: list[DesignElement] = Field(default_factory=list)
    security_controls: list[SecurityControl] = Field(default_factory=list)
    deployment_elements: list[DeploymentElement] = Field(default_factory=list)
    components: list[ArchitectureComponent] = Field(default_factory=list)
    apis: list[ApiEndpoint] = Field(default_factory=list)
    error_rules: list[ErrorHandlingRule] = Field(default_factory=list)
    code_files: list[str] = Field(default_factory=list, description="Source files that implement the requirement")
    unit_test_files: list[str] = Field(default_factory=list)
    code_excerpts: dict[str, str] = Field(
        default_factory=dict, description="Bounded content of the linked files, so tests and reviews see the real code"
    )
    code_versions: dict[str, str] = Field(
        default_factory=dict, description="Content fingerprint per file, so changed code triggers re-testing"
    )
    analysis: QaAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
