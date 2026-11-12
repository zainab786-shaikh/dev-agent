"""Agent that reviews the tests of one software requirement: automatic traceability checks, then an LLM review."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block
from ..models import ReviewFinding, ReviewResult, Severity
from ..review_loop import ArtifactReviewer
from .models import QaContext, QaElementSet

PERFORMANCE_CATEGORIES = {"performance", "scalability", "availability", "reliability"}


def _finding(severity: Severity, area: str, issue: str, recommendation: str) -> ReviewFinding:
    return ReviewFinding(severity=severity, area=area, issue=issue, recommendation=recommendation)


def check_qa(context: QaContext, derived: QaElementSet) -> list[ReviewFinding]:
    """Deterministic checks that the tests are complete and only link to things that exist."""
    high, medium = Severity.HIGH, Severity.MEDIUM
    findings: list[ReviewFinding] = []
    requirement = context.requirement
    api_refs = {f"{a.method.upper()} {a.path}".lower() for a in context.apis}
    files = {*context.code_files, *context.unit_test_files}
    controls = {c.id for c in context.security_controls}

    for c in derived.cases:
        if not c.steps or not c.expected_result.strip():
            findings.append(_finding(high, c.title, "Test case lacks steps or an expected result", "Add both"))
        for ref in c.apis:
            if " ".join(ref.split()).lower() not in api_refs:
                findings.append(_finding(high, c.title, f"Unknown API '{ref}'", "Use only 'METHOD /path' from the list"))
        for path in c.code_paths:
            if path not in files:
                findings.append(_finding(high, c.title, f"Unknown code file '{path}'", "Use only the listed files"))
    for p in derived.performance_plans:
        if not p.threshold.strip() or not p.load_profile.strip():
            findings.append(_finding(high, p.title, "Performance plan lacks a load profile or threshold", "State both, from the requirement target"))
    for s in derived.security_cases:
        for control in s.controls_verified:
            if control not in controls:
                findings.append(_finding(high, s.title, f"Unknown security control '{control}'", "Use only the listed control ids"))
        if not s.steps or not s.expected_secure_behavior.strip():
            findings.append(_finding(high, s.title, "Security case lacks steps or the expected secure behavior", "Add both"))
    for u in derived.uat_scenarios:
        if not (u.given and u.when and u.then):
            findings.append(_finding(medium, u.title, "UAT scenario is missing Given, When or Then", "Write all three"))

    category = str(requirement.details.get("category", ""))
    if requirement.kind in ("functional", "interface") and not derived.cases:
        findings.append(_finding(high, requirement.id, "No test case covers this requirement", "Add test cases"))
    if requirement.kind == "functional" and context.prd_requirements and not derived.uat_scenarios:
        findings.append(_finding(medium, requirement.id, "No UAT scenario for a product requirement", "Add a UAT scenario"))
    if requirement.kind == "non_functional":
        if category in PERFORMANCE_CATEGORIES and not derived.performance_plans:
            findings.append(_finding(high, requirement.id, "A performance-related requirement has no performance plan", "Add one with the target as the threshold"))
        elif category == "security" and not derived.security_cases:
            findings.append(_finding(high, requirement.id, "A security requirement has no security case", "Add security cases"))
        elif not (derived.cases or derived.performance_plans or derived.security_cases):
            findings.append(_finding(high, requirement.id, "Nothing verifies this requirement", "Add tests"))
    if requirement.kind == "functional" and context.security_controls and not derived.security_cases:
        findings.append(_finding(medium, requirement.id, "Security controls apply but no security case exists", "Add a security case"))
    return findings


class QaReviewerAgent(BaseAgent, ArtifactReviewer[QaContext, QaElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "QaReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict QA reviewer. You check that tests fully verify their requirement, trace to the "
            "design and code, and are precise and executable. Respond only with JSON matching the given schema."
        )

    def review(self, context: QaContext, artifact: QaElementSet) -> ReviewResult:
        problems = check_qa(context, artifact)
        if any(p.severity == Severity.HIGH for p in problems):
            return ReviewResult(
                approved=False, summary="Automatic traceability checks failed; fix these first", findings=problems
            )

        prompt = (
            f"Software requirement:\n{context.requirement.model_dump_json()}\n\n"
            f"APIs:\n[{','.join(a.model_dump_json() for a in context.apis)}]\n\n"
            f"Source files:\n{context.code_files}\n\n"
            f"Code of the linked files (excerpts):\n"
            + "\n".join(f"--- {p}\n{t}" for p, t in context.code_excerpts.items())
            + "\n\n"
            f"Test strategy:\n{context.analysis.strategy.model_dump_json()}\n\n"
            f"Confirmed decisions:\n{decided_block(context.decisions)}\n\n"
            f"Tests:\n{artifact.model_dump_json()}\n\n"
            "Review for: parts of the requirement or its acceptance criteria that no test verifies; missing "
            "negative or boundary cases; error responses of the APIs that are not tested; vague steps or "
            "expected results that cannot be checked; performance thresholds that differ from the "
            "requirement target; UAT scenarios written in technical rather than business language; security "
            "cases that do not match the abuse case or control they claim; tests that contradict the "
            "strategy or the confirmed decisions; duplicates. Give each finding a severity "
            "(high/medium/low), the affected test title, the issue, and a concrete recommendation. Set "
            "approved=true only if no high or medium issue remains."
        )
        review = self._invoke(ReviewResult, prompt)
        return review.model_copy(update={"findings": [*problems, *review.findings]})
