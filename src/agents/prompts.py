"""Prompt fragments shared by the stage author agents."""
from __future__ import annotations

from typing import Optional

from ..models import DecisionRecord, StageAnalysis

APP_NOTE = (
    "The product is a three-tier web application: a web client, an API server and a data tier reached through "
    "an ORM. The technologies are fixed in the confirmed decisions (application type, web client framework, API "
    "server stack, ORM, database); follow them and never propose alternatives to them."
)

DECISION_INSTRUCTIONS = (
    "Decisions: wherever the inputs do not settle a choice, list it as a decision proposal with the topic, "
    "why it must be decided, and 2 to 4 realistic options, each with pros and cons. Do not pick one; an "
    "independent judge recommends and the user decides. Never re-propose a decision already made."
)


def lines(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "none"


def decided_block(decisions: list[DecisionRecord]) -> str:
    return lines([f"{d.topic}: {d.chosen}" for d in decisions])


def baseline_block(baseline: Optional[StageAnalysis]) -> str:
    return baseline.confirmed_json() if baseline else "none"
