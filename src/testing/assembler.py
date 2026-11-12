"""Builds the final testing document: resolves links to APIs, code and controls, scans the code, computes coverage."""
from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

from ..architecture.models import ArchitectureDocument
from ..dev.checks import safe_path
from ..dev.models import DevDocument
from ..ids import assign_ids
from ..lld.models import ApiEndpoint, LldDocument
from ..prd.models import ProductRequirementsDocument
from ..srs.models import SoftwareRequirementsDocument
from .models import (
    CoverageEntry,
    QaAnalysis,
    QaDocument,
    QaElementSet,
    RequirementCoverage,
    SecurityReport,
)
from .security_scan import scan_source

M = TypeVar("M", bound=BaseModel)


def _norm(text: str) -> str:
    return " ".join(text.lower().split())


def _api_key(method: str, path: str) -> tuple[str, str]:
    return method.strip().upper(), path.strip().rstrip("/").lower() or "/"


def _requirement_key(item) -> tuple:
    return (tuple(item.requirement_ids), item.title.strip().lower())


class QaAssembler:
    def assemble(
        self,
        prd: ProductRequirementsDocument,
        srs: SoftwareRequirementsDocument,
        architecture: ArchitectureDocument,
        lld: LldDocument,
        dev: DevDocument,
        analysis: QaAnalysis,
        results: dict[str, QaElementSet],
        previous: Optional[QaDocument] = None,
    ) -> QaDocument:
        all_apis = lld.api_specifications
        files = {f.path: f for f in [*dev.source_files, *dev.test_files]}
        controls = {c.id for c in architecture.security_architecture.controls}
        abuse = {_norm(a.title): f"ABUSE-{i}" for i, a in enumerate(prd.abuse_cases, 1)}
        prd_ids = {r.id for r in [*prd.functional_requirements, *prd.non_functional_requirements]}
        origins = {
            r.id: r.source_ids
            for r in [*srs.functional_requirements, *srs.non_functional_requirements, *srs.interface_requirements]
        }

        warnings: list[str] = []
        cases, uat, perf, security = [], [], [], []
        for sid, derived in results.items():
            # Components may expose the same method and path, so prefer the APIs linked to this requirement.
            linked = [a for a in all_apis if sid in a.requirement_ids] or all_apis
            apis = {_api_key(a.method, a.path): a for a in linked}
            for c in derived.cases:
                api_ids, components = [], []
                for ref in c.apis:
                    method, _, path = ref.strip().partition(" ")
                    api: Optional[ApiEndpoint] = apis.get(_api_key(method, path))
                    if api:
                        api_ids.append(api.id)
                        components.append(api.component_id)
                    else:
                        warnings.append(f"{sid}: test case '{c.title}' names unknown API '{ref}'; link dropped")
                paths = []
                for raw in c.code_paths:
                    path = safe_path(raw)
                    if path in files:
                        paths.append(path)
                        components.append(files[path].component_id)
                    else:
                        warnings.append(f"{sid}: test case '{c.title}' names unknown file '{raw}'; link dropped")
                cases.append(c.model_copy(update={
                    "requirement_ids": [sid],
                    "api_ids": list(dict.fromkeys(api_ids)),
                    "code_paths": list(dict.fromkeys(paths)),
                    "component_ids": list(dict.fromkeys(x for x in components if x)),
                }))

            for u in derived.uat_scenarios:
                known = [p for p in u.prd_requirement_ids if p in prd_ids]
                if len(known) != len(u.prd_requirement_ids):
                    warnings.append(f"{sid}: UAT scenario '{u.title}' names unknown product requirements; dropped them")
                known = known or [p for p in origins.get(sid, []) if p in prd_ids]
                uat.append(u.model_copy(update={"prd_requirement_ids": known, "requirement_ids": [sid]}))

            perf += [p.model_copy(update={"requirement_ids": [sid]}) for p in derived.performance_plans]

            for s in derived.security_cases:
                known_controls = [c for c in s.controls_verified if c in controls]
                if len(known_controls) != len(s.controls_verified):
                    warnings.append(f"{sid}: security case '{s.title}' names unknown controls; dropped them")
                abuse_id = abuse.get(_norm(s.abuse_case), "")
                if s.abuse_case and not abuse_id:
                    warnings.append(f"{sid}: security case '{s.title}' names unknown abuse case '{s.abuse_case}'")
                security.append(s.model_copy(update={
                    "controls_verified": known_controls, "abuse_case_id": abuse_id, "requirement_ids": [sid],
                }))

        old = previous
        cases = assign_ids(cases, "TC", old.cases if old else [], _requirement_key)
        uat = assign_ids(uat, "UAT", old.uat_scenarios if old else [], _requirement_key)
        perf = assign_ids(perf, "PERF", old.performance_plans if old else [], _requirement_key)
        security = assign_ids(security, "SECT", old.security_cases if old else [], _requirement_key)

        return QaDocument(
            title=f"Testing Artifacts for {srs.title}",
            overview=analysis.summary,
            strategy=analysis.strategy,
            cases=cases,
            uat_scenarios=uat,
            performance_plans=perf,
            security_cases=security,
            security_report=self._security_report(prd, architecture, dev, security),
            coverage=[
                RequirementCoverage(
                    requirement_id=sid,
                    cases=[c.id for c in cases if sid in c.requirement_ids],
                    uat=[u.id for u in uat if sid in u.requirement_ids],
                    performance=[p.id for p in perf if sid in p.requirement_ids],
                    security=[s.id for s in security if sid in s.requirement_ids],
                )
                for sid in results
            ],
            warnings=warnings,
        )

    @staticmethod
    def _security_report(prd, architecture, dev, security) -> SecurityReport:
        abuse = [
            CoverageEntry(id=f"ABUSE-{i}", title=a.title, case_ids=[s.id for s in security if s.abuse_case_id == f"ABUSE-{i}"])
            for i, a in enumerate(prd.abuse_cases, 1)
        ]
        controls = [
            CoverageEntry(id=c.id, title=c.title, case_ids=[s.id for s in security if c.id in s.controls_verified])
            for c in architecture.security_architecture.controls
        ]
        return SecurityReport(
            scope="Static scan of the generated source files plus coverage of abuse cases and security controls. "
            "The planned security tests were not executed.",
            static_findings=scan_source(dev.source_files),
            abuse_case_coverage=abuse,
            control_coverage=controls,
            uncovered=[f"{e.id} {e.title}" for e in [*abuse, *controls] if not e.case_ids],
        )

    @staticmethod
    def extract(document: QaDocument, requirement_id: str) -> QaElementSet:
        """The part of an existing document that was written for one software requirement."""
        return QaElementSet(
            cases=[c for c in document.cases if requirement_id in c.requirement_ids],
            uat_scenarios=[u for u in document.uat_scenarios if requirement_id in u.requirement_ids],
            performance_plans=[p for p in document.performance_plans if requirement_id in p.requirement_ids],
            security_cases=[s for s in document.security_cases if requirement_id in s.requirement_ids],
        )
