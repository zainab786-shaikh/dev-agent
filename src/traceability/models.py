"""Schemas for the living traceability matrix."""
from __future__ import annotations

from collections import deque

from pydantic import BaseModel, Field

STAGES = ("prd", "sysrs", "srs", "architecture", "lld", "component", "code", "testing")


class TraceNode(BaseModel):
    key: str = Field(description="'<stage>:<id>', unique across stages")
    stage: str
    id: str
    title: str = ""


class TraceEdge(BaseModel):
    """Directed from the upstream item to what was derived from, or verifies, it."""

    source: str
    target: str
    relation: str


class TraceRow(BaseModel):
    root: str = Field(description="The requirement this row starts from, as '<stage>:<id>'")
    title: str = ""
    reach: dict[str, list[str]] = Field(default_factory=dict, description="Everything downstream, grouped by stage")


class TraceGap(BaseModel):
    key: str
    missing: str


class BrokenLink(BaseModel):
    source: str = Field(description="The item that holds the reference")
    reference: str = Field(description="What it refers to but does not exist")


class HistoryEntry(BaseModel):
    at: str
    trigger: str
    artifact: str = ""
    nodes: int
    edges: int
    gaps: int
    broken: int


class TraceabilityMatrix(BaseModel):
    updated_at: str = ""
    stages_present: list[str] = Field(default_factory=list)
    nodes: list[TraceNode] = Field(default_factory=list)
    edges: list[TraceEdge] = Field(default_factory=list)
    rows: list[TraceRow] = Field(default_factory=list)
    gaps: list[TraceGap] = Field(default_factory=list)
    broken_links: list[BrokenLink] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    history: list[HistoryEntry] = Field(default_factory=list)

    def downstream(self, stage: str, item_id: str) -> dict[str, list[str]]:
        """Ids reachable from an item, grouped by stage (the item itself excluded)."""
        adjacency: dict[str, list[str]] = {}
        for e in self.edges:
            adjacency.setdefault(e.source, []).append(e.target)
        by_key = {n.key: n for n in self.nodes}

        start = f"{stage}:{item_id}"
        seen, queue = {start}, deque([start])
        reach: dict[str, list[str]] = {}
        while queue:
            for nxt in adjacency.get(queue.popleft(), []):
                if nxt in seen:
                    continue
                seen.add(nxt)
                queue.append(nxt)
                node = by_key.get(nxt)
                if node:
                    reach.setdefault(node.stage, []).append(node.id)
        return reach
