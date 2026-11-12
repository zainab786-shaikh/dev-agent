import json
from pathlib import Path

import chain
from review_loop import ArtifactAuthor
from testing import QaWorkflow
from testing.models import (
    CaseLevel, PerformancePlan, QaAnalysis, QaCase, QaElementSet, QaStrategy, SecurityCase, UatScenario,
)
from testing.reviewer_agent import check_qa
from testing.sources import requirement_contexts
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal


class StubAuthor(ArtifactAuthor):
    def __init__(self):
        self.created, self.updated = [], []

    def analyze(self, *_):
        return QaAnalysis(summary="s", decision_proposals=[platform_proposal("Performance test tool")])

    def design_strategy(self, *_):
        return QaStrategy(objectives=["verify every requirement"])

    def create(self, context):
        self.created.append(context.requirement.id)
        return self._tests(context)

    def update(self, context, existing):
        self.updated.append(context.requirement.id)
        return self._tests(context)

    @staticmethod
    def _tests(context):
        return QaElementSet(
            cases=[
                QaCase(title=f"works {context.requirement.id}", level=CaseLevel.SYSTEM, steps=["s"], expected_result="e",
                       apis=["post /v1/documents/", "GET /v1/ghost"], code_paths=["./app/main.py", "ghost.py"]),
            ],
            uat_scenarios=[UatScenario(title="uploads", given=["g"], when=["w"], then=["t"], prd_requirement_ids=["FR-99"])],
            performance_plans=[PerformancePlan(title="load", scenario="s", load_profile="100 users", metric="p95", threshold="< 2 s")],
            security_cases=[SecurityCase(title="malware", abuse_case="malware UPLOAD", steps=["s"],
                                         expected_secure_behavior="rejected", controls_verified=["SEC-1", "SEC-9"])],
        )

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")


def _run(tmp_path, dev=None, author=None, existing=None):
    author = author or StubAuthor()
    workflow = QaWorkflow(author, ApprovingReviewer(), ScriptedInteraction(answers=[""]), tmp_path, 5, StubJudge())
    result = workflow.run(chain.prd(), chain.srs(), chain.architecture(), chain.lld(), dev or chain.dev(), existing)
    return result, author


def test_contexts_are_built_from_the_traceability_graph():
    contexts = dict(requirement_contexts(
        chain.prd(), chain.srs(), chain.architecture(), chain.lld(), chain.dev(), QaAnalysis(summary="s"), [], []
    ))
    fr = contexts["FR-1"]
    assert [a.id for a in fr.apis] == ["API-1"] and fr.code_files == ["app/main.py"]
    assert fr.unit_test_files == ["tests/test_main.py"] and [c.id for c in fr.security_controls] == ["SEC-1"]
    assert [p.id for p in fr.prd_requirements] == ["FR-1"] and [s.id for s in fr.user_stories] == ["US-1"]
    assert contexts["NFR-1"].code_files == []  # a confirmed quality target that nothing was designed for


def test_tests_are_linked_to_requirements_apis_code_controls_and_abuse_cases(tmp_path):
    result, _ = _run(tmp_path)
    qa = json.loads(Path(result["output_path"]).read_text())["testing"]

    case = qa["cases"][0]
    assert (case["id"], case["requirement_ids"], case["api_ids"], case["code_paths"], case["component_ids"]) == (
        "TC-1", ["FR-1"], ["API-1"], ["app/main.py"], ["COMP-1"])
    assert qa["uat_scenarios"][0]["prd_requirement_ids"] == ["FR-1"]  # an unknown id falls back to the real parent
    security = qa["security_cases"][0]
    assert security["controls_verified"] == ["SEC-1"] and security["abuse_case_id"] == "ABUSE-1"
    assert any("unknown API 'GET /v1/ghost'" in w for w in qa["warnings"])
    assert any("unknown file 'ghost.py'" in w for w in qa["warnings"])
    assert any("unknown controls" in w for w in qa["warnings"])
    assert qa["coverage"][0] == {"requirement_id": "FR-1", "cases": ["TC-1"], "uat": ["UAT-1"],
                                 "performance": ["PERF-1"], "security": ["SECT-1"]}
    assert qa["strategy"]["objectives"] == ["verify every requirement"]


