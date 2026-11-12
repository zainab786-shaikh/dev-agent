"""Agent that reviews the detailed design of one component."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block
from ..models import ReviewFinding, ReviewResult, Severity
from ..review_loop import ArtifactReviewer
from .models import LldContext, LldElementSet


def _high(area: str, issue: str, recommendation: str) -> ReviewFinding:
    return ReviewFinding(severity=Severity.HIGH, area=area, issue=issue, recommendation=recommendation)


def check_lld(context: LldContext, derived: LldElementSet) -> list[ReviewFinding]:
    """Deterministic checks of the links between the tiers and of the contracts the APIs use."""
    findings: list[ReviewFinding] = []
    tier = context.component.tier.strip().lower()
    known_apis = {" ".join(f"{a.method} {a.path}".split()).lower() for a in context.server_apis}
    contracts = {c.name.lower() for c in [*context.analysis.shared_contracts, *derived.data_contracts, *context.server_contracts]}

    for screen in derived.ui_screens:
        if tier != "client":
            findings.append(_high(screen.name, "Only the web client has screens", "Remove the screens from this component"))
        for call in screen.api_calls:
            if " ".join(call.split()).lower() not in known_apis:
                findings.append(_high(screen.name, f"Calls unknown server API '{call}'", "Use exactly 'METHOD /path' from the server APIs"))
    if tier == "client" and (derived.api_specifications or derived.tables):
        findings.append(_high(context.component.name, "The web client defines endpoints or tables", "Describe screens and client services instead"))
    if tier == "data" and derived.api_specifications:
        findings.append(_high(context.component.name, "The data tier defines API endpoints", "Describe tables and migrations instead"))
    for api in derived.api_specifications:
        for name in (api.request_contract, api.response_contract):
            if name and name.lower() not in contracts:
                findings.append(_high(f"{api.method} {api.path}", f"Contract '{name}' is not defined", "Define it or use a shared contract"))
    return findings


class LldReviewerAgent(BaseAgent, ArtifactReviewer[LldContext, LldElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "LldReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict technical design reviewer. You check that a component's detailed design is "
            "implementable, consistent with the architecture and conventions, and complete. Respond only "
            "with JSON matching the given schema."
        )

    def review(self, context: LldContext, artifact: LldElementSet) -> ReviewResult:
        problems = check_lld(context, artifact)
        if problems:
            return ReviewResult(approved=False, summary="Automatic checks failed; fix these first", findings=problems)

        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        prompt = (
            f"Component:\n{context.component.model_dump_json()}\n\n"
            f"Interactions:\n{dump(context.interactions)}\n\n"
            f"Security controls:\n{dump(context.security_controls)}\n\n"
            f"Requirements served:\n{dump(context.requirements)}\n\n"
            f"Conventions and shared contracts:\n{context.analysis.confirmed_json(exclude={'summary'})}\n\n"
            f"Confirmed implementation decisions:\n{decided_block(context.decisions)}\n\n"
            f"Detailed design:\n{artifact.model_dump_json()}\n\n"
            "Review for: requirements served that no API, class or flow covers; APIs whose request or "
            "response contract is not defined (in this design or the shared contracts); contract fields "
            "without types; missing success status or error responses, or errors not using the shared error "
            "contract; endpoints that ignore the authentication convention or the security controls; tables "
            "without a primary key, foreign keys pointing at unknown tables, or no index for an obvious "
            "lookup; classes or methods using undefined types; sequence diagrams with participants that "
            "are neither this component, its classes, a listed component nor an external system, or with "
            "no failure path; no error handling for timeouts or validation; choices that contradict the "
            "confirmed decisions or technologies; naming that breaks the conventions; duplicates. Give each "
            "finding a severity (high/medium/low), the affected name, the issue, and a concrete "
            "recommendation. Set approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
