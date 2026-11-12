"""Human-readable notes of a run: the steps taken, the options evaluated and the decisions made."""
from __future__ import annotations

from .models import DecisionOutcome, DecisionRecord

_OUTCOME_TEXT = {
    DecisionOutcome.ACCEPTED_RECOMMENDATION: "The user accepted the judge's recommendation",
    DecisionOutcome.CHOSE_OTHER_OPTION: "The user chose a different option",
    DecisionOutcome.CUSTOM: "The user entered their own decision",
    DecisionOutcome.CARRIED_OVER: "Carried over unchanged from the previous version",
    DecisionOutcome.ACCEPTED_AGENT_CHOICE: "Chosen by the agent while designing, accepted by the user",
    DecisionOutcome.PRESET: "Fixed by the application catalog or given on the command line",
    DecisionOutcome.FROM_PROFILE: "Fixed by the application profile chosen before this stage",
}


def _cell(text: str) -> str:
    return " ".join(text.split()).replace("|", "/")


def _join(prefix: str, items: list[str]) -> str:
    return _cell("; ".join(f"{prefix} {i}" for i in items))


class RunNotes:
    def __init__(self, title: str) -> None:
        self.title = title
        self.steps: list[str] = []
        self.clarifications: list[tuple[str, str]] = []
        self.decisions: list[DecisionRecord] = []
        self.items: list[dict] = []

    def step(self, text: str) -> None:
        self.steps.append(text)

    def question(self, question: str, answer: str) -> None:
        self.clarifications.append((question, answer))

    def decision(self, record: DecisionRecord) -> None:
        self.decisions.append(record)

    def item(self, report: dict) -> None:
        self.items.append(report)

    def to_markdown(self) -> str:
        out = [f"# {self.title} - notes", "", "## Process", ""]
        out += [f"{n}. {s}" for n, s in enumerate(self.steps, 1)]

        out += ["", "## Decisions", ""]
        if not self.decisions:
            out.append("No decisions were needed.")
        for d in self.decisions:
            out += [f"### {d.id}: {d.topic}", ""]
            if d.context:
                out += [d.context, ""]
            if d.options:
                out += ["| Option | Description | Pros | Cons |", "|---|---|---|---|"]
                for o in d.options:
                    out.append(
                        f"| {_cell(o.name)} | {_cell(o.description)} | {_join('+', o.pros)} | {_join('-', o.cons)} |"
                    )
                out.append("")
            if d.recommended_option:
                out.append(f"- **Recommended:** {d.recommended_option} - {_cell(d.recommendation_rationale)}")
            out += [f"- **Decision:** {d.chosen}", f"- **How:** {_OUTCOME_TEXT[d.outcome]}", ""]

        if self.clarifications:
            out += ["## Clarifications from the user", ""]
            out += [f"- **Q:** {q}  \n  **A:** {a}" for q, a in self.clarifications]
            out.append("")

        if self.items:
            out += ["## Results per item", "", "| Item | Action | Iterations | Review |", "|---|---|---|---|"]
            for i in self.items:
                if i["action"] == "removed":
                    review = "source no longer present"
                elif i["action"] == "reused":
                    review = "unchanged since the previous version"
                else:
                    review = "passed" if i.get("converged") else "unresolved findings remain"
                out.append(f"| {i['source_id']} | {i['action']} | {i.get('iterations', 0)} | {review} |")
            out.append("")
        return "\n".join(out)
