import json
from pathlib import Path

from architecture.models import (
    ArchitectureComponent, ArchitectureDocument, ComponentDiagram, DesignElement, GlobalDecision,
)
from lld import LldWorkflow
from lld.diagrams import class_mermaid, er_mermaid, sequence_mermaid
from lld.models import (
    ApiEndpoint, ClassKind, ClassRelation, ClassSpec, Column, ContractField, DataContract, DatabaseTable,
    LldAnalysis, LldElementSet, MethodSpec, RelationKind, SequenceDiagram, SequenceStep, StepKind,
)
from review_loop import ArtifactAuthor
from srs.models import SoftwareFunctionalRequirement, SoftwareRequirementsDocument
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def __init__(self):
        self.created, self.updated = [], []

    def analyze(self, *_):
        error = DataContract(name="ErrorResponse", fields=[ContractField(name="code", type="string")])
        return LldAnalysis(
            summary="s", conventions=["REST, /v1 prefix"], shared_contracts=[error],
            decision_proposals=[platform_proposal("API style")],
        )

    def create(self, context):
        self.created.append(context.component.id)
        return self._set(context)

    def update(self, context, existing):
        self.updated.append(context.component.id)
        return self._set(context)

    @staticmethod
    def _set(context):
        name = context.component.name
        return LldElementSet(
            data_contracts=[DataContract(name=f"{name}Request", fields=[ContractField(name="id", type="uuid")])],
            api_specifications=[ApiEndpoint(method="post", path=f"/v1/{name.lower()}", summary="create")],
            tables=[DatabaseTable(name=f"{name}_items", columns=[Column(name="id", type="uuid", primary_key=True)])],
            classes=[ClassSpec(name=f"{name}Service", responsibility="r", kind=ClassKind.INTERFACE)],
            sequence_diagrams=[SequenceDiagram(title="create flow", steps=[SequenceStep(source="Client", target=name, message="POST")])],
        )

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")


def _architecture() -> ArchitectureDocument:
    return ArchitectureDocument(
        title="a", overview="o",
        solution_architecture=[GlobalDecision(topic="Cloud platform", decision="Azure")],
        components=[
            ArchitectureComponent(id="COMP-1", name="Api", responsibility="r", technology="AKS"),
            ArchitectureComponent(id="COMP-2", name="Store", responsibility="r", technology="Cosmos DB"),
        ],
        component_diagram=ComponentDiagram(title="c", mermaid="flowchart LR"),
        design_elements=[DesignElement(id="HLD-1", title="t", description="d", component_ids=["COMP-1"], requirement_ids=["FR-1"])],
    )


def _srs() -> SoftwareRequirementsDocument:
    return SoftwareRequirementsDocument(
        title="t", overview="o",
        functional_requirements=[SoftwareFunctionalRequirement(id="FR-1", title="a", statement="The system shall upload.")],
    )


