"""Agent that analyzes the product requirement and creates/updates/revises the PRD."""
from __future__ import annotations

from typing import Optional

from ..agents.base import BaseAgent
from ..agents.prompts import DECISION_INSTRUCTIONS, baseline_block, decided_block, lines
from ..models import DecisionRecord, ReviewResult
from ..review_loop import ArtifactAuthor
from .digest import prd_digest
from .models import ProductContext, ProductRequirementsAnalysis, ProductRequirementsDocument


class PrdAuthorAgent(BaseAgent, ArtifactAuthor[ProductContext, ProductRequirementsDocument]):
    @property
    def name(self) -> str:
        return "PrdAuthorAgent"

    @property
    def system_prompt(self) -> str:
        return (
            "You are a senior product analyst. You turn rough product requirements into a precise, "
            "testable product requirements document (PRD). Respond only with JSON matching the given schema."
        )

    def analyze(
        self,
        product_requirement: str,
        clarifications: list[str],
        feedback: str,
        decisions: list[DecisionRecord],
        baseline: Optional[ProductRequirementsAnalysis],
        existing: Optional[ProductRequirementsDocument],
    ) -> ProductRequirementsAnalysis:
        existing_block = (
            f"Existing PRD (the requirement above is a new or changed input to it):\n{prd_digest(existing)}\n\n"
            if existing
            else ""
        )
        prompt = (
            f"Product requirement:\n{product_requirement}\n\n{existing_block}"
            f"Already answered by the user (do not ask again):\n{lines(clarifications)}\n\n"
            f"User feedback on the previous analysis:\n{feedback or 'none'}\n\n"
            f"Decisions already made:\n{decided_block(decisions)}\n\n"
            f"Current confirmed analysis (keep it unless the inputs or feedback require a change):\n"
            f"{baseline_block(baseline)}\n\n"
            "Tasks:\n"
            "1. Summarize the product requirement.\n"
            "2. Identify who the users are (roles with goals).\n"
            "3. List clarifying questions for missing facts, including unclear users, features or expected "
            "behavior (max 5; empty if none).\n"
            "4. List non-functional requirements (performance, security, usability, reliability, etc.).\n"
            "5. List abuse cases: how the system could be misused or attacked, with a mitigation.\n"
            "6. Propose business-level decisions where several approaches are possible, e.g. MVP scope, "
            "user sign-in approach, roles. The product is a web application (web client, API server, "
            "database); do not propose platform or technology choices.\n"
            f"{DECISION_INSTRUCTIONS}\n"
            "Focus on business functionality, not technology choices."
        )
        return self._invoke(ProductRequirementsAnalysis, prompt)

    def create(self, context: ProductContext) -> ProductRequirementsDocument:
        return self._invoke(ProductRequirementsDocument, self._base_prompt(context) + self._instructions())

    def update(
        self, context: ProductContext, existing: ProductRequirementsDocument
    ) -> ProductRequirementsDocument:
        prompt = (
            self._base_prompt(context)
            + f"Existing PRD:\n{existing.model_dump_json(indent=2)}\n\n"
            + "Update the existing PRD so it reflects the product requirement, clarifications, confirmed "
            "analysis and decisions above. Keep everything that is still valid (including ids and wording), "
            "add what is new, change what conflicts, and remove what is obsolete.\n"
            + self._instructions()
        )
        return self._invoke(ProductRequirementsDocument, prompt)

    def revise(
        self, context: ProductContext, artifact: ProductRequirementsDocument, review: ReviewResult
    ) -> ProductRequirementsDocument:
        prompt = (
            self._base_prompt(context)
            + f"Current PRD:\n{artifact.model_dump_json(indent=2)}\n\n"
            + "Reviewer findings (resolve every one, keep what is already good):\n"
            + f"{review.model_dump_json(indent=2)}\n\n"
            + self._instructions()
        )
        return self._invoke(ProductRequirementsDocument, prompt)

    def _base_prompt(self, context: ProductContext) -> str:
        return (
            f"Product requirement:\n{context.product_requirement}\n\n"
            f"User clarifications:\n{lines(context.clarifications)}\n\n"
            f"Confirmed decisions (follow them):\n{decided_block(context.decisions)}\n\n"
            f"Confirmed analysis:\n{context.analysis.confirmed_json()}\n\n"
        )

    @staticmethod
    def _instructions() -> str:
        return (
            "Write the full PRD covering: users, functional scope (in/out), functional requirements, "
            "user stories, use cases, user journeys, non-functional requirements and abuse cases. "
            "Use ids FR-1, FR-1.1, NFR-1, US-1, UC-1, UJ-1. Each requirement needs a priority "
            "(must/should/could), measurable acceptance criteria (e.g. 'user receives upload "
            "confirmation within 5 seconds'), and sub-requirements where it can be broken down. "
            "Every functional requirement must be covered by at least one user story, and every user "
            "story must reference a listed user. Describe business functionality only; do not choose "
            "technologies. Include the confirmed non-functional requirements and abuse cases."
        )
