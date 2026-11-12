"""Schemas for the System Requirements Document (SysRS)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ...prd.models import Priority


class SystemKind(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"


class SystemComponent(BaseModel):
    id: str = Field(description="e.g. SYS-1")
    name: str = Field(description="e.g. Mobile App, Document Service, Azure Blob Storage")
    kind: SystemKind
    responsibility: str


class SystemInteraction(BaseModel):
    id: str = Field(description="e.g. INT-1")
    source: str = Field(description="Id of the calling system")
    target: str = Field(description="Id of the called system")
    description: str
    data_exchanged: str = ""
    protocol: str = Field(default="", description="e.g. HTTPS/REST, message queue, event")


class SystemRequirement(BaseModel):
    id: str = Field(default="", description="e.g. SR-1; assigned by the system")
    title: str
    description: str = Field(description="What the system must do, naming the systems involved")
    priority: Priority = Priority.MUST
    prd_requirement_ids: list[str] = Field(default_factory=list, description="PRD requirement ids this traces to")
    system_ids: list[str] = Field(default_factory=list, description="Systems that take part")
    acceptance_criteria: list[str] = Field(default_factory=list)


class IntegrationRequirement(BaseModel):
    id: str = Field(default="", description="e.g. IR-1; assigned by the system")
    title: str
    external_system: str = Field(description="Id of the external system")
    direction: str = Field(description="inbound, outbound or bidirectional")
    interface: str = Field(description="e.g. REST API, SDK, webhook, file drop")
    data_exchanged: str
    authentication: str = ""
    failure_handling: str = Field(default="", description="Retries, timeouts, fallbacks")
    prd_requirement_ids: list[str] = Field(default_factory=list)


class SystemUseCase(BaseModel):
    id: str = Field(default="", description="e.g. SUC-1; assigned by the system")
    title: str
    trigger: str
    systems_involved: list[str] = Field(default_factory=list, description="System ids")
    steps: list[str] = Field(default_factory=list, description="Ordered system-to-system steps")
    postconditions: list[str] = Field(default_factory=list)
    prd_use_case_ids: list[str] = Field(default_factory=list)
    prd_requirement_ids: list[str] = Field(default_factory=list)


class ContextDiagram(BaseModel):
    title: str
    mermaid: str = Field(description="Mermaid flowchart source showing systems and their interactions")
    description: str = ""


class SystemRequirementSet(BaseModel):
    """System requirements derived from ONE product requirement."""

    system_requirements: list[SystemRequirement] = Field(default_factory=list)
    system_use_cases: list[SystemUseCase] = Field(default_factory=list)
    integration_requirements: list[IntegrationRequirement] = Field(default_factory=list)


class SystemRequirementsDocument(BaseModel):
    title: str
    overview: str
    systems: list[SystemComponent] = Field(default_factory=list)
    context_diagram: ContextDiagram
    interactions: list[SystemInteraction] = Field(default_factory=list)
    system_requirements: list[SystemRequirement] = Field(default_factory=list)
    system_use_cases: list[SystemUseCase] = Field(default_factory=list)
    integration_requirements: list[IntegrationRequirement] = Field(default_factory=list)
