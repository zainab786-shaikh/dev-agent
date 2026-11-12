import json

import chain
from testing.models import QaCase, QaDocument, CaseLevel, UatScenario
from traceability import Artifacts, build_matrix, refresh


def _artifacts(**extra):
    return Artifacts(prd=chain.prd(), sysrs=chain.sysrs(), srs=chain.srs(), architecture=chain.architecture(),
                     lld=chain.lld(), dev=chain.dev(), **extra)


def _testing(**case_overrides):
    case = QaCase(id="TC-1", title="Upload works", level=CaseLevel.SYSTEM, steps=["s"], expected_result="e",
                  requirement_ids=["FR-1"], code_paths=["app/main.py"], api_ids=["API-1"], **case_overrides)
    uat = UatScenario(id="UAT-1", title="Customer uploads", prd_requirement_ids=["FR-1"], requirement_ids=["FR-1"])
    return QaDocument(title="q", overview="o", cases=[case], uat_scenarios=[uat])


def test_a_requirement_row_reaches_every_downstream_stage():
    matrix = build_matrix(_artifacts(testing=_testing()))
    row = next(r for r in matrix.rows if r.root == "prd:FR-1")

    assert row.reach["sysrs"] == ["SR-1"] and row.reach["srs"] == ["FR-1"]
    assert row.reach["architecture"] == ["HLD-1", "SEC-1"] and row.reach["lld"] == ["API-1"]
    assert row.reach["component"] == ["COMP-1"] and set(row.reach["code"]) == {"app/main.py", "tests/test_main.py"}
    assert {"TC-1", "UAT-1"} <= set(row.reach["testing"])
    assert row.reach["prd"] == ["US-1"]  # the user story that covers it


def test_requirements_without_a_product_parent_get_their_own_row():
    matrix = build_matrix(_artifacts())
    assert [r.root for r in matrix.rows] == ["prd:FR-1", "srs:NFR-1"]  # NFR-1 is a confirmed quality target


def test_gaps_name_what_is_missing_and_only_for_stages_that_exist():
    gaps = {(g.key, g.missing) for g in build_matrix(_artifacts(testing=_testing())).gaps}
    assert ("srs:NFR-1", "no architecture design") in gaps and ("srs:NFR-1", "no code") in gaps
    assert ("srs:NFR-1", "no test") in gaps
    assert ("architecture:SEC-1", "security control 'TLS' is not tested") in gaps
    assert ("prd:ABUSE-1", "abuse case 'Malware upload' has no security test") in gaps
    assert not any(m == "no UAT scenario" for _, m in gaps)  # FR-1 has UAT-1

    early = build_matrix(Artifacts(prd=chain.prd(), sysrs=chain.sysrs()))
    assert early.gaps == [] and early.broken_links == []  # later stages do not exist yet


def test_references_to_things_that_do_not_exist_are_reported_as_broken():
    bad = _testing()
    bad.cases[0] = bad.cases[0].model_copy(update={"code_paths": ["ghost.py"], "api_ids": ["API-9"]})
    broken = {(b.source, b.reference) for b in build_matrix(_artifacts(testing=bad)).broken_links}
    assert ("testing:TC-1", "code:ghost.py") in broken and ("testing:TC-1", "lld:API-9") in broken

    stale = chain.srs()
    stale.functional_requirements[0] = stale.functional_requirements[0].model_copy(update={"source_ids": ["SR-9"]})
    assert ("srs:FR-1", "sysrs:SR-9") in {
        (b.source, b.reference) for b in build_matrix(Artifacts(prd=chain.prd(), sysrs=chain.sysrs(), srs=stale)).broken_links
    }


def _save(out, name, document):
    folder = out / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}_20260101_000000.json").write_text(json.dumps({name: document.model_dump(mode="json")}), encoding="utf-8")


def test_refresh_rebuilds_from_saved_artifacts_and_keeps_a_history(tmp_path):
    _save(tmp_path, "prd", chain.prd())
    first = refresh(tmp_path, "prd")
    assert [h.trigger for h in first.history] == ["prd"] and first.stages_present == ["prd"]

    _save(tmp_path, "sysrs", chain.sysrs())
    (tmp_path / "srs").mkdir()
    (tmp_path / "srs" / "srs_20260101_000000.json").write_text("{not json", encoding="utf-8")
    second = refresh(tmp_path, "sysrs")

    assert [h.trigger for h in second.history] == ["prd", "sysrs"]
    assert second.history[1].artifact == "sysrs_20260101_000000.json" and second.history[1].edges == 2
    assert any("srs_20260101_000000.json" in n for n in second.notes)  # an unreadable file is reported, not fatal
    markdown = (tmp_path / "traceability" / "traceability.md").read_text(encoding="utf-8")
    assert "| prd:FR-1 Upload documents |" in markdown and "## Update history" in markdown
    assert json.loads((tmp_path / "traceability" / "traceability.json").read_text())["history"][1]["trigger"] == "sysrs"


def test_a_test_for_one_requirement_does_not_cover_another_through_a_shared_component():
    import chain
    from architecture.models import DesignElement
    from srs.models import SoftwareFunctionalRequirement
    from testing.models import QaCase, QaDocument
    from traceability.builder import Artifacts, build_matrix

    srs = chain.srs()
    srs.functional_requirements.append(SoftwareFunctionalRequirement(id="FR-2", title="b", statement="The system shall b."))
    arch = chain.architecture()
    arch.design_elements.append(DesignElement(id="HLD-2", title="h", description="d", component_ids=["COMP-1"], requirement_ids=["FR-2"]))
    qa = QaDocument(title="q", overview="o", cases=[
        QaCase(id="TC-1", title="t", level="unit", requirement_ids=["FR-1"], code_paths=["app/main.py"])])
    gaps = {(g.key, g.missing) for g in build_matrix(Artifacts(srs=srs, architecture=arch, lld=chain.lld(), dev=chain.dev(), testing=qa)).gaps}
    assert ("srs:FR-2", "no test") in gaps and ("srs:FR-1", "no test") not in gaps
