import json
from pathlib import Path

from existing import load_existing
from prd import PrdWorkflow
from prd.models import (
    ProductRequirement, ProductRequirementsAnalysis, ProductRequirementsDocument,
)
from review_loop import ArtifactAuthor
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def __init__(self):
        self.calls = []

    def analyze(self, *_):
        return ProductRequirementsAnalysis(summary="s", decision_proposals=[platform_proposal()])

    def create(self, context):
        self.calls.append("create")
        return ProductRequirementsDocument(
            title="v1", overview="o", functional_requirements=[ProductRequirement(id="FR-1", title="a", description="b")]
        )

    def update(self, context, existing):
        self.calls.append("update")
        return existing.model_copy(update={"title": "v2"})

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves, nothing to revise")


def _run(tmp_path, existing=None):
    author, judge = StubAuthor(), StubJudge()
    io = ScriptedInteraction(answers=[""])
    workflow = PrdWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, judge)
    return workflow.run("an upload feature", existing), author, judge


def test_new_prd_records_decision_and_writes_notes(tmp_path):
    result, author, judge = _run(tmp_path)
    saved = json.loads(Path(result["output_path"]).read_text())

    assert author.calls == ["create"] and judge.calls == 1
    assert saved["mode"] == "new"
    assert saved["decisions"][0]["chosen"] == "Mobile app"
    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "| Web |" in notes and "| Mobile app |" in notes and "The user accepted the judge's recommendation" in notes


def test_existing_prd_is_updated_and_decisions_are_carried_over(tmp_path):
    first, _, _ = _run(tmp_path)
    existing = load_existing(tmp_path, "prd", ProductRequirementsDocument, ProductRequirementsAnalysis)
    assert existing is not None and existing.decisions[0].topic == "Platform"

    result, author, judge = _run(tmp_path, existing)
    saved = json.loads(Path(result["output_path"]).read_text())

    assert author.calls == ["update"]  # not created from scratch
    assert judge.calls == 0  # the topic was decided before, so it is not asked again
    assert saved["mode"] == "update" and saved["prd"]["title"] == "v2"
    assert saved["decisions"][0]["id"] == first["decisions"][0].id


def test_user_can_revisit_a_carried_over_decision(tmp_path):
    _run(tmp_path)
    existing = load_existing(tmp_path, "prd", ProductRequirementsDocument, ProductRequirementsAnalysis)

    author, judge = StubAuthor(), StubJudge()
    io = ScriptedInteraction(answers=["DEC-1", "1"])  # revisit DEC-1, then pick option 1 ("Web")
    result = PrdWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, judge).run("change", existing)
    saved = json.loads(Path(result["output_path"]).read_text())

    assert judge.calls == 1  # judged again with the options evaluated before
    assert [(d["id"], d["chosen"], d["outcome"]) for d in saved["decisions"]] == [("DEC-1", "Web", "chose_other_option")]
    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "chose to revisit 'Platform' (previously 'Mobile app')" in notes


def test_the_application_profile_is_applied_first_and_cannot_be_revisited_per_stage(tmp_path):
    from models import DecisionOutcome, DecisionRecord

    def profile(client):
        return [DecisionRecord(id="PRF-1", stage="profile", topic="Web client framework", chosen=client,
                               outcome=DecisionOutcome.PRESET)]

    def run(existing=None, answers=None, client="React"):
        author, judge = StubAuthor(), StubJudge()
        io = ScriptedInteraction(answers=answers or [""])
        workflow = PrdWorkflow(author, ApprovingReviewer(), io, tmp_path, 5, judge).use_profile(profile(client))
        return workflow.run("req", existing), io

    result, _ = run()
    saved = json.loads(Path(result["output_path"]).read_text())
    assert [(d["stage"], d["chosen"]) for d in saved["decisions"]] == [("profile", "React"), ("prd", "Mobile app")]

    existing = load_existing(tmp_path, "prd", ProductRequirementsDocument, ProductRequirementsAnalysis)
    result, io = run(existing, client="Angular")  # the profile changed in the meantime
    saved = json.loads(Path(result["output_path"]).read_text())
    assert [(d["stage"], d["chosen"]) for d in saved["decisions"]] == [("profile", "Angular"), ("prd", "Mobile app")]
    assert not any("PRF-1" in line for line in io.shown)  # the stage only offers its own decisions for revisiting
    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "Fixed by the application profile" in notes and "Applied the application profile" in notes
