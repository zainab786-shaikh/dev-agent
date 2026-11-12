"""Mermaid sources for the sequence, class and ER diagrams, built from the structured design (no LLM)."""
from __future__ import annotations

import re

from .models import ClassKind, ClassSpec, DatabaseTable, RelationKind, SequenceDiagram, StepKind

_ARROWS = {StepKind.CALL: "->>", StepKind.RETURN: "-->>", StepKind.ASYNC: "-)"}


def _id(name: str) -> str:
    return re.sub(r"\W", "_", name.strip()) or "_"


def _text(text: str) -> str:
    return " ".join(text.replace(";", ",").replace("#", "").split())


def sequence_mermaid(diagram: SequenceDiagram) -> str:
    names = list(dict.fromkeys([*diagram.participants, *(n for s in diagram.steps for n in (s.source, s.target))]))
    lines = ["sequenceDiagram"]
    lines += [f"    participant {_id(n)} as {_text(n)}" for n in names]
    lines += [
        f"    {_id(s.source)}{_ARROWS[s.kind]}{_id(s.target)}: {_text(s.message)}" for s in diagram.steps
    ]
    return "\n".join(lines)


def _generic(text: str) -> str:
    return _text(text).replace("<", "~").replace(">", "~")


def class_mermaid(classes: list[ClassSpec]) -> str:
    lines = ["classDiagram"]
    for c in classes:
        lines.append(f"    class {_id(c.name)} {{")
        if c.kind != ClassKind.CLASS:
            lines.append(f"        <<{c.kind.value}>>")
        lines += [f"        +{_generic(a.type)} {_id(a.name)}" for a in c.attributes]
        lines += [f"        +{_generic(m.signature)}" for m in c.methods]
        lines.append("    }")

    arrows = {
        RelationKind.INHERITS: "{t} <|-- {s}",
        RelationKind.IMPLEMENTS: "{t} <|.. {s}",
        RelationKind.COMPOSES: "{s} *-- {t}",
        RelationKind.USES: "{s} --> {t}",
        RelationKind.DEPENDS: "{s} ..> {t}",
    }
    for c in classes:
        for r in c.relations:
            line = arrows[r.kind].format(s=_id(c.name), t=_id(r.target))
            lines.append(f"    {line}" + (f" : {_text(r.label)}" if r.label else ""))
    return "\n".join(lines)


def er_mermaid(tables: list[DatabaseTable]) -> str:
    if not tables:
        return ""
    lines = ["erDiagram"]
    for t in tables:
        lines.append(f"    {_id(t.name)} {{")
        for col in t.columns:
            keys = [k for k, on in (("PK", col.primary_key), ("FK", bool(col.references)), ("UK", col.unique)) if on]
            lines.append(f"        {_id(col.type)} {_id(col.name)}" + (f" {','.join(keys)}" if keys else ""))
        lines.append("    }")

    known = {_id(t.name) for t in tables}
    for t in tables:
        for col in t.columns:
            if col.references:
                parent = _id(col.references.split(".")[0])
                if parent in known:
                    lines.append(f'    {parent} ||--o{{ {_id(t.name)} : "{_text(col.name)}"')
    return "\n".join(lines)
