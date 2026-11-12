from __future__ import annotations

from pydantic import BaseModel, Field

from ...architecture.models import (
    ArchitectureComponent,
    ComponentInteraction,
    DeploymentElement,
    DesignElement,
    GlobalDecision,
    SecurityControl,
    SourceRequirement,
)
from ...models import DecisionRecord
from .document import ApiEndpoint, DatabaseTable, DataContract
from .analysis import LldAnalysis


class LldContext(BaseModel):
    """Inputs for the detailed design of ONE architecture component."""

    component: ArchitectureComponent
    other_components: list[ArchitectureComponent] = Field(default_factory=list)
    interactions: list[ComponentInteraction] = Field(default_factory=list, description="Those touching the component")
    design_elements: list[DesignElement] = Field(default_factory=list)
    security_controls: list[SecurityControl] = Field(default_factory=list)
    deployment_elements: list[DeploymentElement] = Field(default_factory=list)
    architecture_decisions: list[GlobalDecision] = Field(default_factory=list)
    requirements: list[SourceRequirement] = Field(default_factory=list)
    server_apis: list[ApiEndpoint] = Field(default_factory=list, description="For the web client: the API server endpoints")
    server_contracts: list[DataContract] = Field(default_factory=list, description="For the web client: the server data contracts")
    data_tables: list[DatabaseTable] = Field(default_factory=list, description="For the API server: the tables of the data tier")
    analysis: LldAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
