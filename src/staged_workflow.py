"""Template for every artifact workflow.

analyze -> decide (judge + user verify) -> elaborate -> confirm -> derive -> publish -> save,
creating a new document or updating the existing one, and writing notes of the whole run.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents.decision_judge import DecisionJudge
from .decisions import DecisionService
from .existing import ExistingArtifact
from .interaction import UserInteraction
from .models import DecisionOutcome, DecisionProposal, DecisionRecord
from .notes import RunNotes

logger = logging.getLogger(__name__)

PROFILE_STAGE = "profile"


class StageState(TypedDict, total=False):
    inputs: dict[str, Any]
    existing: Optional[ExistingArtifact]
    clarifications: list[str]
    feedback: str
    analysis: Any
    decisions: list[DecisionRecord]
    revisit_done: bool
    confirmed: bool
    document: Any
    items: list[dict]
    converged: bool
    output_path: str


class StagedWorkflow(ABC):
    name: str  # file prefix and payload key, e.g. "prd"
    title: str

    def __init__(self, interaction: UserInteraction, output_dir: Path, judge: DecisionJudge) -> None:
        self._io = interaction
        self._output_dir = output_dir
        self._decision_service = DecisionService(judge, interaction)
        self._notes = RunNotes(self.title)
        self._upstream: list[DecisionRecord] = []
        self._graph = self._build()

    def use_profile(self, decisions: list[DecisionRecord]) -> "StagedWorkflow":
        """Decisions fixed before this stage (the application profile); every prompt then follows them."""
        self._upstream = list(decisions)
        return self

    # --- stage-specific hooks -------------------------------------------------
    @abstractmethod
    def _analysis_call(self, state: StageState) -> Any: ...

    @abstractmethod
    def _describe(self, analysis: Any) -> list[str]: ...

    @abstractmethod
    def _inputs_digest(self, state: StageState) -> str: ...

    @abstractmethod
    def _derive(self, state: StageState) -> dict: ...

    def _elaborate(self, state: StageState) -> Any:
        return state["analysis"]

    def _publish(self, state: StageState) -> dict:
        """Side effects outside the saved artifact (e.g. writing a project); none by default."""
        return {}

    # --- run ------------------------------------------------------------------
    def _start(self, inputs: dict[str, Any], existing: Optional[ExistingArtifact]) -> StageState:
        self._notes = RunNotes(self.title)
        decisions: list[DecisionRecord] = list(self._upstream)
        if self._upstream:
            self._notes.step(
                "Applied the application profile: " + "; ".join(f"{d.topic}: {d.chosen}" for d in self._upstream)
            )
            for d in self._upstream:
                self._notes.decision(d.model_copy(update={"outcome": DecisionOutcome.FROM_PROFILE}))
        if existing:
            own = [d for d in existing.decisions if d.stage != PROFILE_STAGE]  # the profile is applied fresh
            decisions += own
            self._notes.step(f"Read the inputs and the existing {self.title} ({existing.path.name}); updating it")
        else:
            self._notes.step(f"Read the inputs; no earlier {self.title} found, creating a new one")
        return {
            "inputs": inputs,
            "existing": existing,
            "clarifications": [],
            "feedback": "",
            "decisions": decisions,
        }

    def _execute(self, inputs: dict[str, Any], existing: Optional[ExistingArtifact]) -> StageState:
        return self._graph.invoke(self._start(inputs, existing), {"recursion_limit": 100})

    def _build(self):
        graph = StateGraph(StageState)
        graph.add_node("analyze", self._node_analyze)
        graph.add_node("decide", self._node_decide)
        graph.add_node("elaborate", self._node_elaborate)
        graph.add_node("confirm", self._node_confirm)
        graph.add_node("derive", self._node_derive)
        graph.add_node("publish", self._node_publish)
        graph.add_node("save", self._node_save)

        graph.add_edge(START, "analyze")
        graph.add_edge("analyze", "decide")
        graph.add_edge("decide", "elaborate")
        graph.add_edge("elaborate", "confirm")
        graph.add_conditional_edges(
            "confirm", lambda s: "derive" if s["confirmed"] else "analyze", ["derive", "analyze"]
        )
        graph.add_edge("derive", "publish")
        graph.add_edge("publish", "save")
        graph.add_edge("save", END)
        return graph.compile()

    # --- nodes ----------------------------------------------------------------
    def _node_analyze(self, state: StageState) -> StageState:
        logger.info("%s: analyzing", self.name)
        analysis = self._analysis_call(state)
        self._notes.step(f"Analyzed the inputs: {analysis.summary}")
        return {"analysis": analysis}

    def _node_decide(self, state: StageState) -> StageState:
        analysis = state["analysis"]
        decided = list(state["decisions"])
        proposals = list(analysis.decision_proposals)
        extra: StageState = {}
        if state.get("existing") and not state.get("revisit_done"):
            decided, reopened = self._offer_revisit(decided)
            proposals = [*reopened, *proposals]
            extra["revisit_done"] = True

        background = f"{analysis.summary}\n{self._inputs_digest(state)}"
        if state["clarifications"]:
            background += "\nUser clarifications:\n" + "\n".join(state["clarifications"])
        records = self._decision_service.decide(self.name, proposals, background, decided)
        for record in records:
            self._notes.decision(record)
            self._notes.step(
                f"Evaluated {len(record.options)} options for '{record.topic}'; the judge recommended "
                f"'{record.recommended_option}'; decision: '{record.chosen}'"
            )
        return {"decisions": [*decided, *records], **extra}

    def _offer_revisit(self, decided: list[DecisionRecord]) -> tuple[list[DecisionRecord], list[DecisionProposal]]:
        """Decisions carried over from the previous version stay unless the user reopens them."""
        fixed = [d for d in decided if d.stage == PROFILE_STAGE]
        decided = [d for d in decided if d.stage != PROFILE_STAGE]
        if not decided:
            return fixed, []
        self._io.show("\nDecisions carried over from the previous version:")
        for d in decided:
            self._io.show(f"  - {d.id} {d.topic}: {d.chosen}")
        answer = self._io.ask("Enter the ids to revisit (e.g. DEC-1, DEC-3), or press Enter to keep them all")
        wanted = {a.strip().upper() for a in answer.split(",") if a.strip()}

        kept = [d for d in decided if d.id.upper() not in wanted]
        reopened = [d for d in decided if d.id.upper() in wanted]
        for d in kept:
            self._notes.decision(d.model_copy(update={"outcome": DecisionOutcome.CARRIED_OVER}))
        for d in reopened:
            self._notes.step(f"The user chose to revisit '{d.topic}' (previously '{d.chosen}')")
        return [*fixed, *kept], [DecisionService.proposal_from(d) for d in reopened]

    def _node_elaborate(self, state: StageState) -> StageState:
        return {"analysis": self._elaborate(state)}

    def _node_confirm(self, state: StageState) -> StageState:
        analysis = state["analysis"]
        clarifications = list(state["clarifications"])

        self._io.show(f"\nSummary: {analysis.summary}")
        for line in self._describe(analysis):
            self._io.show(line)

        for q in analysis.clarifying_questions:
            hint = f" ({q.reason})" if q.reason else ""
            answer = self._io.ask(f"Question: {q.question}{hint}\n(leave blank to skip)")
            if answer:
                clarifications.append(f"Q: {q.question} A: {answer}")
                self._notes.question(q.question, answer)

        if self._io.confirm("\nConfirm this analysis?"):
            self._notes.step("The user confirmed the analysis")
            return {"clarifications": clarifications, "confirmed": True, "feedback": ""}
        feedback = self._io.ask("What should be changed, added or removed?")
        self._notes.step(f"The user asked for changes to the analysis: {feedback}")
        return {"clarifications": clarifications, "confirmed": False, "feedback": feedback}

    def _node_derive(self, state: StageState) -> StageState:
        result = self._derive(state)
        self._notes.step(f"Created the {self.title} through create/update, review and revise loops")
        return result

    def _node_publish(self, state: StageState) -> StageState:
        return self._publish(state)

    def _node_save(self, state: StageState) -> StageState:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = self._output_dir / f"{self.name}_{stamp}.json"
        notes_path = path.with_name(f"{path.stem}.notes.md")

        self._notes.step(f"Saved the result to {path.name} and these notes to {notes_path.name}")
        payload = {
            self.name: state["document"].model_dump(mode="json"),
            "analysis": state["analysis"].model_dump(mode="json"),
            "decisions": [d.model_dump(mode="json") for d in state["decisions"]],
            "items": state["items"],
            "converged": state["converged"],
            "mode": "update" if state.get("existing") else "new",
            "steps": self._notes.steps,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        notes_path.write_text(self._notes.to_markdown(), encoding="utf-8")
        self._io.show(f"\n{self.title} saved to {path}\nNotes saved to {notes_path}")
        return {"output_path": str(path)}
