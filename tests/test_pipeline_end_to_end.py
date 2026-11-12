"""Runs the real authors, reviewers and judge (prompts included) against a canned fake LLM.

Covers every stage from PRD to LLD with the saved files fed forward, then an update pass.
No model server is involved.
"""
import inspect
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from agents.decision_judge import DecisionJudge
from architecture import ArchitectureAuthorAgent, ArchitectureReviewerAgent, ArchitectureWorkflow
from architecture.models import (
    ArchitectureAnalysis, ArchitectureComponent, ArchitectureDecisionRecord, ArchitectureDocument,
    ArchitectureElementSet, ArchitectureLandscape, ComponentInteraction, DesignElement, SecurityCategory,
    SecurityControl,
)
from artifact_store import load_architecture, load_dev, load_lld, load_prd, load_srs, load_sysrs
from dev import DevAuthorAgent, DevReviewerAgent, DevWorkflow
from dev.models import DevAnalysis, DevDocument, DevElementSet, DevScaffold, GitWorkflow, ProjectFileSet, SourceFile
from existing import load_existing
from testing import QaAuthorAgent, QaReviewerAgent, QaWorkflow
from testing.models import (
    CaseLevel, PerformancePlan, QaAnalysis, QaCase, QaDocument, QaElementSet, QaLevelPlan, QaStrategy, SecurityCase, UatScenario,
)
from profile import ApplicationProfile, ProfileWorkflow, load_profile
from traceability import TraceabilityMatrix, refresh
from lld import LldAuthorAgent, LldReviewerAgent, LldWorkflow
from lld.models import (
    ApiEndpoint, ClassSpec, Column, ContractField, DataContract, DatabaseTable, ErrorHandlingRule, LldAnalysis,
    LldDocument, LldElementSet, SequenceDiagram, SequenceStep, UiScreen,
)
from models import DecisionJudgement, DecisionOption, DecisionProposal, ReviewResult
from prd import PrdAuthorAgent, PrdReviewerAgent, PrdWorkflow
from prd.models import (
    AbuseCase, FunctionalScope, NonFunctionalProductRequirement, ProductRequirement, ProductRequirementsAnalysis,
    ProductRequirementsDocument, ProductSubRequirement, UserPersona, UserStory,
)
from srs import SrsAuthorAgent, SrsReviewerAgent, SrsWorkflow
from srs.models import (
    InterfaceType, QualityCategory, QualityTarget, QualityTargetSet, SoftwareFunctionalRequirement, SoftwareInterfaceRequirement,
    SoftwareNonFunctionalRequirement, SoftwareRequirementSet, SoftwareRequirementsAnalysis, SoftwareRequirementsDocument,
    SoftwareSubRequirement,
)
from sysrs import SysrsAuthorAgent, SysrsReviewerAgent, SysrsWorkflow
from sysrs.models import (
    IntegrationRequirement, SystemComponent, SystemInteraction, SystemKind, SystemRequirement,
    SystemRequirementSet, SystemRequirementsAnalysis, SystemRequirementsDocument, SystemUseCase,
)
from stubs import ScriptedInteraction


def _proposal(topic: str) -> DecisionProposal:
    return DecisionProposal(
        topic=topic,
        context=f"{topic} is open",
        options=[
            DecisionOption(name="Option A", pros=["simple"], cons=["limited"]),
            DecisionOption(name="Option B", pros=["scalable"], cons=["complex"]),
        ],
    )


def _lld_for_tier(prompt: str) -> LldElementSet:
    """Each tier gets only what it may contain, as the real LLD reviewer requires."""
    classes = [ClassSpec(name="UploadService", responsibility="handles uploads")]
    if '"tier":"client"' in prompt.split("Other components")[0]:
        screen = UiScreen(name="Upload page", route="/upload", purpose="upload a file", api_calls=["POST /v1/documents"])
        return LldElementSet(classes=classes, ui_screens=[screen])
    if '"tier":"data"' in prompt.split("Other components")[0]:
        table = DatabaseTable(name="documents", entity="Document", columns=[Column(name="id", type="uuid", primary_key=True)])
        return LldElementSet(classes=classes, tables=[table])
    return LldElementSet(
        data_contracts=[DataContract(name="UploadRequest", fields=[ContractField(name="file", type="bytes")])],
        api_specifications=[ApiEndpoint(method="POST", path="/v1/documents", summary="upload", request_contract="UploadRequest")],
        classes=classes,
        sequence_diagrams=[SequenceDiagram(title="Upload", steps=[SequenceStep(source="Client", target="UploadService", message="POST")])],
        error_handling=[ErrorHandlingRule(scenario="storage timeout", handling="retry with backoff")],
    )


