"""Schemas for the testing artifacts. Class names avoid a 'Test' prefix so pytest never tries to collect them."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from ...prd.models import Priority


class QaLevelPlan(BaseModel):
    name: str = Field(description="e.g. unit, integration, system, end-to-end, UAT, performance, security")
    purpose: str
    scope: str = ""
    tools: list[str] = Field(default_factory=list)
    entry_criteria: list[str] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)


class QaStrategy(BaseModel):
    """The test strategy: how the product is verified."""

    objectives: list[str] = Field(default_factory=list)
    scope_in: list[str] = Field(default_factory=list)
    scope_out: list[str] = Field(default_factory=list)
    levels: list[QaLevelPlan] = Field(default_factory=list)
    environments: list[str] = Field(default_factory=list)
    test_data: str = ""
    automation_approach: str = ""
    performance_approach: str = ""
    security_approach: str = ""
    defect_management: list[str] = Field(default_factory=list, description="Severity levels, triage, exit rules")
    risks: list[str] = Field(default_factory=list)


class CaseLevel(str, Enum):
    UNIT = "unit"
    INTEGRATION = "integration"
    SYSTEM = "system"
    END_TO_END = "end_to_end"


class CaseType(str, Enum):
    FUNCTIONAL = "functional"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    REGRESSION = "regression"


class QaCase(BaseModel):
    id: str = ""
    title: str
    level: CaseLevel
    type: CaseType = CaseType.FUNCTIONAL
    priority: Priority = Priority.MUST
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    expected_result: str = ""
    apis: list[str] = Field(default_factory=list, description="APIs exercised, exactly as 'METHOD /path' from the list")
    code_paths: list[str] = Field(default_factory=list, description="Files from the provided list that this case verifies")
    automated: bool = True
    requirement_ids: list[str] = Field(default_factory=list, description="Set by the system")
    api_ids: list[str] = Field(default_factory=list, description="Set by the system")
    component_ids: list[str] = Field(default_factory=list, description="Set by the system")


class UatScenario(BaseModel):
    id: str = ""
    title: str
    persona: str = ""
    given: list[str] = Field(default_factory=list)
    when: list[str] = Field(default_factory=list)
    then: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    prd_requirement_ids: list[str] = Field(default_factory=list, description="Product requirement ids from the list")
    requirement_ids: list[str] = Field(default_factory=list, description="Set by the system")


class PerformancePlan(BaseModel):
    id: str = ""
    title: str
    scenario: str = Field(description="What users or systems do during the test")
    load_profile: str = Field(description="Users or requests, ramp-up and duration, e.g. 10,000 users over 10 min")
    metric: str = Field(description="e.g. p95 response time, throughput, error rate")
    threshold: str = Field(description="Pass criterion taken from the requirement target")
    tool: str = ""
    environment: str = ""
    data_volume: str = ""
    requirement_ids: list[str] = Field(default_factory=list, description="Set by the system")


class SecurityCase(BaseModel):
    id: str = ""
    title: str
    abuse_case: str = Field(default="", description="Title of the PRD abuse case it tests, if any")
    owasp_category: str = ""
    steps: list[str] = Field(default_factory=list)
    expected_secure_behavior: str = ""
    controls_verified: list[str] = Field(default_factory=list, description="Security control ids from the list")
    tool: str = ""
    requirement_ids: list[str] = Field(default_factory=list, description="Set by the system")
    abuse_case_id: str = Field(default="", description="Set by the system")


class QaElementSet(BaseModel):
    """Tests derived for ONE software requirement."""

    cases: list[QaCase] = Field(default_factory=list)
    uat_scenarios: list[UatScenario] = Field(default_factory=list)
    performance_plans: list[PerformancePlan] = Field(default_factory=list)
    security_cases: list[SecurityCase] = Field(default_factory=list)


class StaticFinding(BaseModel):
    path: str
    component_id: str = ""
    line: int = 0
    rule: str
    severity: str
    detail: str


class CoverageEntry(BaseModel):
    id: str
    title: str = ""
    case_ids: list[str] = Field(default_factory=list)


class SecurityReport(BaseModel):
    scope: str = ""
    static_findings: list[StaticFinding] = Field(default_factory=list)
    abuse_case_coverage: list[CoverageEntry] = Field(default_factory=list)
    control_coverage: list[CoverageEntry] = Field(default_factory=list)
    uncovered: list[str] = Field(default_factory=list)


class RequirementCoverage(BaseModel):
    requirement_id: str
    cases: list[str] = Field(default_factory=list)
    uat: list[str] = Field(default_factory=list)
    performance: list[str] = Field(default_factory=list)
    security: list[str] = Field(default_factory=list)


class QaDocument(BaseModel):
    title: str
    overview: str
    strategy: QaStrategy = Field(default_factory=QaStrategy)
    cases: list[QaCase] = Field(default_factory=list)
    uat_scenarios: list[UatScenario] = Field(default_factory=list)
    performance_plans: list[PerformancePlan] = Field(default_factory=list)
    security_cases: list[SecurityCase] = Field(default_factory=list)
    security_report: SecurityReport = Field(default_factory=SecurityReport)
    coverage: list[RequirementCoverage] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
