"""Schemas for the Architecture Design (SAD, HLD, ADRs, security and deployment architecture)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ...models import DecisionOption


class GlobalDecision(BaseModel):
    topic: str = Field(
        description="e.g. architecture style (monolith/microservices), cloud platform, security model, "
        "scalability strategy, data storage, messaging"
    )
    decision: str
    rationale: str = ""


class ArchitectureComponent(BaseModel):
    id: str = Field(description="e.g. COMP-1")
    name: str
    responsibility: str
    technology: str = Field(default="", description="e.g. Azure Kubernetes Service, Cosmos DB, Event Hubs")
    tier: str = Field(default="", description="client (web client), api (API server), data (database) or external")


class ComponentInteraction(BaseModel):
    id: str = Field(description="e.g. CI-1")
    source: str = Field(description="Id of the calling component")
    target: str = Field(description="Id of the called component")
    description: str
    mechanism: str = Field(default="", description="e.g. REST, gRPC, event stream, queue")


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class SecurityCategory(str, Enum):
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    ENCRYPTION_AT_REST = "encryption_at_rest"
    ENCRYPTION_IN_TRANSIT = "encryption_in_transit"
    NETWORK_SECURITY = "network_security"
    SECRETS_MANAGEMENT = "secrets_management"
    AUDIT_LOGGING = "audit_logging"
    DATA_PROTECTION = "data_protection"
    OTHER = "other"


class DesignElement(BaseModel):
    """High-level design: how components realize a requirement."""

    id: str = Field(default="", description="e.g. HLD-1; assigned by the system")
    title: str
    description: str
    component_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class ArchitectureDecisionRecord(BaseModel):
    id: str = Field(default="", description="e.g. ADR-1; assigned by the system")
    title: str
    status: DecisionStatus = DecisionStatus.ACCEPTED
    context: str = Field(description="The requirement or force that drives the decision")
    options: list[DecisionOption] = Field(
        default_factory=list, description="2 to 4 options evaluated, each with pros and cons"
    )
    decision: str = Field(description="The chosen option and how it is applied")
    rationale: str = Field(default="", description="Why the chosen option beats the others")
    consequences: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class SecurityControl(BaseModel):
    id: str = Field(default="", description="e.g. SEC-1; assigned by the system")
    title: str
    category: SecurityCategory
    description: str
    component_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class DeploymentElement(BaseModel):
    id: str = Field(default="", description="e.g. DEP-1; assigned by the system")
    name: str
    platform_service: str = Field(description="e.g. Azure Kubernetes Service, Azure Front Door")
    scaling: str = Field(default="", description="How it scales, with numbers where the requirement has them")
    resiliency: str = Field(default="", description="Redundancy, zones/regions, failover, backup")
    component_ids: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)


class ArchitectureElementSet(BaseModel):
    """Architecture derived from ONE software requirement."""

    design_elements: list[DesignElement] = Field(default_factory=list)
    decisions: list[ArchitectureDecisionRecord] = Field(default_factory=list)
    security_controls: list[SecurityControl] = Field(default_factory=list)
    deployment_elements: list[DeploymentElement] = Field(default_factory=list)


class ComponentDiagram(BaseModel):
    title: str
    mermaid: str


class SecurityArchitecture(BaseModel):
    model: str = ""
    controls: list[SecurityControl] = Field(default_factory=list)


class DeploymentArchitecture(BaseModel):
    platform: str = ""
    elements: list[DeploymentElement] = Field(default_factory=list)


class ArchitectureDocument(BaseModel):
    title: str
    overview: str
    solution_architecture: list[GlobalDecision] = Field(default_factory=list)
    components: list[ArchitectureComponent] = Field(default_factory=list)
    interactions: list[ComponentInteraction] = Field(default_factory=list)
    component_diagram: ComponentDiagram
    design_elements: list[DesignElement] = Field(default_factory=list)
    decisions: list[ArchitectureDecisionRecord] = Field(default_factory=list)
    security_architecture: SecurityArchitecture = Field(default_factory=SecurityArchitecture)
    deployment_architecture: DeploymentArchitecture = Field(default_factory=DeploymentArchitecture)
