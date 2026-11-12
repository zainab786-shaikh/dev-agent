"""Agent that decides the tooling and git workflow, then writes code and unit tests per component."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..architecture.models import ArchitectureDocument
from ..lld.models import LldDocument
from ..models import DecisionRecord, ReviewFinding, ReviewResult
from ..review_loop import ArtifactAuthor
from .models import DevAnalysis, DevContext, DevDocument, DevElementSet, DevScaffold, ProjectFileSet, SourceFile
from .sources import dev_digest


class DevAuthorAgent(BaseAgent, ArtifactAuthor[DevContext, DevElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "DevAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior software engineer. You implement a detailed design as clean, working source "
            "code with unit tests, and you define a clear git workflow. Never put secrets in code. Respond "
            "only with JSON matching the given schema."
        )

    def analyze(
        self,
        architecture: ArchitectureDocument,
        lld: LldDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[DevAnalysis],
    ) -> DevAnalysis:
        prompt = (
            f"Architecture and detailed design:\n{dev_digest(architecture, lld)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous proposal:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed analysis (keep it unless the inputs or feedback require a change):\n"
            f"{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the implementation approach in two or three sentences.\n"
            "2. Ask clarifying questions about facts that cannot be inferred, e.g. team skills, mandated "
            "language, CI platform (max 5; empty if none).\n"
            "3. Propose the open decisions. The languages, frameworks, ORM and database are already fixed by "
            "the application profile; propose only the unit test framework for each tier, the dependency "
            "manager and lint/format tooling for each tier, the CI platform, the git branching model "
            "(trunk-based vs gitflow) and the commit message convention.\n"
            f"{DECISION_INSTRUCTIONS}\n"
            "Do not fill in layout or git workflow yet; they are written after the decisions are made."
        )
        return self._invoke(DevAnalysis, prompt)

    def design_scaffold(
        self,
        architecture: ArchitectureDocument,
        lld: LldDocument,
        clarifications: list[str],
        decisions: list[DecisionRecord],
        baseline: Optional[DevAnalysis],
    ) -> DevScaffold:
        current = baseline.model_dump_json(include={"layout", "git_workflow"}) if baseline else "none"
        prompt = (
            f"Architecture and detailed design:\n{dev_digest(architecture, lld)}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(decisions)}\n\n"
            f"User clarifications:\n{lines(clarifications)}\n\n"
            f"Current layout and git workflow (keep them unless the decisions require a change):\n{current}\n\n"
            "Define: (1) layout conventions for one repository with a folder per tier (web client, API "
            "server, database migrations): project structure inside each tier, module and file naming, where "
            "unit tests live and how they are named, error handling, logging, configuration through "
            "environment variables, and CI jobs per tier; (2) the git workflow: branching model, main branch, branch name pattern using "
            "{component}, commit convention and a one-line commit template using {component} and {name}, "
            "and the pull request and CI rules."
        )
        return self._invoke(DevScaffold, prompt)

    def create(self, context: DevContext) -> DevElementSet:
        return self._invoke(DevElementSet, self._base_prompt(context) + self._instructions(context))

    def update(self, context: DevContext, existing: DevElementSet) -> DevElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing code and tests of this component:\n{existing.model_dump_json()}\n\n"
            + "Update them so they implement the detailed design above. Keep everything still valid "
            "(including file paths and names), change what conflicts, add what is missing, remove what is "
            "obsolete. Return the complete files.\n"
            + self._instructions(context)
        )
        return self._invoke(DevElementSet, prompt)

    def revise(self, context: DevContext, artifact: DevElementSet, review: ReviewResult) -> DevElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current code and tests:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good; return the complete files):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions(context)
        )
        return self._invoke(DevElementSet, prompt)

    def project_files(
        self,
        analysis: DevAnalysis,
        decisions: list[DecisionRecord],
        document: DevDocument,
        existing: list[SourceFile],
        problems: list[ReviewFinding],
    ) -> ProjectFileSet:
        summary = {
            "title": document.title,
            "components": [
                {"component": p.component_id, "branch": p.branch, "files": p.files} for p in document.commit_plan
            ],
            "dependencies": document.component_dependencies,
        }
        prompt = (
            f"Layout conventions:\n{lines(analysis.layout)}\n\n"
            f"Git workflow:\n{analysis.git_workflow.model_dump_json()}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(decisions)}\n\n"
            f"Generated components, their files and their dependencies:\n{summary}\n\n"
            f"Existing project files (keep what is still valid):\n"
            f"{'[' + ','.join(f.model_dump_json() for f in existing) + ']' if existing else 'none'}\n\n"
            + (f"Problems found in the previous attempt (fix them):\n{[p.model_dump() for p in problems]}\n\n" if problems else "")
            + "Write the project-level files: the dependency manifest of each tier in the format of its confirmed "
            "stack and package manager (one per tier, each listing ALL dependencies of that tier), a README "
            "(overview, setup, how to run the unit tests, the git workflow), .gitignore, a CI pipeline "
            "definition that runs the unit tests on pull requests (for the decided CI platform), and a "
            "pull request template. Use relative paths, no secrets, and do not repeat any component file."
        )
        return self._invoke(ProjectFileSet, prompt)

    def _base_prompt(self, context: DevContext) -> str:
        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        return (
            f"Component to implement:\n{context.component.model_dump_json()}\n\n"
            f"Other components (for references only):\n{dump(context.other_components)}\n\n"
            f"Detailed design of this component (implement it exactly):\n{context.design.model_dump_json()}\n\n"
            f"Shared data contracts:\n{dump(context.shared_contracts)}\n\n"
            f"Server APIs the web client calls (call exactly these):\n{dump(context.server_apis)}\n\n"
            f"Server data contracts the web client uses:\n{dump(context.server_contracts)}\n\n"
            f"Tables the API server's ORM entities map:\n{dump(context.data_tables)}\n\n"
            f"Architecture decisions:\n{dump(context.architecture_decisions)}\n\n"
            f"Layout conventions:\n{lines(context.analysis.layout)}\n\n"
            f"Confirmed decisions, including language and test framework (follow them):\n"
            f"{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _tier_guidance(context: DevContext) -> str:
        tier = context.component.tier.strip().lower()
        if tier == "client":
            return (
                "This is the web client, written in the confirmed framework with TypeScript: routes and "
                "screens, components, services or hooks that call exactly the listed server APIs with the "
                "contracts as TypeScript types, loading, empty and error states, input validation, an API "
                "base URL from environment configuration. Put the files in the web client folder. "
            )
        if tier == "api":
            return (
                "This is the API server, written in the confirmed stack: controllers or routes, services, "
                "repositories, ORM entities mapping the listed tables with the confirmed ORM, request "
                "validation, authentication as specified, and errors mapped to the shared error contract. "
                "Put the files in the API server folder. "
            )
        if tier == "data":
            return (
                "This is the data tier: database migration or schema scripts in the format of the confirmed "
                "ORM and engine that create the tables, keys, constraints and indexes, plus seed data if "
                "needed. Put the files in the database folder. "
            )
        return ""

    @classmethod
    def _instructions(cls, context: DevContext) -> str:
        return cls._tier_guidance(context) + cls._generic_instructions()

    @staticmethod
    def _generic_instructions() -> str:
        return (
            "Write complete source files and unit test files for THIS component only, in the decided "
            "language and test framework, following the layout conventions. Implement every API, class and "
            "method of the design with the specified names, signatures, status codes, validation and error "
            "handling. Unit tests must cover the success path and each error path of every public function "
            "or method, be isolated (mock databases, network and other components) and need no external "
            "services. Never hard-code secrets: read configuration from environment variables. Use "
            "relative paths with forward slashes. List third-party packages in dependencies. Each file "
            "must contain complete, syntactically valid code with all imports."
        )
