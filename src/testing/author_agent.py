"""Agent that decides the test strategy and writes tests per software requirement."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..architecture.models import ArchitectureDocument
from ..dev.models import DevDocument
from ..models import DecisionRecord, ReviewResult
from ..prd.models import ProductRequirementsDocument
from ..review_loop import ArtifactAuthor
from ..srs.models import SoftwareRequirementsDocument
from .models import QaAnalysis, QaContext, QaElementSet, QaStrategy
from .sources import qa_digest


def _code_block(excerpts: dict[str, str]) -> str:
    return "\n".join(f"--- {path}\n{text}" for path, text in excerpts.items()) or "none"


class QaAuthorAgent(BaseAgent, ArtifactAuthor[QaContext, QaElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "QaAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior QA and test architect. You define how a product is verified and write precise, "
            "traceable test cases, UAT scenarios, performance test plans and security tests. Respond only "
            "with JSON matching the given schema."
        )

    def analyze(
        self,
        prd: ProductRequirementsDocument,
        srs: SoftwareRequirementsDocument,
        architecture: ArchitectureDocument,
        dev: DevDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[QaAnalysis],
    ) -> QaAnalysis:
        prompt = (
            f"Requirements, architecture and code:\n{qa_digest(prd, srs, architecture, dev)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous proposal:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed analysis (keep it unless the inputs or feedback require a change):\n"
            f"{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the testing challenge in two or three sentences.\n"
            "2. Ask clarifying questions about facts that cannot be inferred, e.g. available environments, "
            "production-like data, who performs UAT (max 5; empty if none).\n"
            "3. Propose the open decisions: integration and system test approach, performance test tool "
            "and environment, security testing tools (SAST, DAST, dependency scanning), UAT approach, "
            "test data strategy, defect tracking.\n"
            f"{DECISION_INSTRUCTIONS}\n"
            "Do not fill in the strategy yet; it is written after the decisions are made."
        )
        return self._invoke(QaAnalysis, prompt)

    def design_strategy(
        self,
        prd: ProductRequirementsDocument,
        srs: SoftwareRequirementsDocument,
        architecture: ArchitectureDocument,
        dev: DevDocument,
        clarifications: list[str],
        decisions: list[DecisionRecord],
        baseline: Optional[QaAnalysis],
    ) -> QaStrategy:
        current = baseline.strategy.model_dump_json() if baseline else "none"
        prompt = (
            f"Requirements, architecture and code:\n{qa_digest(prd, srs, architecture, dev)}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(decisions)}\n\n"
            f"User clarifications:\n{lines(clarifications)}\n\n"
            f"Current strategy (keep it unless the decisions require a change):\n{current}\n\n"
            "Write the test strategy: objectives, scope in and out, the test levels (unit, integration, "
            "system, end-to-end, UAT, performance, security) each with purpose, tools, entry and exit "
            "criteria (web client: component and browser end-to-end tests; API server: API and integration "
            "tests against a test database; data tier: migration and query tests), environments, test data, automation approach, performance approach, security "
            "approach, defect management (severity levels, triage, release exit rules) and risks."
        )
        return self._invoke(QaStrategy, prompt)

    def create(self, context: QaContext) -> QaElementSet:
        return self._invoke(QaElementSet, self._base_prompt(context) + self._instructions())

    def update(self, context: QaContext, existing: QaElementSet) -> QaElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing tests for this requirement:\n{existing.model_dump_json()}\n\n"
            + "Update them so they cover the requirement, code and design above. Keep everything still valid "
            "(including titles and wording), add what is missing, change what conflicts, remove what is "
            "obsolete.\n"
            + self._instructions()
        )
        return self._invoke(QaElementSet, prompt)

    def revise(self, context: QaContext, artifact: QaElementSet, review: ReviewResult) -> QaElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current tests:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions()
        )
        return self._invoke(QaElementSet, prompt)

    def _base_prompt(self, context: QaContext) -> str:
        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        return (
            f"Software requirement to verify:\n{context.requirement.model_dump_json()}\n\n"
            f"Product requirements it comes from (use their ids for UAT):\n{dump(context.prd_requirements)}\n\n"
            f"User stories:\n{dump(context.user_stories)}\n\n"
            f"Abuse cases (use their exact titles):\n{dump(context.abuse_cases)}\n\n"
            f"Components:\n{dump(context.components)}\n\n"
            f"APIs that implement it:\n{dump(context.apis)}\n\n"
            f"Error handling rules:\n{dump(context.error_rules)}\n\n"
            f"Architecture design elements:\n{dump(context.design_elements)}\n\n"
            f"Security controls (use their ids):\n{dump(context.security_controls)}\n\n"
            f"Deployment elements:\n{dump(context.deployment_elements)}\n\n"
            f"Source files that implement it:\n{lines(context.code_files)}\n\n"
            f"Existing unit test files:\n{lines(context.unit_test_files)}\n\n"
            f"Code of these files (excerpts; test what it really does):\n{_code_block(context.code_excerpts)}\n\n"
            f"Test strategy:\n{context.analysis.strategy.model_dump_json()}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _instructions() -> str:
        return (
            "Write the tests for THIS requirement only, choosing levels by tier: browser end-to-end and "
            "component tests for the web client, API and integration tests for the API server, migration and "
            "query tests for the data tier. Use local ids TC-n, UAT-n, PERF-n, SECT-n (they "
            "are renumbered later). Test cases: positive, negative and boundary cases with preconditions, "
            "steps and an expected result; set apis exactly as 'METHOD /path' from the list and code_paths "
            "from the listed files only. UAT scenarios: business-language Given/When/Then for a user, with "
            "acceptance criteria and the product requirement ids they accept. Performance plans for "
            "requirements with a measurable target (response time, load, availability): workload, metric "
            "and a threshold taken from the target, tool and environment. Security cases for the listed "
            "abuse cases and controls that apply (use exact abuse case titles and control ids), with the "
            "OWASP category, steps and the expected secure behavior. Do not invent APIs, files, controls "
            "or abuse cases. Leave a list empty when it does not apply to this requirement."
        )
