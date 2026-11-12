import json
from pathlib import Path

from architecture import ArchitectureWorkflow
from architecture.models import (
    ArchitectureComponent, ArchitectureDecisionRecord, ArchitectureElementSet, ArchitectureLandscape,
    ArchitectureAnalysis, ComponentInteraction, DesignElement, SecurityCategory, SecurityControl,
)
from models import DecisionOption
from review_loop import ArtifactAuthor
from srs.models import (
    InterfaceType, QualityCategory, SoftwareFunctionalRequirement, SoftwareInterfaceRequirement,
    SoftwareNonFunctionalRequirement, SoftwareRequirementsDocument,
)
from sysrs.models import ContextDiagram, SystemRequirementsDocument
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def __init__(self):
        self.created, self.updated, self.update_notes = [], [], []

    def analyze(self, *_):
        return ArchitectureAnalysis(
            summary="s", decision_proposals=[platform_proposal("Security model"), platform_proposal("Cloud platform")]
        )

    def design_landscape(self, *_):
        components = [
            ArchitectureComponent(id="COMP-1", name="API", responsibility="r", technology="AKS"),
            ArchitectureComponent(id="COMP-2", name="Store", responsibility="r", technology="Cosmos DB"),
        ]
        interactions = [ComponentInteraction(id="CI-1", source="COMP-1", target="COMP-2", description="reads")]
        return ArchitectureLandscape(components=components, interactions=interactions)

    def create(self, context):
        self.created.append(context.requirement.id)
        return self._set(context)

    def update(self, context, existing):
        self.updated.append(context.requirement.id)
        self.update_notes += context.clarifications
        return self._set(context)

    @staticmethod
    def _set(context):
        options = [DecisionOption(name="AKS", pros=["scales"], cons=["ops"]), DecisionOption(name="VMs")]
        return ArchitectureElementSet(
            design_elements=[DesignElement(id="HLD-1", title=f"design {context.requirement.id}", description="d")],
            decisions=[
                ArchitectureDecisionRecord(
                    id="ADR-1", title="Use AKS", context="c", options=options, decision="AKS", rationale="scales"
                )
            ],
            security_controls=[
                SecurityControl(id="SEC-1", title="TLS", category=SecurityCategory.ENCRYPTION_IN_TRANSIT, description="d")
            ],
        )

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")


def _srs() -> SoftwareRequirementsDocument:
    return SoftwareRequirementsDocument(
        title="t", overview="o",
        functional_requirements=[SoftwareFunctionalRequirement(id="FR-1", title="a", statement="The system shall upload.")],
        non_functional_requirements=[
            SoftwareNonFunctionalRequirement(
                id="NFR-1", category=QualityCategory.SCALABILITY, statement="s", metric="users", target="10 million"
            )
        ],
        interface_requirements=[
            SoftwareInterfaceRequirement(
                id="IFR-1", interface_type=InterfaceType.API, name="n", statement="s", counterpart="c"
            )
        ],
    )


def _sysrs() -> SystemRequirementsDocument:
    return SystemRequirementsDocument(title="s", overview="o", context_diagram=ContextDiagram(title="c", mermaid="flowchart LR"))


def _run(tmp_path, answers, confirms=None):
    author = StubAuthor()
    io = ScriptedInteraction(answers=answers, confirms=confirms)
    workflow = ArchitectureWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, StubJudge())
    result = workflow.run(_srs(), _sysrs())
    return result, author


def _saved(result):
    return json.loads(Path(result["output_path"]).read_text())


def test_decisions_are_verified_then_design_is_assembled(tmp_path):
    result, author = _run(tmp_path, answers=["", ""])  # accept both recommended decisions
    arch = _saved(result)["architecture"]

    assert [d["topic"] for d in arch["solution_architecture"]] == ["Security model", "Cloud platform"]
    assert arch["security_architecture"]["model"] == "Mobile app"
    assert arch["deployment_architecture"]["platform"] == "Mobile app"
    assert [d["id"] for d in arch["design_elements"]] == ["HLD-1", "HLD-2", "HLD-3"]
    assert len(arch["decisions"]) == 1 and arch["decisions"][0]["requirement_ids"] == ["FR-1", "NFR-1", "IFR-1"]
    assert [o["name"] for o in arch["decisions"][0]["options"]] == ["AKS", "VMs"]
    assert "COMP_1 -->" in arch["component_diagram"]["mermaid"]


