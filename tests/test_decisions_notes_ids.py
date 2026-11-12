from pydantic import BaseModel

from decisions import DecisionService
from ids import assign_ids
from models import DecisionJudgement, DecisionOutcome, DecisionRecord
from notes import RunNotes
from stubs import ScriptedInteraction, StubJudge, platform_proposal


def _decide(answer, decided=None, proposals=None):
    io = ScriptedInteraction(answers=[answer])
    service = DecisionService(StubJudge(), io)
    records = service.decide("prd", proposals or [platform_proposal()], "background", decided or [])
    return records, io


def test_enter_accepts_the_recommendation():
    (record,), io = _decide("")
    assert (record.chosen, record.outcome) == ("Mobile app", DecisionOutcome.ACCEPTED_RECOMMENDATION)
    assert "(recommended)" in io.asked[0] and "+ no install" in io.asked[0]


def test_number_picks_another_option():
    (record,), _ = _decide("1")
    assert (record.chosen, record.outcome) == ("Web", DecisionOutcome.CHOSE_OTHER_OPTION)
    assert record.recommended_option == "Mobile app"


def test_free_text_is_a_custom_decision():
    (record,), _ = _decide("Progressive web app")
    assert (record.chosen, record.outcome) == ("Progressive web app", DecisionOutcome.CUSTOM)


def test_decided_topics_and_single_option_proposals_are_skipped():
    decided = [DecisionRecord(id="DEC-1", stage="prd", topic="platform", chosen="Web", outcome=DecisionOutcome.CARRIED_OVER)]
    single = platform_proposal("Sign-in")
    single.options = single.options[:1]
    records, io = _decide("", decided=decided, proposals=[platform_proposal(), single])
    assert records == [] and io.asked == []


def test_new_decision_ids_never_collide_with_kept_ones():
    kept = [DecisionRecord(id="DEC-2", stage="prd", topic="Other", chosen="x", outcome=DecisionOutcome.CARRIED_OVER)]
    (record,), _ = _decide("", decided=kept)
    assert record.id == "DEC-3"


def test_a_judge_pick_that_is_not_an_option_is_flagged():
    class OffListJudge(StubJudge):
        def judge(self, stage, background, proposal):
            return DecisionJudgement(recommended_option="Something else", rationale="because")

    io = ScriptedInteraction(answers=[""])
    (record,) = DecisionService(OffListJudge(), io).decide("prd", [platform_proposal()], "bg", [])
    assert record.chosen == "Web"  # falls back to the first listed option
    assert "not a listed option" in record.recommendation_rationale


def test_notes_list_options_recommendation_and_outcome():
    (record,), _ = _decide("1")
    notes = RunNotes("PRD")
    notes.step("Read the inputs")
    notes.decision(record)
    notes.question("Who?", "Customers")
    notes.item({"source_id": "FR-1", "action": "created", "iterations": 2, "converged": True})
    text = notes.to_markdown()
    for expected in ("| Option | Description | Pros | Cons |", "| Mobile app |", "**Recommended:** Mobile app",
                     "The user chose a different option", "**Decision:** Web", "Customers", "| FR-1 | created | 2 | passed |"):
        assert expected in text


def test_ids_stay_stable_and_are_never_reused():
    class Item(BaseModel):
        id: str = ""
        title: str

    old = [Item(id="SR-1", title="a"), Item(id="SR-3", title="c")]
    new = assign_ids([Item(title="c"), Item(title="new"), Item(title="a")], "SR", old, lambda i: i.title)
    assert [i.id for i in new] == ["SR-3", "SR-4", "SR-1"]
