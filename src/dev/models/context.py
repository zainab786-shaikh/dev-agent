from __future__ import annotations

from pydantic import BaseModel, Field

from ...architecture.models import ArchitectureComponent, GlobalDecision
from ...lld.models import ApiEndpoint, DatabaseTable, DataContract, LldElementSet
from ...models import DecisionRecord
from .analysis import DevAnalysis


class DevContext(BaseModel):
    """Inputs for writing the code and unit tests of ONE architecture component."""

    component: ArchitectureComponent
    other_components: list[ArchitectureComponent] = Field(default_factory=list)
    design: LldElementSet = Field(description="The component's detailed design to implement")
    shared_contracts: list[DataContract] = Field(default_factory=list)
    server_apis: list[ApiEndpoint] = Field(default_factory=list, description="For the web client: the server endpoints to call")
    server_contracts: list[DataContract] = Field(default_factory=list, description="For the web client: the server data contracts")
    data_tables: list[DatabaseTable] = Field(default_factory=list, description="For the API server: the tables its ORM entities map")
    architecture_decisions: list[GlobalDecision] = Field(default_factory=list)
    analysis: DevAnalysis
    clarifications: list[str] = Field(default_factory=list)
    decisions: list[DecisionRecord] = Field(default_factory=list)