def test_user_can_send_an_adr_back_and_the_affected_items_are_redone(tmp_path):
    # asks: two decisions, then which ADR to revisit, then what is wrong with it
    # confirms: analysis, "accept ADRs?" -> no, then yes after the redo
    result, author = _run(
        tmp_path, answers=["", "", "ADR-1", "too expensive"], confirms=[True, False, True]
    )
    saved = _saved(result)

    assert author.created == ["FR-1", "NFR-1", "IFR-1"]
    assert author.updated == ["FR-1", "NFR-1", "IFR-1"]  # the ADR served all three requirements
    assert any("too expensive" in note for note in author.update_notes)
    assert {i["action"] for i in saved["items"]} == {"updated"}

    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "revisit ADR-1" in notes and "Chosen by the agent while designing, accepted by the user" in notes


class PerRequirementAdrAuthor(StubAuthor):
    @staticmethod
    def _set(context):
        element_set = StubAuthor._set(context)
        adr = element_set.decisions[0].model_copy(update={"title": f"Use AKS for {context.requirement.id}"})
        return element_set.model_copy(update={"decisions": [adr]})


def test_only_the_flagged_adr_items_are_redone_and_others_keep_their_real_action(tmp_path):
    author = PerRequirementAdrAuthor()
    io = ScriptedInteraction(answers=["", "", "ADR-1", "cheaper"], confirms=[True, False, True])
    workflow = ArchitectureWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, StubJudge())
    saved = _saved(workflow.run(_srs(), _sysrs()))

    assert author.updated == ["FR-1"]
    reports = {i["source_id"]: (i["action"], i["iterations"]) for i in saved["items"]}
    assert reports == {"FR-1": ("updated", 1), "NFR-1": ("created", 1), "IFR-1": ("created", 1)}


class TieredAuthor(StubAuthor):
    """Returns a landscape missing the data tier at first, as a weak model might."""

    def __init__(self, good_after):
        super().__init__()
        self.good_after, self.landscape_calls, self.problems = good_after, 0, []

    def design_landscape(self, *args):
        self.landscape_calls += 1
        self.problems.append(args[5] if len(args) > 5 else None)
        components = [
            ArchitectureComponent(id="COMP-1", name="Web", responsibility="r", technology="React", tier="client"),
            ArchitectureComponent(id="COMP-2", name="Api", responsibility="r", technology="FastAPI", tier="api"),
        ]
        interactions = [ComponentInteraction(id="CI-1", source="COMP-1", target="COMP-2", description="calls")]
        if self.landscape_calls >= self.good_after:
            components.append(ArchitectureComponent(id="COMP-3", name="Db", responsibility="r", technology="PostgreSQL", tier="data"))
            interactions.append(ComponentInteraction(id="CI-2", source="COMP-2", target="COMP-3", description="reads"))
        return ArchitectureLandscape(components=components, interactions=interactions)


def test_the_three_tiers_are_enforced_with_one_retry_that_names_the_problem(tmp_path):
    author = TieredAuthor(good_after=2)
    io = ScriptedInteraction(answers=["", ""])
    ArchitectureWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, StubJudge()).run(_srs(), _sysrs())

    assert author.landscape_calls == 2
    assert author.problems[1] == ["there is no component in the 'data' tier"]
    assert not any("warning" in line for line in io.shown)


def test_a_landscape_that_stays_wrong_is_shown_to_the_user_as_a_warning(tmp_path):
    author = TieredAuthor(good_after=99)
    io = ScriptedInteraction(answers=["", ""])
    result = ArchitectureWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, StubJudge()).run(_srs(), _sysrs())

    assert author.landscape_calls == 2  # one retry only
    assert any("no component in the 'data' tier" in line for line in io.shown)
    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "left for the user to judge" in notes
