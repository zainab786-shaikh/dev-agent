"""Mermaid flowchart source builder shared by the diagram-producing assemblers."""
from __future__ import annotations

import re


def _node(node_id: str) -> str:
    return re.sub(r"\W", "_", node_id)


def _label(text: str) -> str:
    return text.replace('"', "'")


def flowchart(nodes: list[tuple[str, str]], edges: list[tuple[str, str, str]]) -> str:
    """nodes: (id, label); edges: (source id, target id, label)."""
    lines = ["flowchart LR"]
    lines += [f'    {_node(i)}["{_label(label)}"]' for i, label in nodes]
    lines += [f'    {_node(s)} -->|"{_label(label[:40])}"| {_node(t)}' for s, t, label in edges]
    return "\n".join(lines)
