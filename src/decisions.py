"""Finds the best option for each decision (via the judge) and verifies it with the user."""
from __future__ import annotations

import re

from .agents.decision_judge import DecisionJudge
from .interaction import UserInteraction
from .models import DecisionOption, DecisionOutcome, DecisionProposal, DecisionRecord


def _norm(topic: str) -> str:
    return " ".join(topic.lower().split())


def _number(record_id: str) -> int:
    match = re.fullmatch(r"DEC-(\d+)", record_id)
    return int(match.group(1)) if match else 0


class DecisionService:
    def __init__(self, judge: DecisionJudge, interaction: UserInteraction) -> None:
        self._judge = judge
        self._io = interaction

    @staticmethod
    def proposal_from(record: DecisionRecord) -> DecisionProposal:
        """Re-opens a decided topic with the options that were evaluated before."""
        return DecisionProposal(topic=record.topic, context=record.context, options=record.options)

    def decide(
        self, stage: str, proposals: list[DecisionProposal], background: str, decided: list[DecisionRecord]
    ) -> list[DecisionRecord]:
        known = {_norm(d.topic) for d in decided}
        pending: list[DecisionProposal] = []
        for proposal in proposals:
            if _norm(proposal.topic) in known or len(proposal.options) < 2:
                continue
            known.add(_norm(proposal.topic))
            pending.append(proposal)
        if not pending:
            return []

        self._io.show(f"\n{len(pending)} decision(s) need your verification (options, the judge's pick and why).")
        records = []
        first_number = max((_number(d.id) for d in decided), default=0) + 1
        for number, proposal in enumerate(pending, first_number):
            judgement = self._judge.judge(stage, background, proposal)
            recommended, matched = self._match(proposal, judgement.recommended_option)
            rationale = judgement.rationale
            if not matched:
                rationale += f" (The judge named '{judgement.recommended_option}', which is not a listed option.)"
            records.append(self._ask(stage, f"DEC-{number}", proposal, recommended, rationale))
        return records

    @staticmethod
    def _match(proposal: DecisionProposal, name: str) -> tuple[DecisionOption, bool]:
        wanted = _norm(name)
        for option in proposal.options:
            if _norm(option.name) == wanted:
                return option, True
        for option in proposal.options:
            if wanted and (wanted in _norm(option.name) or _norm(option.name) in wanted):
                return option, True
        return proposal.options[0], False

    def _ask(
        self, stage: str, record_id: str, proposal: DecisionProposal, recommended: DecisionOption, rationale: str
    ) -> DecisionRecord:
        text = [f"\nDecision: {proposal.topic}"]
        if proposal.context:
            text.append(f"  {proposal.context}")
        for n, option in enumerate(proposal.options, 1):
            marker = " (recommended)" if option is recommended else ""
            text.append(f"  {n}. {option.name}{marker}: {option.description}")
            text += [f"       + {p}" for p in option.pros] + [f"       - {c}" for c in option.cons]
        text.append(f"  Judge: {recommended.name} - {rationale}")
        text.append("Press Enter to accept the recommendation, type an option number to choose another, or type your own decision.")
        answer = self._io.ask("\n".join(text))

        chosen, outcome = recommended.name, DecisionOutcome.ACCEPTED_RECOMMENDATION
        if answer.isdigit() and 1 <= int(answer) <= len(proposal.options):
            picked = proposal.options[int(answer) - 1]
            if picked is not recommended:
                chosen, outcome = picked.name, DecisionOutcome.CHOSE_OTHER_OPTION
        elif answer:
            chosen, outcome = answer, DecisionOutcome.CUSTOM

        return DecisionRecord(
            id=record_id,
            stage=stage,
            topic=proposal.topic,
            context=proposal.context,
            options=proposal.options,
            recommended_option=recommended.name,
            recommendation_rationale=rationale,
            chosen=chosen,
            outcome=outcome,
        )
