"""Agent that sets the design conventions and details each component's implementation."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..architecture.models import ArchitectureDocument
from ..models import DecisionRecord, ReviewResult
from ..review_loop import ArtifactAuthor
from ..srs.models import SoftwareRequirementsDocument
from .models import LldAnalysis, LldContext, LldElementSet
from .sources import lld_digest


class LldAuthorAgent(BaseAgent, ArtifactAuthor[LldContext, LldElementSet]):
    profile_aware = True

    @property
    def name(self) -> str:
        return "LldAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a technical lead who writes implementation-level designs: API specifications with "
            "request/response formats, database schemas, service interfaces and classes, data contracts, "
            "sequence flows and error handling. Respond only with JSON matching the given schema."
        )

    def analyze(
        self,
        architecture: ArchitectureDocument,
        srs: SoftwareRequirementsDocument,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[LldAnalysis],
    ) -> LldAnalysis:
        prompt = (
            f"Architecture and requirements:\n{lld_digest(architecture, srs)}\n\n"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous proposal:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed conventions and contracts (keep them unless the inputs or feedback require "
            f"a change):\n{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the implementation approach in two or three sentences.\n"
            "2. List the conventions every component follows: API versioning, naming, pagination, "
            "idempotency, id and timestamp formats, authentication header, validation rules.\n"
            "3. Define the shared data contracts used across components, always including the standard "
            "error response and the pagination envelope, with typed fields.\n"
            "4. Ask clarifying questions about facts that cannot be inferred (max 5; empty if none).\n"
            "5. Propose implementation-level decisions that are still open, e.g. API style (REST, gRPC, "
            "GraphQL), error response format, id strategy (UUID, ULID, sequence), database technology per "
            "component, event serialization, how callers authenticate.\n"
            f"{DECISION_INSTRUCTIONS}"
        )
        return self._invoke(LldAnalysis, prompt)

    def create(self, context: LldContext) -> LldElementSet:
        return self._invoke(LldElementSet, self._base_prompt(context) + self._instructions(context))

    def update(self, context: LldContext, existing: LldElementSet) -> LldElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Existing detailed design of this component:\n{existing.model_dump_json()}\n\n"
            + "Update it so it reflects the component, architecture, decisions and conventions above, and "
            "any user feedback in the clarifications. Keep everything still valid (including names and "
            "paths), add what is new, change what conflicts, remove what is obsolete.\n"
            + self._instructions(context)
        )
        return self._invoke(LldElementSet, prompt)

    def revise(self, context: LldContext, artifact: LldElementSet, review: ReviewResult) -> LldElementSet:
        prompt = (
            self._base_prompt(context)
            + f"Current detailed design:\n{artifact.model_dump_json()}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions(context)
        )
        return self._invoke(LldElementSet, prompt)

    def _base_prompt(self, context: LldContext) -> str:
        dump = lambda items: "[" + ",".join(i.model_dump_json() for i in items) + "]"  # noqa: E731
        return (
            f"Component to design:\n{context.component.model_dump_json()}\n\n"
            f"Other components (for references only):\n{dump(context.other_components)}\n\n"
            f"Interactions of this component:\n{dump(context.interactions)}\n\n"
            f"High-level design elements:\n{dump(context.design_elements)}\n\n"
            f"Security controls:\n{dump(context.security_controls)}\n\n"
            f"Deployment elements:\n{dump(context.deployment_elements)}\n\n"
            f"Server APIs the web client calls (use exactly these):\n{dump(context.server_apis)}\n\n"
            f"Server data contracts the web client uses:\n{dump(context.server_contracts)}\n\n"
            f"Tables of the data tier the API server maps with the ORM:\n{dump(context.data_tables)}\n\n"
            f"Architecture decisions:\n{dump(context.architecture_decisions)}\n\n"
            f"Software requirements this component serves:\n{dump(context.requirements)}\n\n"
            f"Conventions and shared contracts (reuse their names, do not redefine them):\n"
            f"{context.analysis.confirmed_json(exclude={'summary'})}\n\n"
            f"Confirmed implementation decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
        )

    @staticmethod
    def _tier_guidance(context: LldContext) -> str:
        tier = context.component.tier.strip().lower()
        if tier == "client":
            return (
                "This is the web client: describe its screens (route, UI components, loading/empty/error "
                "states, validation rules, and the server APIs each calls, exactly as 'METHOD /path' from the "
                "list), client services such as the API client and state management, and view-model "
                "contracts. It has no tables and no server endpoints. "
            )
        if tier == "api":
            return (
                "This is the API server: describe endpoints with request and response contracts, status codes "
                "and errors in the shared error contract, controller, service and repository classes, and ORM "
                "entity classes that map the listed data tier tables with the confirmed ORM. It has no "
                "screens and defines no tables of its own. "
            )
        if tier == "data":
            return (
                "This is the data tier: describe tables with typed columns, keys, constraints and indexes, "
                "set entity to the ORM entity name for each table, and the migration approach. It has no "
                "endpoints or screens. "
            )
        return ""

    @classmethod
    def _instructions(cls, context: LldContext) -> str:
        return cls._tier_guidance(context) + cls._generic_instructions()

    @staticmethod
    def _generic_instructions() -> str:
        return (
            "Write the detailed design for THIS component only. Output: data contracts for its request, "
            "response, event and entity shapes (typed fields, required flags, constraints); API "
            "specifications (method, path, parameters, request and response contract names, success status, "
            "error responses with codes and conditions, authentication, and the requirement ids served); "
            "database tables with typed columns, keys, foreign keys as 'table.column' and indexes for the "
            "access patterns, only for data this component owns; classes and service interfaces with "
            "typed attributes, method signatures and the errors they raise; sequence diagrams for the key "
            "flows including a failure path, using only this component, its classes and the listed other "
            "components or external systems as participants; and error handling rules (scenario, error "
            "code, handling, retry/timeout, logging). Reference contracts by name and use the confirmed "
            "technologies. Leave a list empty when the component does not need it, e.g. a pure client has "
            "no tables. Names are what identifies an item, so keep them stable."
        )
