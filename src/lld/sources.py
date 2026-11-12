"""Views of the SRS and architecture used to prompt and to build the per-component contexts."""
from __future__ import annotations

import json

from ..architecture.models import ArchitectureComponent, ArchitectureDocument
from ..architecture.sources import source_requirements
from ..srs.models import SoftwareRequirementsDocument


def lld_digest(architecture: ArchitectureDocument, srs: SoftwareRequirementsDocument) -> str:
    return json.dumps(
        {
            "title": architecture.title,
            "architecture_decisions": [
                {"topic": d.topic, "decision": d.decision} for d in architecture.solution_architecture
            ],
            "components": [
                {"id": c.id, "name": c.name, "technology": c.technology, "responsibility": c.responsibility}
                for c in architecture.components
            ],
            "interactions": [
                {"source": i.source, "target": i.target, "description": i.description, "mechanism": i.mechanism}
                for i in architecture.interactions
            ],
            "requirements": [{"id": r.id, "statement": r.statement} for r in source_requirements(srs)],
        }
    )


def component_requirement_ids(architecture: ArchitectureDocument, component_id: str) -> list[str]:
    """Software requirement ids that the architecture ties to a component."""
    linked = [
        *architecture.design_elements,
        *architecture.security_architecture.controls,
        *architecture.deployment_architecture.elements,
    ]
    ids = [rid for item in linked if component_id in item.component_ids for rid in item.requirement_ids]
    return list(dict.fromkeys(ids))


def related_requirements(architecture: ArchitectureDocument, srs: SoftwareRequirementsDocument, component: ArchitectureComponent):
    wanted = set(component_requirement_ids(architecture, component.id))
    return [r for r in source_requirements(srs) if r.id in wanted]