RESPONSES = {
    DecisionJudgement: lambda: DecisionJudgement(recommended_option="Option B", rationale="scales better"),
    ReviewResult: lambda: ReviewResult(approved=True, summary="ok"),
    ProductRequirementsAnalysis: lambda: ProductRequirementsAnalysis(
        summary="Customers upload documents",
        users=[UserPersona(name="Customer", description="uploads files")],
        non_functional_requirements=[NonFunctionalProductRequirement(category="availability", description="99.95%")],
        abuse_cases=[AbuseCase(title="Malware upload", description="d", mitigation="scan")],
        decision_proposals=[_proposal("Platform")],
    ),
    ProductRequirementsDocument: lambda: ProductRequirementsDocument(
        title="Document upload", overview="o",
        users=[UserPersona(name="Customer", description="d")],
        functional_scope=FunctionalScope(in_scope=["upload"]),
        functional_requirements=[ProductRequirement(
            id="FR-1", title="Upload documents", description="Customers upload documents",
            acceptance_criteria=["confirmation within 5 seconds"],
            sub_requirements=[ProductSubRequirement(id="FR-1.1", title="Validate type", description="d")],
        )],
        user_stories=[UserStory(id="US-1", persona="Customer", goal="upload", benefit="share", requirement_ids=["FR-1"])],
        non_functional_requirements=[ProductRequirement(id="NFR-1", title="Availability", description="99.95%")],
        abuse_cases=[AbuseCase(title="Malware upload", description="d", mitigation="scan")],
    ),
    SystemRequirementsAnalysis: lambda: SystemRequirementsAnalysis(
        summary="Upload path",
        systems=[
            SystemComponent(id="SYS-1", name="Mobile App", kind=SystemKind.INTERNAL, responsibility="client"),
            SystemComponent(id="SYS-2", name="Blob Storage", kind=SystemKind.EXTERNAL, responsibility="store"),
        ],
        interactions=[SystemInteraction(id="INT-1", source="SYS-1", target="SYS-2", description="uploads document")],
        decision_proposals=[_proposal("Integration style")],
    ),
    SystemRequirementSet: lambda: SystemRequirementSet(
        system_requirements=[SystemRequirement(
            id="SR-1", title="Store uploaded document", description="Mobile App sends the document to Blob Storage",
            system_ids=["SYS-1", "SYS-2"],
        )],
        system_use_cases=[SystemUseCase(id="SUC-1", title="Upload", trigger="user taps upload", systems_involved=["SYS-1"])],
        integration_requirements=[IntegrationRequirement(
            id="IR-1", title="Blob integration", external_system="SYS-2", direction="outbound",
            interface="REST", data_exchanged="document",
        )],
    ),
    SoftwareRequirementsAnalysis: lambda: SoftwareRequirementsAnalysis(
        summary="Software scope", functional_areas=["upload"],
        quality_targets=[QualityTarget(category=QualityCategory.AVAILABILITY, metric="availability", target="99.95%")],
        interfaces=["REST API"], decision_proposals=[_proposal("Availability target")],
    ),
    QualityTargetSet: lambda: QualityTargetSet(
        quality_targets=[QualityTarget(category=QualityCategory.AVAILABILITY, metric="availability", target="99.95%")]
    ),
    SoftwareRequirementSet: lambda: SoftwareRequirementSet(
        functional_requirements=[SoftwareFunctionalRequirement(
            id="FR-1", title="Accept upload", statement="The system shall accept a document upload.",
            sub_requirements=[SoftwareSubRequirement(id="FR-1.1", statement="The system shall validate the file type.")],
        )],
        non_functional_requirements=[SoftwareNonFunctionalRequirement(
            id="NFR-1", category=QualityCategory.PERFORMANCE, statement="s", metric="latency", target="< 2 s",
        )],
        interface_requirements=[SoftwareInterfaceRequirement(
            id="IFR-1", interface_type=InterfaceType.API, name="Upload API", statement="s", counterpart="Mobile App",
        )],
    ),
    ArchitectureAnalysis: lambda: ArchitectureAnalysis(
        summary="Cloud architecture", decision_proposals=[_proposal("Cloud platform"), _proposal("Security model")]
    ),
    ArchitectureLandscape: lambda: ArchitectureLandscape(
        components=[
            ArchitectureComponent(id="COMP-1", name="Document API", responsibility="stores", technology="FastAPI", tier="api"),
            ArchitectureComponent(id="COMP-2", name="Database", responsibility="data", technology="PostgreSQL", tier="data"),
            ArchitectureComponent(id="COMP-3", name="Web Client", responsibility="ui", technology="React", tier="client"),
        ],
        interactions=[
            ComponentInteraction(id="CI-1", source="COMP-3", target="COMP-1", description="calls"),
            ComponentInteraction(id="CI-2", source="COMP-1", target="COMP-2", description="reads and writes"),
        ],
    ),
    ArchitectureElementSet: lambda: ArchitectureElementSet(
        design_elements=[DesignElement(title="Upload handler", description="d", component_ids=["COMP-1"])],
        decisions=[ArchitectureDecisionRecord(
            title="Use AKS", context="scale", decision="AKS", rationale="scales",
            options=[DecisionOption(name="AKS", pros=["scales"]), DecisionOption(name="VMs", cons=["manual"])],
        )],
        security_controls=[SecurityControl(
            title="TLS everywhere", category=SecurityCategory.ENCRYPTION_IN_TRANSIT, description="d", component_ids=["COMP-1"],
        )],
    ),
    LldAnalysis: lambda: LldAnalysis(
        summary="Implementation approach", conventions=["REST under /v1"],
        shared_contracts=[DataContract(name="ErrorResponse", fields=[ContractField(name="code", type="string")])],
        decision_proposals=[_proposal("API style")],
    ),
    LldElementSet: lambda prompt: _lld_for_tier(prompt),
    DevAnalysis: lambda: DevAnalysis(summary="Python service", decision_proposals=[_proposal("Programming language")]),
    DevScaffold: lambda: DevScaffold(
        layout=["one package per component"], git_workflow=GitWorkflow(branching_model="trunk-based")
    ),
    DevElementSet: lambda: DevElementSet(
        source_files=[SourceFile(path="app/main.py", content="def handler():\n    return 'ok'\n")],
        test_files=[SourceFile(path="tests/test_main.py", content="def test_handler():\n    assert True\n")],
        dependencies=["requests"],
    ),
    ProjectFileSet: lambda: ProjectFileSet(
        files=[SourceFile(path="README.md", content="# project\n"), SourceFile(path="requirements.txt", content="requests\n")]
    ),
    QaAnalysis: lambda: QaAnalysis(summary="Verification", decision_proposals=[_proposal("Performance test tool")]),
    QaStrategy: lambda: QaStrategy(
        objectives=["verify every requirement"], levels=[QaLevelPlan(name="unit", purpose="logic")]
    ),
    QaElementSet: lambda: QaElementSet(
        cases=[QaCase(
            title="Upload succeeds", level=CaseLevel.SYSTEM, steps=["POST a file"], expected_result="201",
            apis=["POST /v1/documents"], code_paths=["app/main.py"],
        )],
        uat_scenarios=[UatScenario(
            title="Customer uploads a document", given=["a customer"], when=["uploads"], then=["sees confirmation"],
            prd_requirement_ids=["FR-1"],
        )],
        performance_plans=[PerformancePlan(
            title="Upload load", scenario="s", load_profile="100 users for 10 min", metric="p95", threshold="< 2 s",
        )],
        security_cases=[SecurityCase(
            title="Malware upload is rejected", abuse_case="Malware upload", steps=["upload a test virus"],
            expected_secure_behavior="rejected", controls_verified=["SEC-1"],
        )],
    ),
}


