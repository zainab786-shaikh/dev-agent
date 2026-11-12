import json

import pytest

from profile import ProfileWorkflow, load_profile, match_option
from profile.catalog import CLIENT_OPTIONS, SERVER_OPTIONS
from stubs import ScriptedInteraction, StubJudge


class PickJudge(StubJudge):
    """Recommends a fixed option name when the topic has it, else the last option."""

    def __init__(self, picks):
        super().__init__()
        self.picks = picks

    def judge(self, stage, background, proposal):
        names = {o.name for o in proposal.options}
        pick = next((p for p in self.picks if p in names), proposal.options[-1].name)
        self.calls += 1
        from models import DecisionJudgement
        return DecisionJudgement(recommended_option=pick, rationale="best fit")


def _run(tmp_path, answers=None, confirms=None, existing=None, judge=None, **presets):
    io = ScriptedInteraction(answers=answers, confirms=confirms)
    workflow = ProfileWorkflow(io, tmp_path, judge or PickJudge(["Angular", "Node.js with TypeScript (NestJS)", "Prisma", "PostgreSQL"]))
    return workflow.run(presets=presets, existing=existing), io


def test_options_match_by_name_or_unique_prefix():
    assert match_option(SERVER_OPTIONS, "node").name == "Node.js with TypeScript (NestJS)"
    assert match_option(SERVER_OPTIONS, "PYTHON").name == "Python (FastAPI)"
    assert match_option(CLIENT_OPTIONS, "react").name == "React"
    with pytest.raises(ValueError, match="choose from"):
        match_option(SERVER_OPTIONS, "ruby")


def test_presets_skip_the_questions_and_the_orm_follows_the_server(tmp_path):
    (profile, path), io = _run(tmp_path, client="angular", server="java", database="postgres")

    assert (profile.client, profile.server, profile.orm, profile.database) == (
        "Angular", "Java (Spring Boot)", "Hibernate (Spring Data JPA)", "PostgreSQL")
    assert io.asked == []  # nothing was asked
    assert [d.id for d in profile.decisions] == ["PRF-1", "PRF-2", "PRF-3", "PRF-4", "PRF-5"]
    assert {d.stage for d in profile.decisions} == {"profile"}
    assert profile.decisions[3].context.endswith("(the only option for this stack)")  # Hibernate is the only Java ORM
    assert load_profile(tmp_path)[0].summary() == profile.summary()


def test_choices_show_the_options_the_judge_pick_and_ask_the_user(tmp_path):
    (profile, path), io = _run(tmp_path, answers=["", "", "", "2"])  # accept 3, pick option 2 for the database

    assert (profile.client, profile.server, profile.orm, profile.database) == (
        "Angular", "Node.js with TypeScript (NestJS)", "Prisma", "MySQL")
    first = io.asked[0]
    assert "Angular (recommended)" in first and "React" in first and "Judge: Angular" in first
    assert [d.outcome.value for d in profile.decisions] == [
        "preset", "accepted_recommendation", "accepted_recommendation", "accepted_recommendation", "chose_other_option"]

    notes = path.with_name(path.stem + ".notes.md").read_text()
    assert "| Angular |" in notes and "| React |" in notes and "**Decision:** MySQL" in notes
    assert json.loads(path.read_text())["profile"]["database"] == "MySQL"


def test_only_listed_options_are_accepted(tmp_path):
    (profile, _), io = _run(tmp_path, answers=["Svelte", "", "", "", ""])  # a made-up client is refused, then asked again
    assert profile.client == "Angular"
    assert any("Only the listed options" in line for line in io.shown)


def test_an_existing_profile_can_be_kept_or_replaced(tmp_path):
    (first, path), _ = _run(tmp_path, client="react", server="python", database="mysql")

    (kept, kept_path), io = _run(tmp_path, existing=(first, path))  # the user keeps it (confirm defaults to yes)
    assert (kept, kept_path) == (first, path) and io.asked == []

    (changed, _), _ = _run(tmp_path, confirms=[False], existing=(first, path), client="angular", server="python", database="mysql")
    assert changed.client == "Angular"
