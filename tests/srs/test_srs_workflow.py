import json
from pathlib import Path

from artifact_store import load_sysrs
from prd.models import ProductRequirement, ProductRequirementsDocument
from review_loop import ArtifactAuthor
from srs import SrsWorkflow
from srs.models import (
    QualityCategory, QualityTarget, SoftwareFunctionalRequirement, SoftwareNonFunctionalRequirement,
    SoftwareRequirementSet, SoftwareRequirementsAnalysis, SoftwareSubRequirement,
)
from sysrs.models import ContextDiagram, SystemRequirement, SystemRequirementsDocument
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def reconcile_targets(self, analysis, clarifications, decisions):
        return analysis.quality_targets

    def analyze(self, *_):
        target = QualityTarget(category=QualityCategory.AVAILABILITY, metric="availability", target="99.95%")
        return SoftwareRequirementsAnalysis(
            summary="s", quality_targets=[target], decision_proposals=[platform_proposal("Availability target")]
        )

    def create(self, context):
        fr = SoftwareFunctionalRequirement(
            id="FR-1", title=f"upload for {context.system_requirement.id}", statement="The system shall upload.",
            sub_requirements=[SoftwareSubRequirement(id="x", statement="The system shall validate type.")],
        )
        nfr = SoftwareNonFunctionalRequirement(
            id="NFR-1", category=QualityCategory.PERFORMANCE, statement="s",
            metric=f"latency {context.system_requirement.id}", target="< 2 s",
        )
        return SoftwareRequirementSet(functional_requirements=[fr], non_functional_requirements=[nfr])

    def update(self, context, existing):
        return existing

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")


def _sysrs() -> SystemRequirementsDocument:
    requirements = [
        SystemRequirement(id="SR-1", title="a", description="d", prd_requirement_ids=["FR-1"]),
        SystemRequirement(id="SR-2", title="b", description="d", prd_requirement_ids=["FR-2"]),
    ]
    return SystemRequirementsDocument(
        title="s", overview="o", context_diagram=ContextDiagram(title="c", mermaid="flowchart LR"),
        system_requirements=requirements,
    )


def test_srs_derives_one_set_per_system_requirement(tmp_path):
    prd = ProductRequirementsDocument(
        title="p", overview="o", functional_requirements=[ProductRequirement(id="FR-1", title="a", description="b")]
    )
    workflow = SrsWorkflow(StubAuthor(), ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
    result = workflow.run(prd, _sysrs())
    saved = json.loads(Path(result["output_path"]).read_text())
    srs = saved["srs"]

    assert [f["id"] for f in srs["functional_requirements"]] == ["FR-1", "FR-2"]
    assert [f["source_ids"] for f in srs["functional_requirements"]] == [["SR-1", "FR-1"], ["SR-2", "FR-2"]]
    assert srs["functional_requirements"][1]["sub_requirements"][0]["id"] == "FR-2.1"
    # confirmed system-wide target first, then the item-specific ones
    assert [n["id"] for n in srs["non_functional_requirements"]] == ["NFR-1", "NFR-2", "NFR-3"]
    assert srs["non_functional_requirements"][0]["target"] == "99.95%"
    assert saved["decisions"][0]["topic"] == "Availability target"


def test_load_sysrs(tmp_path):
    path = tmp_path / "sysrs_20260101_000000.json"
    path.write_text(json.dumps({"sysrs": _sysrs().model_dump(mode="json")}), encoding="utf-8")
    assert load_sysrs(path).title == "s"


def test_quality_targets_follow_the_decision_the_user_made(tmp_path):
    class DecidingAuthor(StubAuthor):
        def reconcile_targets(self, analysis, clarifications, decisions):
            chosen = next(d.chosen for d in decisions if d.topic == "Availability target")
            return [t.model_copy(update={"target": chosen}) for t in analysis.quality_targets]

    prd = ProductRequirementsDocument(title="p", overview="o")
    workflow = SrsWorkflow(DecidingAuthor(), ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
    result = workflow.run(prd, _sysrs())
    assert result["decisions"][0].chosen == "Mobile app"  # the stub judge's recommendation
    assert result["document"].non_functional_requirements[0].target == "Mobile app"