def test_security_report_scans_the_code_and_lists_untested_controls_and_abuse_cases(tmp_path):
    dev = chain.dev("import hashlib\nh = hashlib.md5(b'x')\nresult = eval(user_input)\nAPI_KEY = 'abcd1234efgh5678'\n")
    result, _ = _run(tmp_path, dev=dev)
    report = json.loads(Path(result["output_path"]).read_text())["testing"]["security_report"]

    assert {(f["rule"], f["line"]) for f in report["static_findings"]} == {
        ("weak-hash", 2), ("dynamic-eval", 3), ("hard-coded-secret", 4)}
    assert "not executed" in report["scope"]
    assert report["uncovered"] == []  # SEC-1 and the abuse case are both covered by the generated security case


def test_update_reuses_unchanged_requirements_and_retests_when_the_code_changes(tmp_path):
    from existing import load_existing
    from testing.models import QaDocument

    _run(tmp_path)
    existing = load_existing(tmp_path, "testing", QaDocument, QaAnalysis)
    result, author = _run(tmp_path, dev=chain.dev("def upload():\n    return 2\n"), existing=existing)
    saved = json.loads(Path(result["output_path"]).read_text())

    assert author.created == [] and author.updated == ["FR-1"]  # only the requirement whose code changed
    assert {i["source_id"]: i["action"] for i in saved["items"]} == {"FR-1": "updated", "NFR-1": "reused"}
    assert saved["testing"]["cases"][0]["id"] == "TC-1"  # ids stay stable


def _context(kind="functional", **details):
    contexts = dict(requirement_contexts(
        chain.prd(), chain.srs(), chain.architecture(), chain.lld(), chain.dev(), QaAnalysis(summary="s"), [], []
    ))
    context = contexts["FR-1"] if kind == "functional" else contexts["NFR-1"]
    return context.model_copy(update={"requirement": context.requirement.model_copy(update={"details": details})}) if details else context


def _issues(context, derived):
    return {f.issue for f in check_qa(context, derived)}


def test_review_checks_catch_missing_and_made_up_links():
    context = _context()
    good = QaElementSet(
        cases=[QaCase(title="ok", level=CaseLevel.SYSTEM, steps=["s"], expected_result="e", apis=["POST /v1/documents"],
                      code_paths=["app/main.py"])],
        uat_scenarios=[UatScenario(title="u", given=["g"], when=["w"], then=["t"])],
        security_cases=[SecurityCase(title="sec", steps=["s"], expected_secure_behavior="b", controls_verified=["SEC-1"])],
    )
    assert check_qa(context, good) == []

    assert "No test case covers this requirement" in _issues(context, QaElementSet())
    bad = QaElementSet(cases=[QaCase(title="x", level=CaseLevel.UNIT, apis=["GET /nope"], code_paths=["nope.py"])])
    assert {"Unknown API 'GET /nope'", "Unknown code file 'nope.py'",
            "Test case lacks steps or an expected result"} <= _issues(context, bad)


def test_performance_requirements_need_a_performance_plan():
    context = _context("non_functional", category="availability", metric="availability", target="99.95%")
    assert "A performance-related requirement has no performance plan" in _issues(context, QaElementSet())
    plan = PerformancePlan(title="p", scenario="s", load_profile="1000 users", metric="uptime", threshold="99.95%")
    assert _issues(context, QaElementSet(performance_plans=[plan])) == set()


def test_code_excerpts_are_bounded_and_marked_when_cut():
    from dev.models import SourceFile
    from testing.sources import _excerpts

    files = [SourceFile(path="a.py", content="x" * 2000), SourceFile(path="b.py", content="y" * 100)]
    result = _excerpts(files, budget=1600, per_file=1500)
    assert result["a.py"].endswith("(truncated)") and len(result["a.py"]) < 1600
    assert result["b.py"] == "y" * 100
    assert sum(len(t) for t in result.values()) <= 1600 + 20
