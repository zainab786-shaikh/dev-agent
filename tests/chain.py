"""A small, consistent set of artifacts from PRD to code, for traceability and testing-stage tests."""
from architecture.models import (
    ArchitectureComponent, ArchitectureDocument, ComponentDiagram, DesignElement, SecurityCategory, SecurityControl,
)
from dev.models import DevDocument, SourceFile
from lld.models import ApiEndpoint, LldDocument
from prd.models import AbuseCase, ProductRequirement, ProductRequirementsDocument, UserStory
from srs.models import (
    QualityCategory, SoftwareFunctionalRequirement, SoftwareNonFunctionalRequirement, SoftwareRequirementsDocument,
)
from sysrs.models import ContextDiagram, SystemRequirement, SystemRequirementsDocument


def prd() -> ProductRequirementsDocument:
    return ProductRequirementsDocument(
        title="Docs", overview="o",
        functional_requirements=[ProductRequirement(id="FR-1", title="Upload documents", description="d")],
        user_stories=[UserStory(id="US-1", persona="Customer", goal="upload", benefit="share", requirement_ids=["FR-1"])],
        abuse_cases=[AbuseCase(title="Malware upload", description="d")],
    )


def sysrs() -> SystemRequirementsDocument:
    return SystemRequirementsDocument(
        title="s", overview="o", context_diagram=ContextDiagram(title="c", mermaid="flowchart LR"),
        system_requirements=[SystemRequirement(id="SR-1", title="Store upload", description="d", prd_requirement_ids=["FR-1"])],
    )


def srs() -> SoftwareRequirementsDocument:
    return SoftwareRequirementsDocument(
        title="t", overview="o",
        functional_requirements=[
            SoftwareFunctionalRequirement(id="FR-1", title="Accept upload", statement="The system shall accept uploads.",
                                          source_ids=["SR-1", "FR-1"]),
        ],
        non_functional_requirements=[
            SoftwareNonFunctionalRequirement(id="NFR-1", category=QualityCategory.AVAILABILITY, statement="s",
                                             metric="availability", target="99.95%", source_ids=["confirmed-quality-target"]),
        ],
    )


def architecture() -> ArchitectureDocument:
    from architecture.models import SecurityArchitecture

    return ArchitectureDocument(
        title="a", overview="o",
        components=[ArchitectureComponent(id="COMP-1", name="Api", responsibility="r", technology="AKS")],
        component_diagram=ComponentDiagram(title="c", mermaid="flowchart LR"),
        design_elements=[DesignElement(id="HLD-1", title="Upload handler", description="d", component_ids=["COMP-1"],
                                       requirement_ids=["FR-1"])],
        security_architecture=SecurityArchitecture(controls=[
            SecurityControl(id="SEC-1", title="TLS", category=SecurityCategory.ENCRYPTION_IN_TRANSIT, description="d",
                            component_ids=["COMP-1"], requirement_ids=["FR-1"]),
        ]),
    )


def lld() -> LldDocument:
    return LldDocument(
        title="l", overview="o",
        api_specifications=[ApiEndpoint(id="API-1", method="POST", path="/v1/documents", summary="upload",
                                        requirement_ids=["FR-1"], component_id="COMP-1")],
    )


def dev(source="def upload():\n    return 1\n") -> DevDocument:
    return DevDocument(
        title="d", overview="o",
        source_files=[SourceFile(path="app/main.py", content=source, component_id="COMP-1")],
        test_files=[SourceFile(path="tests/test_main.py", content="def test_x():\n    assert True\n", component_id="COMP-1")],
    )
