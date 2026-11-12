"""Schemas for the Detailed Technical Design (LLD). Ids, component ids and diagrams are filled in by code."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ContractField(BaseModel):
    name: str
    type: str = Field(description="e.g. string, int, uuid, datetime, list<Item>, or another contract name")
    required: bool = True
    description: str = ""
    constraints: str = Field(default="", description="e.g. max length 255, > 0, allowed values")


class DataContract(BaseModel):
    """A request, response, event or entity shape shared between services."""

    id: str = ""
    name: str
    description: str = ""
    fields: list[ContractField] = Field(default_factory=list)
    component_id: str = Field(default="", description="Owning component; empty for shared contracts")


class ParameterLocation(str, Enum):
    PATH = "path"
    QUERY = "query"
    HEADER = "header"


class ApiParameter(BaseModel):
    name: str
    location: ParameterLocation
    type: str
    required: bool = True
    description: str = ""


class ApiError(BaseModel):
    status: int
    code: str = Field(description="Machine-readable error code")
    when: str = Field(description="The condition that causes it")


class ApiEndpoint(BaseModel):
    id: str = ""
    method: str = Field(description="HTTP method, or the RPC/operation kind for non-REST styles")
    path: str = Field(description="Route, e.g. /v1/documents/{id}, or the RPC name")
    summary: str
    parameters: list[ApiParameter] = Field(default_factory=list)
    request_contract: str = Field(default="", description="Name of the request DataContract, if any")
    response_contract: str = Field(default="", description="Name of the response DataContract, if any")
    success_status: int = 200
    errors: list[ApiError] = Field(default_factory=list)
    authentication: str = ""
    requirement_ids: list[str] = Field(default_factory=list, description="Software requirement ids served")
    component_id: str = ""


class Column(BaseModel):
    name: str
    type: str
    nullable: bool = False
    primary_key: bool = False
    unique: bool = False
    default: str = ""
    references: str = Field(default="", description="Foreign key target as 'table.column'")


class DatabaseTable(BaseModel):
    """A table, or a container/collection for document stores."""

    id: str = ""
    name: str
    entity: str = Field(default="", description="ORM entity or model class mapped to this table")
    purpose: str = ""
    columns: list[Column] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list, description="e.g. 'idx_owner_created (owner_id, created_at)'")
    component_id: str = ""


class DatabaseSchema(BaseModel):
    tables: list[DatabaseTable] = Field(default_factory=list)
    mermaid: str = Field(default="", description="ER diagram source built from the tables")


class ClassKind(str, Enum):
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"


class RelationKind(str, Enum):
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    COMPOSES = "composes"
    USES = "uses"
    DEPENDS = "depends"


class ClassMember(BaseModel):
    name: str
    type: str


class MethodSpec(BaseModel):
    signature: str = Field(description="e.g. uploadDocument(request: UploadRequest): UploadResponse")
    description: str = ""
    raises: list[str] = Field(default_factory=list, description="Errors or exceptions it can raise")


class ClassRelation(BaseModel):
    target: str = Field(description="Name of the related class or interface")
    kind: RelationKind
    label: str = ""


class ClassSpec(BaseModel):
    """A class, or a service interface the component exposes or depends on."""

    id: str = ""
    name: str
    kind: ClassKind = ClassKind.CLASS
    responsibility: str
    attributes: list[ClassMember] = Field(default_factory=list)
    methods: list[MethodSpec] = Field(default_factory=list)
    relations: list[ClassRelation] = Field(default_factory=list)
    component_id: str = ""


class ClassDiagram(BaseModel):
    component_id: str
    title: str
    mermaid: str


class StepKind(str, Enum):
    CALL = "call"
    RETURN = "return"
    ASYNC = "async"


class SequenceStep(BaseModel):
    source: str
    target: str
    message: str
    kind: StepKind = StepKind.CALL


class SequenceDiagram(BaseModel):
    id: str = ""
    title: str
    participants: list[str] = Field(default_factory=list, description="Components, classes or external actors")
    steps: list[SequenceStep] = Field(default_factory=list, description="Ordered; include the failure path")
    mermaid: str = ""
    requirement_ids: list[str] = Field(default_factory=list)
    component_id: str = ""


class UiScreen(BaseModel):
    """A screen or route of the web client."""

    id: str = ""
    name: str
    route: str = Field(description="URL route, e.g. /documents/:id")
    purpose: str
    ui_components: list[str] = Field(default_factory=list, description="Components or widgets on the screen")
    api_calls: list[str] = Field(default_factory=list, description="Server APIs it calls, exactly 'METHOD /path'")
    states: list[str] = Field(default_factory=list, description="e.g. loading, empty, error, success")
    validations: list[str] = Field(default_factory=list, description="Form and input validation rules")
    requirement_ids: list[str] = Field(default_factory=list, description="Software requirement ids served")
    component_id: str = ""


class ErrorHandlingRule(BaseModel):
    id: str = ""
    scenario: str = Field(description="e.g. downstream timeout, validation failure, duplicate request")
    error_code: str = ""
    handling: str = Field(description="What the component does, e.g. retry with backoff, return 422, dead-letter")
    retry: str = Field(default="", description="Retry policy, timeout, circuit breaker")
    logging: str = Field(default="", description="What is logged or alerted")
    component_id: str = ""


class LldElementSet(BaseModel):
    """Detailed design derived for ONE architecture component."""

    data_contracts: list[DataContract] = Field(default_factory=list)
    api_specifications: list[ApiEndpoint] = Field(default_factory=list)
    tables: list[DatabaseTable] = Field(default_factory=list)
    classes: list[ClassSpec] = Field(default_factory=list)
    sequence_diagrams: list[SequenceDiagram] = Field(default_factory=list)
    error_handling: list[ErrorHandlingRule] = Field(default_factory=list)
    ui_screens: list[UiScreen] = Field(default_factory=list, description="Only for the web client component")


class LldDocument(BaseModel):
    title: str
    overview: str
    conventions: list[str] = Field(default_factory=list)
    data_contracts: list[DataContract] = Field(default_factory=list)
    api_specifications: list[ApiEndpoint] = Field(default_factory=list)
    database_schema: DatabaseSchema = Field(default_factory=DatabaseSchema)
    classes: list[ClassSpec] = Field(default_factory=list)
    class_diagrams: list[ClassDiagram] = Field(default_factory=list)
    sequence_diagrams: list[SequenceDiagram] = Field(default_factory=list)
    error_handling: list[ErrorHandlingRule] = Field(default_factory=list)
    ui_screens: list[UiScreen] = Field(default_factory=list)
