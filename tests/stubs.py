"""Stubs shared by the workflow tests (no LLM involved)."""
from interaction import UserInteraction
from models import DecisionJudgement, DecisionOption, DecisionProposal, ReviewResult
from review_loop import ArtifactReviewer


class ScriptedInteraction(UserInteraction):
    """Answers questions from a script; blank answer / yes when the script runs out."""

    def __init__(self, answers=None, confirms=None):
        self.shown, self.asked = [], []
        self._answers, self._confirms = list(answers or []), list(confirms or [])

    def show(self, text):
        self.shown.append(text)

    def ask(self, prompt):
        self.asked.append(prompt)
        return self._answers.pop(0) if self._answers else ""

    def confirm(self, prompt):
        return self._confirms.pop(0) if self._confirms else True


class StubJudge:
    """Recommends the last option of every proposal."""

    def __init__(self):
        self.calls = 0

    def judge(self, stage, background, proposal):
        self.calls += 1
        return DecisionJudgement(recommended_option=proposal.options[-1].name, rationale="best fit")


def platform_proposal(topic="Platform") -> DecisionProposal:
    return DecisionProposal(
        topic=topic,
        context="Where users reach the product",
        options=[
            DecisionOption(name="Web", description="Browser", pros=["no install"], cons=["offline"]),
            DecisionOption(name="Mobile app", description="Native", pros=["camera"], cons=["two stores"]),
        ],
    )


class ApprovingReviewer(ArtifactReviewer):
    def review(self, context, artifact):
        return ReviewResult(approved=True, summary="ok")