def test_lld_designs_each_component_and_assembles_with_diagrams_and_traceability(tmp_path):
    author = StubAuthor()
    workflow = LldWorkflow(author, ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
    result = workflow.run(_srs(), _architecture())
    saved = json.loads(Path(result["output_path"]).read_text())
    lld = saved["lld"]

    assert author.created == ["COMP-1", "COMP-2"]
    assert [c["name"] for c in lld["data_contracts"]] == ["ErrorResponse", "ApiRequest", "StoreRequest"]
    assert [c["id"] for c in lld["data_contracts"]] == ["CON-1", "CON-2", "CON-3"]
    assert [(a["id"], a["component_id"], a["requirement_ids"]) for a in lld["api_specifications"]] == [
        ("API-1", "COMP-1", ["FR-1"]), ("API-2", "COMP-2", []),
    ]
    assert [t["id"] for t in lld["database_schema"]["tables"]] == ["TBL-1", "TBL-2"]
    assert "erDiagram" in lld["database_schema"]["mermaid"]
    assert {d["component_id"] for d in lld["class_diagrams"]} == {"COMP-1", "COMP-2"}
    assert lld["sequence_diagrams"][0]["mermaid"].startswith("sequenceDiagram")
    assert saved["decisions"][0]["topic"] == "API style"


def test_unchanged_components_are_reused_when_the_lld_is_updated(tmp_path):
    from existing import load_existing
    from lld.models import LldDocument

    def run(architecture, existing=None):
        author = StubAuthor()
        wf = LldWorkflow(author, ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
        return wf.run(_srs(), architecture, existing), author

    run(_architecture())
    existing = load_existing(tmp_path, "lld", LldDocument, LldAnalysis)
    changed = _architecture()
    changed.design_elements.append(
        DesignElement(id="HLD-2", title="t2", description="d", component_ids=["COMP-2"], requirement_ids=["FR-1"])
    )

    result, author = run(changed, existing)
    saved = json.loads(Path(result["output_path"]).read_text())

    assert author.created == [] and author.updated == ["COMP-2"]
    assert {i["source_id"]: i["action"] for i in saved["items"]} == {"COMP-1": "reused", "COMP-2": "updated"}
    assert [a["id"] for a in saved["lld"]["api_specifications"]] == ["API-1", "API-2"]  # ids stay stable


def test_diagram_sources():
    seq = SequenceDiagram(
        title="t", participants=["Client"],
        steps=[
            SequenceStep(source="Client", target="Doc Service", message="POST /v1/docs; body"),
            SequenceStep(source="Doc Service", target="Client", message="201", kind=StepKind.RETURN),
        ],
    )
    text = sequence_mermaid(seq)
    assert "participant Doc_Service as Doc Service" in text
    assert "Client->>Doc_Service: POST /v1/docs, body" in text and "Doc_Service-->>Client: 201" in text

    classes = [
        ClassSpec(name="DocService", kind=ClassKind.INTERFACE, responsibility="r",
                  methods=[MethodSpec(signature="upload(req: UploadRequest): List<Doc>")]),
        ClassSpec(name="DocServiceImpl", responsibility="r",
                  relations=[ClassRelation(target="DocService", kind=RelationKind.IMPLEMENTS)]),
    ]
    text = class_mermaid(classes)
    assert "<<interface>>" in text and "+upload(req: UploadRequest): List~Doc~" in text
    assert "DocService <|.. DocServiceImpl" in text

    tables = [
        DatabaseTable(name="customers", columns=[Column(name="id", type="uuid", primary_key=True)]),
        DatabaseTable(name="orders", columns=[
            Column(name="id", type="uuid", primary_key=True),
            Column(name="customer_id", type="varchar(36)", references="customers.id"),
        ]),
    ]
    text = er_mermaid(tables)
    assert "uuid id PK" in text and "varchar_36_ customer_id FK" in text
    assert 'customers ||--o{ orders : "customer_id"' in text


def _lld_context(tier, **extra):
    from lld.models import LldContext

    component = ArchitectureComponent(id="COMP-9", name="X", responsibility="r", tier=tier)
    return LldContext(component=component, analysis=LldAnalysis(summary="s"), **extra)


def test_cross_tier_checks_for_the_web_client_and_the_api_server():
    from lld.models import UiScreen
    from lld.reviewer_agent import check_lld

    server = ApiEndpoint(method="GET", path="/v1/docs", summary="list")
    client = _lld_context("client", server_apis=[server])
    ok = LldElementSet(ui_screens=[UiScreen(name="List", route="/docs", purpose="p", api_calls=["get /v1/docs"])])
    assert check_lld(client, ok) == []

    bad = LldElementSet(
        ui_screens=[UiScreen(name="List", route="/docs", purpose="p", api_calls=["GET /v1/ghost"])],
        api_specifications=[ApiEndpoint(method="GET", path="/x", summary="s")],
    )
    issues = {f.issue for f in check_lld(client, bad)}
    assert "Calls unknown server API 'GET /v1/ghost'" in issues
    assert "The web client defines endpoints or tables" in issues

    api = _lld_context("api")
    undefined = LldElementSet(api_specifications=[ApiEndpoint(method="POST", path="/v1/docs", summary="s", request_contract="Nope")])
    assert {f.issue for f in check_lld(api, undefined)} == {"Contract 'Nope' is not defined"}
    assert {f.issue for f in check_lld(api, LldElementSet(ui_screens=[UiScreen(name="S", route="/", purpose="p")]))} == {
        "Only the web client has screens"}


def test_tiers_are_designed_data_then_api_then_client_and_each_sees_what_it_depends_on(tmp_path):
    architecture = ArchitectureDocument(
        title="a", overview="o", component_diagram=ComponentDiagram(title="c", mermaid="flowchart LR"),
        components=[
            ArchitectureComponent(id="COMP-1", name="Web", responsibility="r", tier="client"),
            ArchitectureComponent(id="COMP-2", name="Api", responsibility="r", tier="api"),
            ArchitectureComponent(id="COMP-3", name="Db", responsibility="r", tier="data"),
        ],
    )
    seen = {}

    class TierAuthor(StubAuthor):
        def create(self, context):
            self.created.append(context.component.id)
            seen[context.component.id] = ([a.path for a in context.server_apis], [t.name for t in context.data_tables])
            from lld.models import DatabaseTable
            return LldElementSet(
                api_specifications=[ApiEndpoint(method="GET", path="/v1/docs", summary="s")] if context.component.tier == "api" else [],
                tables=[DatabaseTable(name="docs")] if context.component.tier == "data" else [],
            )

    author = TierAuthor()
    workflow = LldWorkflow(author, ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
    workflow.run(_srs(), architecture)

    assert author.created == ["COMP-3", "COMP-2", "COMP-1"]
    assert seen["COMP-1"] == (["/v1/docs"], []) and seen["COMP-2"] == ([], ["docs"]) and seen["COMP-3"] == ([], [])


def test_same_named_contracts_of_different_components_are_kept():
    from lld.assembler import LldAssembler

    def item(field):
        return LldElementSet(data_contracts=[DataContract(name="Item", fields=[ContractField(name=field, type="string")])])

    lld = LldAssembler().assemble(_architecture(), LldAnalysis(summary="s"), {"COMP-1": item("id"), "COMP-2": item("price")})
    assert [(c.component_id, c.fields[0].name) for c in lld.data_contracts] == [("COMP-1", "id"), ("COMP-2", "price")]
    assert [c.fields[0].name for c in LldAssembler.extract(lld, "COMP-2").data_contracts] == ["price"]