class FakeLLM:
    """Stands in for the chat model: records every prompt and answers with canned structured output."""

    def __init__(self):
        self.calls: list[tuple[str, str]] = []  # (schema name, user prompt)

    def with_structured_output(self, schema, method=None):
        fake = self

        class Bound:
            def invoke(self, messages):
                fake.calls.append((schema.__name__, messages[1].content))
                factory = RESPONSES[schema]
                return factory(messages[1].content) if inspect.signature(factory).parameters else factory()

        return Bound()

    def count(self, schema_name: str, since: int = 0) -> int:
        return sum(1 for name, _ in self.calls[since:] if name == schema_name)

    def prompts(self, schema_name: str, since: int = 0) -> list[str]:
        return [p for name, p in self.calls[since:] if name == schema_name]


def _profile(fake, out: Path) -> ApplicationProfile:
    workflow = ProfileWorkflow(ScriptedInteraction(), out, DecisionJudge(fake))
    profile, _ = workflow.run(presets={"client": "react", "server": "python", "database": "postgres"})
    return profile


def _stages(fake, out: Path, profile: ApplicationProfile):
    io = ScriptedInteraction()

    def make(cls_workflow, author, reviewer, name):
        return cls_workflow(author(fake), reviewer(fake), io, out / name, 5, DecisionJudge(fake)).use_profile(profile.decisions)

    return {
        "prd": make(PrdWorkflow, PrdAuthorAgent, PrdReviewerAgent, "prd"),
        "sysrs": make(SysrsWorkflow, SysrsAuthorAgent, SysrsReviewerAgent, "sysrs"),
        "srs": make(SrsWorkflow, SrsAuthorAgent, SrsReviewerAgent, "srs"),
        "architecture": make(ArchitectureWorkflow, ArchitectureAuthorAgent, ArchitectureReviewerAgent, "architecture"),
        "lld": make(LldWorkflow, LldAuthorAgent, LldReviewerAgent, "lld"),
        "testing": QaWorkflow(
            QaAuthorAgent(fake), QaReviewerAgent(fake), io, out / "testing", 5, DecisionJudge(fake)
        ).use_profile(profile.decisions),
        "dev": DevWorkflow(
            DevAuthorAgent(fake), DevReviewerAgent(fake), io, out / "dev", 5, DecisionJudge(fake),
            project_dir=out / "dev" / "project",
        ).use_profile(profile.decisions),
    }


