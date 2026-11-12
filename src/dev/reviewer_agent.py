"""Agent that reviews generated code: automatic safety checks first, then an LLM review."""
from __future__ import annotations

from ..agents.base import BaseAgent
from ..agents.prompts import decided_block
from ..models import ReviewResult, Severity
from ..review_loop import ArtifactReviewer
from .checks import check_element_set
from .models import DevContext, DevElementSet


class DevReviewerAgent(BaseAgent, ArtifactReviewer[DevContext, DevElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "DevReviewerAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a strict code reviewer. You check that code implements its design, handles errors, "
            "is secure, and is covered by meaningful isolated unit tests. Respond only with JSON matching "
            "the given schema."
        )

    def review(self, context: DevContext, artifact: DevElementSet) -> ReviewResult:
        problems = check_element_set(artifact)
        if any(p.severity == Severity.HIGH for p in problems):
            return ReviewResult(
                approved=False, summary="Automatic checks failed; fix these before the detailed review", findings=problems
            )

        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        prompt = (
            f"Component:\n{context.component.model_dump_json()}\n\n"
            f"Detailed design it must implement:\n{context.design.model_dump_json()}\n\n"
            f"Server APIs the web client calls:\n{dump(context.server_apis)}\n\n"
            f"Server data contracts the web client uses:\n{dump(context.server_contracts)}\n\n"
            f"Tables the API server's ORM entities map:\n{dump(context.data_tables)}\n\n"
            f"Shared data contracts:\n{dump(context.shared_contracts)}\n\n"
            f"Layout conventions:\n" + "\n".join(f"- {c}" for c in context.analysis.layout) + "\n\n"
            f"Confirmed decisions:\n{decided_block(context.decisions)}\n\n"
            f"Code and tests:\n{artifact.model_dump_json()}\n\n"
            "Review for: APIs, classes or methods of the design that are not implemented or have different "
            "names, signatures, status codes or error handling; missing input validation; missing imports or "
            "undefined names; unsafe patterns (injection, unvalidated input, hard-coded secrets, "
            "disabled TLS verification); unit tests missing for a public function or for an error path; "
            "tests that need a real database, network or other component; tests that assert nothing; "
            "files that break the layout conventions or the decided language and test framework. Give each "
            "finding a severity (high/medium/low), the affected file path, the issue, and a concrete "
            "recommendation. Set approved=true only if no high or medium issue remains."
        )
        return self._invoke(ReviewResult, prompt)
