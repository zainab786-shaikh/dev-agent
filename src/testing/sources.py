"""Builds the per-requirement test contexts from the traceability graph, and a compact digest for prompts."""
from __future__ import annotations

import json
from typing import Any

from ..architecture.models import ArchitectureDocument
from ..architecture.sources import source_requirements
from ..dev.models import DevDocument
from ..existing import fingerprint
from ..lld.models import LldDocument
from ..prd.models import ProductRequirementsDocument
from ..srs.models import SoftwareRequirementsDocument
from .models import QaAnalysis, QaContext


def qa_digest(
    prd: ProductRequirementsDocument,
    srs: SoftwareRequirementsDocument,
    architecture: ArchitectureDocument,
    dev: DevDocument,
) -> str:
    return json.dumps(
        {
            "title": srs.title,
            "functional_requirements": [{"id": r.id, "statement": r.statement} for r in srs.functional_requirements],
            "non_functional_requirements": [
                {"id": r.id, "category": r.category.value, "metric": r.metric, "target": r.target}
                for r in srs.non_functional_requirements
            ],
            "interfaces": [{"id": r.id, "name": r.name} for r in srs.interface_requirements],
            "abuse_cases": [a.title for a in prd.abuse_cases],
            "security_controls": [{"id": c.id, "title": c.title} for c in architecture.security_architecture.controls],
            "components": [{"id": c.id, "name": c.name, "technology": c.technology} for c in architecture.components],
            "unit_test_files": [f.path for f in dev.test_files],
        }
    )


def _excerpts(files, budget: int = 6000, per_file: int = 1500) -> dict[str, str]:
    """Source files first, each cut to a size the local model's context can hold."""
    result: dict[str, str] = {}
    for f in files:
        if budget <= 0:
            break
        text = f.content[: min(per_file, budget)]
        result[f.path] = text + ("\n... (truncated)" if len(text) < len(f.content) else "")
        budget -= len(text)
    return result


def requirement_contexts(
    prd: ProductRequirementsDocument,
    srs: SoftwareRequirementsDocument,
    architecture: ArchitectureDocument,
    lld: LldDocument,
    dev: DevDocument,
    analysis: QaAnalysis,
    clarifications: list[str],
    decisions: list[Any],
) -> list[tuple[str, QaContext]]:
    """One context per software requirement, holding everything the traceability graph links to it."""
    from ..traceability.builder import Artifacts, build_matrix  # deferred: the builder imports the testing models

    matrix = build_matrix(Artifacts(prd=prd, srs=srs, architecture=architecture, lld=lld, dev=dev))
    prd_items = {r.id: r for r in [*prd.functional_requirements, *prd.non_functional_requirements]}
    origins = {
        r.id: r.source_ids
        for r in [*srs.functional_requirements, *srs.non_functional_requirements, *srs.interface_requirements]
    }

    contexts = []
    for requirement in source_requirements(srs):
        reach = {stage: set(ids) for stage, ids in matrix.downstream("srs", requirement.id).items()}
        prd_ids = {i for i in origins.get(requirement.id, []) if i in prd_items}
        contexts.append((
            requirement.id,
            QaContext(
                requirement=requirement,
                prd_requirements=[prd_items[i] for i in prd_items if i in prd_ids],
                user_stories=[s for s in prd.user_stories if prd_ids & set(s.requirement_ids)],
                abuse_cases=prd.abuse_cases,
                design_elements=[d for d in architecture.design_elements if d.id in reach.get("architecture", ())],
                security_controls=[
                    c for c in architecture.security_architecture.controls if c.id in reach.get("architecture", ())
                ],
                deployment_elements=[
                    d for d in architecture.deployment_architecture.elements if d.id in reach.get("architecture", ())
                ],
                components=[c for c in architecture.components if c.id in reach.get("component", ())],
                apis=[a for a in lld.api_specifications if a.id in reach.get("lld", ())],
                error_rules=[e for e in lld.error_handling if e.component_id in reach.get("component", ())],
                code_files=[f.path for f in dev.source_files if f.path in reach.get("code", ())],
                unit_test_files=[f.path for f in dev.test_files if f.path in reach.get("code", ())],
                code_excerpts=_excerpts(
                    [f for f in [*dev.source_files, *dev.test_files] if f.path in reach.get("code", ())]
                ),
                code_versions={
                    f.path: fingerprint(f.content)
                    for f in [*dev.source_files, *dev.test_files]
                    if f.path in reach.get("code", ())
                },
                analysis=analysis,
                clarifications=clarifications,
                decisions=decisions,
            ),
        ))
    return contexts
