"""Workflow for artifacts derived item by item: each source item gets its own create/update + review loop."""
from __future__ import annotations

from abc import abstractmethod
from pathlib import Path
from typing import Any

from .agents.decision_judge import DecisionJudge
from .existing import fingerprint
from .interaction import UserInteraction
from .review_loop import ArtifactAuthor, ArtifactReviewer, ReviewLoop
from .staged_workflow import StagedWorkflow, StageState

_IGNORED_IN_FINGERPRINT = {"analysis", "decisions", "clarifications"}


class PerItemWorkflow(StagedWorkflow):
    def __init__(
        self,
        author: ArtifactAuthor,
        reviewer: ArtifactReviewer,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
    ) -> None:
        self._loop = ReviewLoop(self.name.upper(), author, reviewer, max_iterations)
        super().__init__(interaction, output_dir, judge)

    # --- hooks ----------------------------------------------------------------
    @abstractmethod
    def _items(self, state: StageState) -> list[tuple[str, Any]]:
        """(source id, context) for every source item."""

    @abstractmethod
    def _extract(self, document: Any, source_id: str) -> Any:
        """The part of an existing document that was derived from one source item."""

    @abstractmethod
    def _assemble(self, state: StageState, results: dict[str, Any], previous: Any) -> Any: ...

    def _review_decisions(self, state: StageState, document: Any) -> dict[str, str]:
        """Item-level decisions the user may send back; returns feedback per source id."""
        return {}

    def _enrich(self, source_id: str, context: Any, results: dict[str, Any]) -> Any:
        """Adds what earlier items of this pass produced, for items that depend on them."""
        return context

    def _finalize(self, state: StageState, document: Any) -> Any:
        """Last step on the assembled document, e.g. generating files that need every item."""
        return document

    # --- derive ---------------------------------------------------------------
    @staticmethod
    def _is_empty(derived: Any) -> bool:
        return not any(getattr(derived, f) for f in type(derived).model_fields)

    def _derive(self, state: StageState) -> dict:
        existing = state.get("existing")
        analysis = state["analysis"]
        base = fingerprint(
            analysis.confirmed_json(exclude={"summary"}),
            [(d.topic, d.chosen) for d in state["decisions"]],
            state["clarifications"],
        )
        items = self._items(state)

        previous_document = existing.document if existing else None
        previous: dict[str, tuple[Any, Any, dict]] = {}
        if existing:
            previous = {
                sid: (self._extract(existing.document, sid), existing.fingerprint(sid), report)
                for sid, report in existing.items.items()
            }

        current = {sid for sid, _ in items}
        removed = [sid for sid in previous if sid not in current]

        feedback: dict[str, str] = {}
        while True:
            results, reports = self._process(items, previous, base, feedback)
            document = self._assemble(state, results, previous_document)
            previous_document = document
            touched = any(r["action"] != "reused" for r in reports)
            feedback = self._review_decisions(state, document) if touched else {}
            if not feedback:
                break
            previous = {
                r["source_id"]: (results[r["source_id"]], r["fingerprint"], {**r, "in_run": True}) for r in reports
            }

        for sid in removed:
            self._notes.item({"source_id": sid, "action": "removed"})
        for report in reports:
            self._notes.item(report)
        return {
            "document": self._finalize(state, document),
            "items": reports,
            "converged": all(r.get("converged", True) for r in reports),
        }

    def _process(
        self,
        items: list[tuple[str, Any]],
        previous: dict[str, tuple[Any, Any, dict]],
        base: str,
        feedback: dict[str, str],
    ) -> tuple[dict[str, Any], list[dict]]:
        results: dict[str, Any] = {}
        reports: list[dict] = []
        for index, (sid, context) in enumerate(items, 1):
            context = self._enrich(sid, context, results)
            fp = fingerprint(context.model_dump(mode="json", exclude=_IGNORED_IN_FINGERPRINT), base, feedback.get(sid, ""))
            prior = previous.get(sid)
            prior_set = prior[0] if prior and not self._is_empty(prior[0]) else None

            retry = prior_set is not None and prior[2].get("converged") is False and not prior[2].get("in_run")
            if prior_set is not None and prior[1] == fp and not retry:
                results[sid] = prior_set
                earlier = prior[2]
                if earlier.get("in_run"):  # produced earlier in this run: keep what actually happened
                    report = {k: v for k, v in earlier.items() if k != "in_run"}
                else:
                    report = {**earlier, "action": "reused", "iterations": 0}
                report.update(source_id=sid, fingerprint=fp)
                status = "reused (unchanged)" if report["action"] == "reused" else f"{report['action']} earlier in this run"
            else:
                if sid in feedback:
                    note = f"User feedback on {sid}: {feedback[sid]}"
                    context = context.model_copy(update={"clarifications": [*context.clarifications, note]})
                outcome = self._loop.run(context, existing=prior_set)
                results[sid] = outcome.artifact
                report = {
                    "source_id": sid,
                    "action": "updated" if prior_set is not None else "created",
                    "iterations": outcome.iterations,
                    "converged": outcome.converged,
                    "fingerprint": fp,
                    "review": outcome.review.model_dump(mode="json"),
                }
                status = f"{report['action']}, {outcome.iterations} iteration(s), " + (
                    "passed review" if outcome.converged else "unresolved findings"
                )
            reports.append(report)
            self._io.show(f"[{index}/{len(items)}] {sid}: {status}")
        return results, reports
