import json
from pathlib import Path

from artifact_store import latest_artifact_file, load_prd
from existing import load_existing
from prd.models import ProductRequirement, ProductRequirementsDocument
from review_loop import ArtifactAuthor
from sysrs import SysrsWorkflow
from sysrs.models import (
    SystemComponent, SystemInteraction, SystemKind, SystemRequirement, SystemRequirementSet,
    SystemRequirementsAnalysis, SystemRequirementsDocument,
)
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def __init__(self):
        self.created, self.updated = [], []

    def analyze(self, *_):
        systems = [
            SystemComponent(id="SYS-1", name="Mobile App", kind=SystemKind.INTERNAL, responsibility="r"),
            SystemComponent(id="SYS-2", name="Blob Storage", kind=SystemKind.EXTERNAL, responsibility="r"),
        ]
        interactions = [SystemInteraction(id="INT-1", source="SYS-1", target="SYS-2", description="uploads")]
        return SystemRequirementsAnalysis(
            summary="s", systems=systems, interactions=interactions, decision_proposals=[platform_proposal("Integration style")]
        )

    def create(self, context):
        self.created.append(context.prd_requirement.id)
        return self._set(context)

    def update(self, context, existing):
        self.updated.append(context.prd_requirement.id)
        return self._set(context)

    @staticmethod
    def _set(context):
        req = SystemRequirement(id="SR-9", title=f"handle {context.prd_requirement.id}", description="d")
        return SystemRequirementSet(system_requirements=[req])

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")


def _prd(*ids, description="b") -> ProductRequirementsDocument:
    return ProductRequirementsDocument(
        title="p", overview="o",
        functional_requirements=[ProductRequirement(id=i, title=i, description=description) for i in ids],
    )


def _run(tmp_path, prd, existing=None):
    author, judge = StubAuthor(), StubJudge()
    workflow = SysrsWorkflow(author, ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, judge)
    return workflow.run(prd, existing), author


def _saved(result):
    return json.loads(Path(result["output_path"]).read_text())


def test_new_sysrs_has_one_set_per_requirement_traced_and_diagrammed(tmp_path):
    result, author = _run(tmp_path, _prd("FR-1", "FR-2", "FR-3"))
    saved = _saved(result)
    requirements = saved["sysrs"]["system_requirements"]

    assert author.created == ["FR-1", "FR-2", "FR-3"]
    assert [r["id"] for r in requirements] == ["SR-1", "SR-2", "SR-3"]
    assert [r["prd_requirement_ids"] for r in requirements] == [["FR-1"], ["FR-2"], ["FR-3"]]
    assert "SYS_1 -->" in saved["sysrs"]["context_diagram"]["mermaid"]
    assert [i["action"] for i in saved["items"]] == ["created"] * 3


def test_update_reuses_unchanged_updates_changed_creates_new_and_drops_removed(tmp_path):
    first, _ = _run(tmp_path, _prd("FR-1", "FR-2", "FR-3"))
    existing = load_existing(tmp_path, "sysrs", SystemRequirementsDocument, SystemRequirementsAnalysis)

    # FR-1 unchanged, FR-2 changed, FR-3 removed, FR-4 new
    prd = ProductRequirementsDocument(
        title="p", overview="o",
        functional_requirements=[
            ProductRequirement(id="FR-1", title="FR-1", description="b"),
            ProductRequirement(id="FR-2", title="FR-2", description="changed"),
            ProductRequirement(id="FR-4", title="FR-4", description="b"),
        ],
    )
    result, author = _run(tmp_path, prd, existing)
    saved = _saved(result)

    assert author.created == ["FR-4"] and author.updated == ["FR-2"]
    assert {i["source_id"]: i["action"] for i in saved["items"]} == {"FR-1": "reused", "FR-2": "updated", "FR-4": "created"}
    by_source = {r["prd_requirement_ids"][0]: r["id"] for r in saved["sysrs"]["system_requirements"]}
    assert by_source == {"FR-1": "SR-1", "FR-2": "SR-2", "FR-4": "SR-4"}  # stable ids; SR-3 is not reused

    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "| FR-3 | removed |" in notes and "| FR-1 | reused |" in notes and "Carried over" in notes


def test_load_latest_prd(tmp_path):
    for name in ("prd_20260101_000000.json", "prd_20260102_000000.json"):
        (tmp_path / name).write_text(json.dumps({"prd": _prd("FR-1").model_dump(mode="json")}), encoding="utf-8")
    assert latest_artifact_file(tmp_path, "prd").name == "prd_20260102_000000.json"
    assert load_prd(latest_artifact_file(tmp_path, "prd")).title == "p"
