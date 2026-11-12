"""Builds the final SRS from per-system-requirement results (no LLM)."""
from __future__ import annotations

from typing import Optional, TypeVar

from pydantic import BaseModel

from ..ids import assign_ids
from ..sysrs.models import SystemRequirementsDocument
from .models import (
    SoftwareFunctionalRequirement,
    SoftwareNonFunctionalRequirement,
    SoftwareRequirementSet,
    SoftwareRequirementsAnalysis,
    SoftwareRequirementsDocument,
)

M = TypeVar("M", bound=BaseModel)

CONFIRMED_TARGET_SOURCE = "confirmed-quality-target"


def _with_sources(items: list[M], sources: list[str]) -> list[M]:
    return [item.model_copy(update={"source_ids": sources}) for item in items]


def _functional_key(r: SoftwareFunctionalRequirement) -> tuple:
    return (tuple(r.source_ids), r.title.strip().lower())


def _quality_key(r: SoftwareNonFunctionalRequirement) -> tuple:
    return (tuple(r.source_ids), r.category.value, r.metric.strip().lower())


def _interface_key(r) -> tuple:
    return (tuple(r.source_ids), r.name.strip().lower())


class SrsAssembler:
    def assemble(
        self,
        sysrs: SystemRequirementsDocument,
        analysis: SoftwareRequirementsAnalysis,
        clarifications: list[str],
        results: dict[str, SoftwareRequirementSet],
        previous: Optional[SoftwareRequirementsDocument] = None,
    ) -> SoftwareRequirementsDocument:
        by_id = {r.id: r for r in sysrs.system_requirements}
        functional, quality, interfaces = [], [], []
        for source_id, derived in results.items():
            system_requirement = by_id[source_id]
            sources = [system_requirement.id, *system_requirement.prd_requirement_ids]
            functional += _with_sources(derived.functional_requirements, sources)
            quality += _with_sources(derived.non_functional_requirements, sources)
            interfaces += _with_sources(derived.interface_requirements, sources)

        # System-wide targets the user confirmed come first.
        confirmed = [
            SoftwareNonFunctionalRequirement(
                id="",
                category=t.category,
                statement=f"The system shall achieve {t.metric}: {t.target}.",
                metric=t.metric,
                target=t.target,
                source_ids=[CONFIRMED_TARGET_SOURCE],
            )
            for t in analysis.quality_targets
        ]

        functional = assign_ids(functional, "FR", previous.functional_requirements if previous else [], _functional_key)
        functional = [f.model_copy(update={"sub_requirements": self._number_subs(f)}) for f in functional]
        return SoftwareRequirementsDocument(
            title=f"Software Requirements for {sysrs.title}",
            overview=analysis.summary,
            assumptions=clarifications,
            functional_requirements=functional,
            non_functional_requirements=assign_ids(
                [*confirmed, *quality], "NFR", previous.non_functional_requirements if previous else [], _quality_key
            ),
            interface_requirements=assign_ids(
                interfaces, "IFR", previous.interface_requirements if previous else [], _interface_key
            ),
        )

    @staticmethod
    def _number_subs(requirement: SoftwareFunctionalRequirement):
        return [
            s.model_copy(update={"id": f"{requirement.id}.{m}"}) for m, s in enumerate(requirement.sub_requirements, 1)
        ]

    @staticmethod
    def extract(document: SoftwareRequirementsDocument, source_id: str) -> SoftwareRequirementSet:
        """The part of an existing SRS that was derived from one system requirement."""
        return SoftwareRequirementSet(
            functional_requirements=[r for r in document.functional_requirements if source_id in r.source_ids],
            non_functional_requirements=[r for r in document.non_functional_requirements if source_id in r.source_ids],
            interface_requirements=[r for r in document.interface_requirements if source_id in r.source_ids],
        )
