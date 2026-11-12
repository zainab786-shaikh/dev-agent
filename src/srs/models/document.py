"""Schemas for the Software Requirements Specification (SRS)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ...prd.models import Priority


class QualityCategory(str, Enum):
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    SCALABILITY = "scalability"
    SECURITY = "security"
    RELIABILITY = "reliability"
    USABILITY = "usability"
    MAINTAINABILITY = "maintainability"
    COMPLIANCE = "compliance"
    OBSERVABILITY = "observability"


class InterfaceType(str, Enum):
    USER = "user_interface"
    API = "api"
    COMMUNICATION = "communication"
    DATA = "data"
    HARDWARE = "hardware"


class SoftwareSubRequirement(BaseModel):
    id: str = Field(default="", description="e.g. FR-1.1; assigned by the system")
    statement: str = Field(description="'The system shall ...'")
    acceptance_criteria: list[str] = Field(default_factory=list)


class SoftwareFunctionalRequirement(BaseModel):
    id: str = Field(default="", description="e.g. FR-1; assigned by the system")
    title: str
    statement: str = Field(description="One testable sentence: 'The system shall ...'")
    priority: Priority = Priority.MUST
    source_ids: list[str] = Field(default_factory=list, description="PRD or system requirement ids this traces to")
    acceptance_criteria: list[str] = Field(default_factory=list)
    sub_requirements: list[SoftwareSubRequirement] = Field(default_factory=list)


class SoftwareNonFunctionalRequirement(BaseModel):
    id: str = Field(default="", description="e.g. NFR-1; assigned by the system")
    category: QualityCategory
    statement: str = Field(description="'The system shall ...' with a measurable target")
    metric: str = Field(description="What is measured, e.g. availability, response time, concurrent users")
    target: str = Field(description="Measurable target, e.g. 99.95%, < 2 seconds, 10,000 users")
    measurement_method: str = Field(default="", description="How the target is verified")
    priority: Priority = Priority.MUST
    source_ids: list[str] = Field(default_factory=list)


class SoftwareInterfaceRequirement(BaseModel):
    id: str = Field(default="", description="e.g. IFR-1; assigned by the system")
    interface_type: InterfaceType
    name: str
    statement: str = Field(description="'The system shall ...'")
    counterpart: str = Field(description="System, user or device on the other side")
    protocol_or_format: str = Field(default="", description="e.g. HTTPS/REST JSON, AMQP, PDF")
    data_exchanged: str = ""
    source_ids: list[str] = Field(default_factory=list, description="e.g. system integration requirement ids")


class SoftwareRequirementSet(BaseModel):
    """Software requirements derived from ONE system requirement."""

    functional_requirements: list[SoftwareFunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[SoftwareNonFunctionalRequirement] = Field(default_factory=list)
    interface_requirements: list[SoftwareInterfaceRequirement] = Field(default_factory=list)


class SoftwareRequirementsDocument(BaseModel):
    title: str
    overview: str
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    functional_requirements: list[SoftwareFunctionalRequirement] = Field(default_factory=list)
    non_functional_requirements: list[SoftwareNonFunctionalRequirement] = Field(default_factory=list)
    interface_requirements: list[SoftwareInterfaceRequirement] = Field(default_factory=list)
