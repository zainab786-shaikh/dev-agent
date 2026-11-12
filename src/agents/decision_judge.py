"""Independent judge that recommends the best option for a decision."""
from __future__ import annotations

from ..models import DecisionJudgement, DecisionProposal
from .base import BaseAgent


class DecisionJudge(BaseAgent):
    @property
    def name(self) -> str:
        return "DecisionJudge"

    @property
    def system_prompt(self) -> str:
        return (
            "You are an impartial senior engineer judging options for a decision. You weigh every option "
            "against the stated inputs and recommend exactly one. Respond only with JSON matching the "
            "given schema."
        )

    def judge(self, stage: str, background: str, proposal: DecisionProposal) -> DecisionJudgement:
        prompt = (
            f"Stage: {stage}\n\nBackground:\n{background}\n\n"
            f"Decision: {proposal.topic}\nWhy it is needed: {proposal.context}\n\n"
            f"Options:\n{proposal.model_dump_json(include={'options'}, indent=2)}\n\n"
            "Compare the options on fit with the requirements, risk, cost, complexity and the stated pros "
            "and cons. Recommend exactly one option by its exact name and explain why it is the best fit "
            "and why the others are weaker, in two or three sentences."
        )
        return self._invoke(DecisionJudgement, prompt)
