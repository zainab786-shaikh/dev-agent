"""Builds the traceability matrix from the latest artifact of every stage (no LLM)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ..architecture.models import ArchitectureDocument
from ..dev.models import DevDocument
from ..lld.models import LldDocument
from ..prd.models import ProductRequirementsDocument
from ..srs.models import SoftwareRequirementsDocument
from ..sysrs.models import SystemRequirementsDocument
from ..testing.models import QaDocument
from .models import BrokenLink, TraceEdge, TraceGap, TraceNode, TraceRow, TraceabilityMatrix

CONFIRMED_TARGET = "confirmed-quality-target"
PERFORMANCE_CATEGORIES = {"performance", "scalability", "availability", "reliability"}


@dataclass
class Artifacts:
    prd: Optional[ProductRequirementsDocument] = None
    sysrs: Optional[SystemRequirementsDocument] = None
    srs: Optional[SoftwareRequirementsDocument] = None
    architecture: Optional[ArchitectureDocument] = None
    lld: Optional[LldDocument] = None
    dev: Optional[DevDocument] = None
    testing: Optional[QaDocument] = None

    def present(self) -> list[str]:
        return [name for name in ("prd", "sysrs", "srs", "architecture", "lld", "dev", "testing") if getattr(self, name)]


def _key(stage: str, item_id: str) -> str:
    return f"{stage}:{item_id}"


class _Builder:
    def __init__(self, a: Artifacts) -> None:
        self.a = a
        self.present = set(a.present())
        self.nodes: dict[str, TraceNode] = {}
        self.edges: list[TraceEdge] = []
        self.broken: list[BrokenLink] = []

    # --- helpers --------------------------------------------------------------
    def node(self, stage: str, item_id: str, title: str = "") -> None:
        self.nodes[_key(stage, item_id)] = TraceNode(key=_key(stage, item_id), stage=stage, id=item_id, title=title)

    def link(self, src: tuple[str, str], dst: tuple[str, str], relation: str) -> None:
        """Upstream -> downstream. A reference to an id that does not exist is recorded as broken."""
        if not (self._artifact_exists(src[0]) and self._artifact_exists(dst[0])):
            return
        s, d = _key(*src), _key(*dst)
        if s in self.nodes and d in self.nodes:
            self.edges.append(TraceEdge(source=s, target=d, relation=relation))
        elif d in self.nodes:
            self.broken.append(BrokenLink(source=d, reference=s))
        elif s in self.nodes:
            self.broken.append(BrokenLink(source=s, reference=d))

    def _artifact_exists(self, stage: str) -> bool:
        return {"component": "architecture", "code": "dev"}.get(stage, stage) in self.present

    # --- nodes ----------------------------------------------------------------
    def add_nodes(self) -> None:
        a = self.a
        if a.prd:
            for r in [*a.prd.functional_requirements, *a.prd.non_functional_requirements]:
                self.node("prd", r.id, r.title)
            for s in a.prd.user_stories:
                self.node("prd", s.id, s.goal)
            for i, abuse in enumerate(a.prd.abuse_cases, 1):
                self.node("prd", f"ABUSE-{i}", abuse.title)
        if a.sysrs:
            for r in a.sysrs.system_requirements:
                self.node("sysrs", r.id, r.title)
            for u in a.sysrs.system_use_cases:
                self.node("sysrs", u.id, u.title)
            for i in a.sysrs.integration_requirements:
                self.node("sysrs", i.id, i.title)
        if a.srs:
            for r in a.srs.functional_requirements:
                self.node("srs", r.id, r.title)
            for r in a.srs.non_functional_requirements:
                self.node("srs", r.id, f"{r.metric}: {r.target}")
            for r in a.srs.interface_requirements:
                self.node("srs", r.id, r.name)
        if a.architecture:
            for c in a.architecture.components:
                self.node("component", c.id, c.name)
            for d in a.architecture.design_elements:
                self.node("architecture", d.id, d.title)
            for d in a.architecture.decisions:
                self.node("architecture", d.id, d.title)
            for c in a.architecture.security_architecture.controls:
                self.node("architecture", c.id, c.title)
            for d in a.architecture.deployment_architecture.elements:
                self.node("architecture", d.id, d.name)
        if a.lld:
            for x in a.lld.api_specifications:
                self.node("lld", x.id, f"{x.method} {x.path}")
            for x in a.lld.sequence_diagrams:
                self.node("lld", x.id, x.title)
            for x in a.lld.database_schema.tables:
                self.node("lld", x.id, x.name)
            for x in a.lld.classes:
                self.node("lld", x.id, x.name)
            for x in a.lld.error_handling:
                self.node("lld", x.id, x.scenario)
            for x in a.lld.ui_screens:
                self.node("lld", x.id, f"{x.name} {x.route}")
        if a.dev:
            for f in [*a.dev.source_files, *a.dev.test_files]:
                self.node("code", f.path, f.purpose)
        if a.testing:
            for c in a.testing.cases:
                self.node("testing", c.id, c.title)
            for u in a.testing.uat_scenarios:
                self.node("testing", u.id, u.title)
            for p in a.testing.performance_plans:
                self.node("testing", p.id, p.title)
            for s in a.testing.security_cases:
                self.node("testing", s.id, s.title)

    # --- edges ----------------------------------------------------------------
    def add_edges(self) -> None:
        a = self.a
        if a.prd:
            for s in a.prd.user_stories:
                for rid in s.requirement_ids:
                    self.link(("prd", rid), ("prd", s.id), "covered by story")
        if a.sysrs:
            for item in [*a.sysrs.system_requirements, *a.sysrs.system_use_cases, *a.sysrs.integration_requirements]:
                for pid in item.prd_requirement_ids:
                    self.link(("prd", pid), ("sysrs", item.id), "derived from")
        if a.srs:
            self._srs_edges(a.srs)
        if a.architecture:
            self._architecture_edges(a.architecture)
        if a.lld:
            self._lld_edges(a.lld)
        if a.dev:
            for f in [*a.dev.source_files, *a.dev.test_files]:
                if f.component_id:
                    self.link(("component", f.component_id), ("code", f.path), "implemented in")
        if a.testing:
            self._testing_edges(a.testing)

    def _srs_edges(self, srs: SoftwareRequirementsDocument) -> None:
        prd_ids = {n.id for n in self.nodes.values() if n.stage == "prd"}
        for r in [*srs.functional_requirements, *srs.non_functional_requirements, *srs.interface_requirements]:
            for ref in r.source_ids:
                if ref == CONFIRMED_TARGET or ref in prd_ids:
                    continue  # confirmed targets have no upstream; PRD ids are reached through the system requirement
                if "sysrs" in self.present:
                    self.link(("sysrs", ref), ("srs", r.id), "derived from")

    def _architecture_edges(self, arch: ArchitectureDocument) -> None:
        elements = [
            *arch.design_elements,
            *arch.decisions,
            *arch.security_architecture.controls,
            *arch.deployment_architecture.elements,
        ]
        for e in elements:
            for rid in e.requirement_ids:
                if "srs" in self.present:
                    self.link(("srs", rid), ("architecture", e.id), "designed by")
            for cid in getattr(e, "component_ids", []):
                self.link(("architecture", e.id), ("component", cid), "realized by")

    def _lld_edges(self, lld: LldDocument) -> None:
        for item in [*lld.api_specifications, *lld.sequence_diagrams, *lld.ui_screens]:
            for rid in item.requirement_ids:
                if "srs" in self.present:
                    self.link(("srs", rid), ("lld", item.id), "detailed in")
            if item.component_id:
                self.link(("lld", item.id), ("component", item.component_id), "owned by")
        for item in [*lld.database_schema.tables, *lld.classes, *lld.error_handling]:
            if item.component_id:
                self.link(("component", item.component_id), ("lld", item.id), "detailed in")

    def _testing_edges(self, qa: QaDocument) -> None:
        for c in qa.cases:
            for rid in c.requirement_ids:
                self.link(("srs", rid), ("testing", c.id), "verified by")
            for path in c.code_paths:
                self.link(("code", path), ("testing", c.id), "tested by")
            for api in c.api_ids:
                self.link(("lld", api), ("testing", c.id), "tested by")
        for u in qa.uat_scenarios:
            for pid in u.prd_requirement_ids:
                self.link(("prd", pid), ("testing", u.id), "accepted by")
        for p in qa.performance_plans:
            for rid in p.requirement_ids:
                self.link(("srs", rid), ("testing", p.id), "verified by")
        for s in qa.security_cases:
            for rid in s.requirement_ids:
                self.link(("srs", rid), ("testing", s.id), "verified by")
            for control in s.controls_verified:
                self.link(("architecture", control), ("testing", s.id), "tested by")
            if s.abuse_case_id:
                self.link(("prd", s.abuse_case_id), ("testing", s.id), "tested by")


def _gaps(m: TraceabilityMatrix, a: Artifacts) -> list[TraceGap]:
    present = set(a.present())
    gaps: list[TraceGap] = []

    def has(reach: dict[str, list[str]], stage: str, prefix: str = "") -> bool:
        return any(i.startswith(prefix) for i in reach.get(stage, []))

    def gap(key: str, missing: str) -> None:
        gaps.append(TraceGap(key=key, missing=missing))

    if a.prd:
        functional = {r.id for r in a.prd.functional_requirements}
        for r in [*a.prd.functional_requirements, *a.prd.non_functional_requirements]:
            reach = m.downstream("prd", r.id)
            if "sysrs" in present and not reach.get("sysrs"):
                gap(_key("prd", r.id), "no system requirement")
            if "testing" in present and r.id in functional and not has(reach, "testing", "UAT"):
                gap(_key("prd", r.id), "no UAT scenario")
        if "testing" in present:
            for i, abuse in enumerate(a.prd.abuse_cases, 1):
                if not has(m.downstream("prd", f"ABUSE-{i}"), "testing", "SECT"):
                    gap(_key("prd", f"ABUSE-{i}"), f"abuse case '{abuse.title}' has no security test")
    if a.sysrs and "srs" in present:
        for r in a.sysrs.system_requirements:
            if not m.downstream("sysrs", r.id).get("srs"):
                gap(_key("sysrs", r.id), "no software requirement")
    if a.srs:
        nfr_ids = {r.id: r for r in a.srs.non_functional_requirements}
        for r in [*a.srs.functional_requirements, *a.srs.non_functional_requirements, *a.srs.interface_requirements]:
            reach = m.downstream("srs", r.id)
            key = _key("srs", r.id)
            is_nfr = r.id in nfr_ids
            if "architecture" in present and not reach.get("architecture"):
                gap(key, "no architecture design")
            if "lld" in present and not is_nfr and not reach.get("lld"):
                gap(key, "no detailed design (API or flow)")
            if "dev" in present and not reach.get("code"):
                gap(key, "no code")
            if "testing" in present:  # only tests written for this requirement count, not ones reached through a shared component
                own = {"testing": [e.target.split(":", 1)[1] for e in m.edges if e.source == key and e.target.startswith("testing:")]}
                if not own["testing"]:
                    gap(key, "no test")
                elif is_nfr and r.category.value in PERFORMANCE_CATEGORIES and not has(own, "testing", "PERF"):
                    gap(key, "no performance test")
                elif is_nfr and r.category.value == "security" and not has(own, "testing", "SECT"):
                    gap(key, "no security test")
                elif not is_nfr and not has(own, "testing", "TC"):
                    gap(key, "no test case")
    if a.architecture and "testing" in present:
        for c in a.architecture.security_architecture.controls:
            if not has(m.downstream("architecture", c.id), "testing", "SECT"):
                gap(_key("architecture", c.id), f"security control '{c.title}' is not tested")
    return gaps


def build_matrix(a: Artifacts) -> TraceabilityMatrix:
    b = _Builder(a)
    b.add_nodes()
    b.add_edges()
    matrix = TraceabilityMatrix(
        stages_present=a.present(), nodes=list(b.nodes.values()), edges=b.edges, broken_links=b.broken
    )

    roots: list[TraceNode] = []
    if a.prd:
        requirement_ids = {r.id for r in [*a.prd.functional_requirements, *a.prd.non_functional_requirements]}
        roots += [n for n in matrix.nodes if n.stage == "prd" and n.id in requirement_ids]
    targets = {e.target for e in matrix.edges if e.source.startswith(("prd:", "sysrs:"))}
    roots += [n for n in matrix.nodes if n.stage == "srs" and n.key not in targets]  # e.g. confirmed quality targets
    matrix.rows = [TraceRow(root=n.key, title=n.title, reach=matrix.downstream(n.stage, n.id)) for n in roots]
    matrix.gaps = _gaps(matrix, a)
    return matrix
