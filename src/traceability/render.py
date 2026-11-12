"""Markdown view of the traceability matrix."""
from __future__ import annotations

from .models import TraceabilityMatrix

_COLUMNS = [
    ("prd", "Stories"), ("sysrs", "System req."), ("srs", "Software req."), ("architecture", "Architecture"),
    ("lld", "LLD"), ("component", "Components"), ("code", "Code"), ("testing", "Tests"),
]
_LIMIT = 6


def _cell(ids: list[str]) -> str:
    shown = ", ".join(ids[:_LIMIT])
    extra = f" +{len(ids) - _LIMIT} more" if len(ids) > _LIMIT else ""
    return (shown + extra).replace("|", "/") or "-"


def render_markdown(m: TraceabilityMatrix) -> str:
    out = [
        "# Traceability matrix",
        "",
        f"Updated: {m.updated_at}. Stages present: {', '.join(m.stages_present) or 'none'}. "
        f"{len(m.nodes)} items, {len(m.edges)} links, {len(m.gaps)} gaps, {len(m.broken_links)} broken links.",
        "",
        "Each row starts from a requirement and lists everything derived from or verifying it. Links from a "
        "requirement to APIs are exact; links from components to code are per component.",
        "",
        "| Requirement | " + " | ".join(label for _, label in _COLUMNS) + " |",
        "|---|" + "---|" * len(_COLUMNS),
    ]
    for row in m.rows:
        title = f" {row.title}" if row.title else ""
        cells = " | ".join(_cell(row.reach.get(stage, [])) for stage, _ in _COLUMNS)
        out.append(f"| {row.root}{title} | {cells} |".replace("\n", " "))

    out += ["", "## Gaps", ""]
    out += [f"- {g.key}: {g.missing}" for g in m.gaps] or ["None."]
    out += ["", "## Broken links", ""]
    out += [f"- {b.source} refers to {b.reference}, which does not exist" for b in m.broken_links] or ["None."]
    if m.notes:
        out += ["", "## Notes", ""] + [f"- {n}" for n in m.notes]

    out += ["", "## Update history", "", "| When | Step | Artifact | Items | Links | Gaps | Broken |", "|---|---|---|---|---|---|---|"]
    out += [
        f"| {h.at} | {h.trigger} | {h.artifact} | {h.nodes} | {h.edges} | {h.gaps} | {h.broken} |" for h in m.history[-30:]
    ]
    return "\n".join(out) + "\n"