def _pipeline(fake, out: Path, update: bool) -> dict[str, dict]:
    profile = load_profile(out)[0] if update else _profile(fake, out)
    stages = _stages(fake, out, profile)

    def previous(name, document_cls, analysis_cls):
        return load_existing(out / name, name, document_cls, analysis_cls) if update else None

    results = {}
    results["prd"] = stages["prd"].run(
        "Customers upload documents", previous("prd", ProductRequirementsDocument, ProductRequirementsAnalysis)
    )
    prd = load_prd(Path(results["prd"]["output_path"]))
    refresh(out, "prd")
    results["sysrs"] = stages["sysrs"].run(
        prd, previous("sysrs", SystemRequirementsDocument, SystemRequirementsAnalysis)
    )
    sysrs = load_sysrs(Path(results["sysrs"]["output_path"]))
    refresh(out, "sysrs")
    results["srs"] = stages["srs"].run(
        prd, sysrs, previous("srs", SoftwareRequirementsDocument, SoftwareRequirementsAnalysis)
    )
    srs = load_srs(Path(results["srs"]["output_path"]))
    refresh(out, "srs")
    results["architecture"] = stages["architecture"].run(
        srs, sysrs, previous("architecture", ArchitectureDocument, ArchitectureAnalysis)
    )
    architecture = load_architecture(Path(results["architecture"]["output_path"]))
    refresh(out, "architecture")
    results["lld"] = stages["lld"].run(srs, architecture, previous("lld", LldDocument, LldAnalysis))
    lld = load_lld(Path(results["lld"]["output_path"]))
    refresh(out, "lld")
    results["dev"] = stages["dev"].run(architecture, lld, previous("dev", DevDocument, DevAnalysis))
    dev = load_dev(Path(results["dev"]["output_path"]))
    refresh(out, "dev")
    results["testing"] = stages["testing"].run(prd, srs, architecture, lld, dev, previous("testing", QaDocument, QaAnalysis))
    refresh(out, "testing")
    return results


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")
def test_full_pipeline_creates_then_updates(tmp_path):
    fake = FakeLLM()

    # --- create everything, each stage reading the previous stage's saved file -------------------
    first = _pipeline(fake, tmp_path, update=False)
    for name, result in first.items():
        assert result["converged"] is True, name
        path = Path(result["output_path"])
        assert path.exists() and path.with_name(path.stem + ".notes.md").exists(), name

    # every stage verified its decision with options, judge pick and the user's acceptance
    for name, topic in [("prd", "Platform"), ("sysrs", "Integration style"), ("srs", "Availability target"),
                        ("architecture", "Cloud platform"), ("lld", "API style"),
                        ("dev", "Programming language"),
                        ("testing", "Performance test tool")]:
        own = [d for d in first[name]["decisions"] if d.stage != "profile"]
        assert (own[0].topic, own[0].chosen) == (topic, "Option B"), name
        assert [d.chosen for d in first[name]["decisions"] if d.stage == "profile"][1:] == [
            "React", "Python (FastAPI)", "SQLAlchemy", "PostgreSQL"], name  # the profile reaches every stage

    # the profile appears in the prompts, and each tier is designed in dependency order
    for schema_name in ("ArchitectureElementSet", "LldElementSet", "DevElementSet", "QaElementSet"):
        assert all("Web client framework: React" in p and "ORM: SQLAlchemy" in p for p in fake.prompts(schema_name)), schema_name
    tiers = [re.search(r'Component to design:\n\{[^}]*"tier":"(\w+)"', p).group(1) for p in fake.prompts("LldElementSet")]
    assert tiers == ["data", "api", "client"]
    assert any("This is the web client" in p for p in fake.prompts("DevElementSet"))
    assert any("This is the API server" in p for p in fake.prompts("DevElementSet"))
    client_prompt = next(p for p in fake.prompts("LldElementSet") if "This is the web client" in p)
    assert '"path":"/v1/documents"' in client_prompt.split("Server APIs the web client calls")[1]  # it sees the server APIs

    # confirmed decisions reach the per-item prompts
    assert all("Cloud platform: Option B" in p for p in fake.prompts("ArchitectureElementSet"))
    assert all("API style: Option B" in p for p in fake.prompts("LldElementSet"))

    # traceability and structure across the chain
    sysrs = first["sysrs"]["document"]
    assert [r.prd_requirement_ids for r in sysrs.system_requirements] == [["FR-1"], ["NFR-1"]]
    srs = first["srs"]["document"]
    assert srs.functional_requirements[0].source_ids == ["SR-1", "FR-1"]
    assert srs.non_functional_requirements[0].source_ids == ["confirmed-quality-target"]
    architecture = first["architecture"]["document"]
    assert [d.title for d in architecture.decisions] == ["Use AKS"] and len(architecture.decisions[0].requirement_ids) > 1
    lld = first["lld"]["document"]
    assert {c.component_id for c in lld.class_diagrams} == {"COMP-1", "COMP-2", "COMP-3"}
    assert [s.api_calls for s in lld.ui_screens] == [["POST /v1/documents"]] and lld.database_schema.tables[0].entity == "Document"
    assert lld.database_schema.mermaid.startswith("erDiagram")
    dev = first["dev"]["document"]
    project = tmp_path / "dev" / "project"
    assert [f.path for f in dev.project_files] == ["README.md", "requirements.txt"]
    assert (project / "app/main.py").exists() and (project / "tests/test_main.py").exists() and (project / ".git").exists()
    commits = len(subprocess.run(["git", "log", "--oneline"], cwd=project, capture_output=True, text=True).stdout.splitlines())
    assert commits >= 3  # scaffold, a component commit and its merge

    # --- the living traceability matrix was rebuilt after every step and is consistent ---------------
    matrix = TraceabilityMatrix.model_validate_json((tmp_path / "traceability" / "traceability.json").read_text(encoding="utf-8"))
    steps = ["prd", "sysrs", "srs", "architecture", "lld", "dev", "testing"]
    assert [h.trigger for h in matrix.history] == steps
    assert [h.nodes for h in matrix.history] == sorted(h.nodes for h in matrix.history)  # it only grows as stages are added
    assert matrix.broken_links == [] and matrix.notes == []
    row = next(r for r in matrix.rows if r.root == "prd:FR-1")
    for stage in ("sysrs", "srs", "architecture", "lld", "component", "code", "testing"):
        assert row.reach.get(stage), stage
    assert any(i.startswith("UAT-") for i in row.reach["testing"])
    assert all(c.requirement_ids and c.code_paths and c.api_ids for c in first["testing"]["document"].cases)
    assert (tmp_path / "traceability" / "traceability.md").exists()

    # --- update: same inputs, so per-item stages reuse everything and nothing is created again ---
    mark = len(fake.calls)
    second = _pipeline(fake, tmp_path, update=True)

    assert fake.count("ProductRequirementsDocument", mark) == 1
    assert any("Existing PRD:" in p for p in fake.prompts("ProductRequirementsDocument", mark))
    for schema_name in ("SystemRequirementSet", "SoftwareRequirementSet", "ArchitectureElementSet", "LldElementSet", "DevElementSet", "QaElementSet"):
        assert fake.count(schema_name, mark) == 0, schema_name  # all reused
    for name in ("sysrs", "srs", "architecture", "lld", "dev", "testing"):
        assert {i["action"] for i in second[name]["items"]} == {"reused"}, name
        assert second[name]["decisions"] == first[name]["decisions"]  # carried over, not asked again
    assert fake.count("DecisionJudgement", mark) == 0
    assert len(subprocess.run(["git", "log", "--oneline"], cwd=project, capture_output=True, text=True).stdout.splitlines()) == commits

    # stable ids across versions
    assert [a.id for a in second["lld"]["document"].api_specifications] == [
        a.id for a in first["lld"]["document"].api_specifications
    ]
    assert [r.id for r in second["srs"]["document"].functional_requirements] == [
        r.id for r in first["srs"]["document"].functional_requirements
    ]
