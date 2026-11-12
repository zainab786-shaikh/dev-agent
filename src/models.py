"""Review and decision schemas shared by every artifact stage."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewFinding(BaseModel):
    severity: Severity
    area: str = Field(description="Requirement id or section the finding applies to")
    issue: str
    recommendation: str


class ReviewResult(BaseModel):
    approved: bool
    summary: str
    findings: list[ReviewFinding] = Field(default_factory=list)

    def blocking(self) -> bool:
        """A review only passes when no high or medium severity finding remains."""
        return not self.approved or any(f.severity in (Severity.HIGH, Severity.MEDIUM) for f in self.findings)


class ClarifyingQuestion(BaseModel):
    question: str
    reason: str = ""


class DecisionOption(BaseModel):
    name: str
    description: str = ""
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)


class DecisionProposal(BaseModel):
    """A choice the inputs do not settle, with the options found for it."""

    topic: str
    context: str = Field(default="", description="What must be decided and why")
    options: list[DecisionOption] = Field(default_factory=list, description="2 to 4 realistic alternatives")


class DecisionJudgement(BaseModel):
    recommended_option: str = Field(description="Exact name of one of the listed options")
    rationale: str


class DecisionOutcome(str, Enum):
    ACCEPTED_RECOMMENDATION = "accepted_recommendation"
    CHOSE_OTHER_OPTION = "chose_other_option"
    CUSTOM = "custom"
    CARRIED_OVER = "carried_over"
    ACCEPTED_AGENT_CHOICE = "accepted_agent_choice"
    PRESET = "preset"
    FROM_PROFILE = "from_profile"


class DecisionRecord(BaseModel):
    """A verified decision: what was evaluated, what was recommended, what the user decided."""

    id: str
    stage: str
    topic: str
    context: str = ""
    options: list[DecisionOption] = Field(default_factory=list)
    recommended_option: str = ""
    recommendation_rationale: str = ""
    chosen: str
    outcome: DecisionOutcome


_NOT_CONFIRMED = {"clarifying_questions", "decision_proposals"}


class StageAnalysis(BaseModel):
    """What a stage proposes before deriving its document; subclasses add stage-specific fields."""

    summary: str
    clarifying_questions: list[ClarifyingQuestion] = Field(default_factory=list)
    decision_proposals: list[DecisionProposal] = Field(default_factory=list)

    def confirmed_json(self, exclude: set[str] | None = None) -> str:
        return self.model_dump_json(exclude=_NOT_CONFIRMED | (exclude or set()))
