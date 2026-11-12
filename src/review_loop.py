"""Reusable create/update -> review -> revise loop; every artifact (PRD, design, ...) plugs into it."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, Optional, TypedDict, TypeVar

from langgraph.graph import END, START, StateGraph

from .models import ReviewResult

C = TypeVar("C")  # context the artifact is written from
A = TypeVar("A")  # the artifact itself

logger = logging.getLogger(__name__)


class ArtifactAuthor(ABC, Generic[C, A]):
    @abstractmethod
    def create(self, context: C) -> A: ...

    @abstractmethod
    def update(self, context: C, existing: A) -> A:
        """Bring an existing artifact in line with the current context, keeping what is still valid."""

    @abstractmethod
    def revise(self, context: C, artifact: A, review: ReviewResult) -> A: ...


class ArtifactReviewer(ABC, Generic[C, A]):
    @abstractmethod
    def review(self, context: C, artifact: A) -> ReviewResult: ...


@dataclass
class LoopResult(Generic[A]):
    artifact: A
    review: ReviewResult
    iterations: int
    converged: bool


class _LoopState(TypedDict, total=False):
    context: Any
    existing: Optional[Any]
    artifact: Any
    review: Optional[ReviewResult]
    iteration: int


class ReviewLoop(Generic[C, A]):
    def __init__(
        self,
        name: str,
        author: ArtifactAuthor[C, A],
        reviewer: ArtifactReviewer[C, A],
        max_iterations: int,
    ) -> None:
        self._name = name
        self._author = author
        self._reviewer = reviewer
        self._max_iterations = max_iterations
        self._graph = self._build()

    def run(self, context: C, existing: Optional[A] = None) -> LoopResult[A]:
        state = self._graph.invoke(
            {"context": context, "existing": existing, "iteration": 0}, {"recursion_limit": 200}
        )
        review: ReviewResult = state["review"]
        return LoopResult(state["artifact"], review, state["iteration"], not review.blocking())

    def _build(self):
        graph = StateGraph(_LoopState)
        graph.add_node("create", self._create)
        graph.add_node("update", self._update)
        graph.add_node("review", self._review)
        graph.add_node("revise", self._revise)
        graph.add_conditional_edges(
            START, lambda s: "update" if s.get("existing") is not None else "create", ["create", "update"]
        )
        graph.add_edge("create", "review")
        graph.add_edge("update", "review")
        graph.add_conditional_edges("review", self._next, ["revise", END])
        graph.add_edge("revise", "review")
        return graph.compile()

    def _create(self, state: _LoopState) -> _LoopState:
        logger.info("%s: creating", self._name)
        return {"artifact": self._author.create(state["context"]), "iteration": 1}

    def _update(self, state: _LoopState) -> _LoopState:
        logger.info("%s: updating the existing version", self._name)
        return {"artifact": self._author.update(state["context"], state["existing"]), "iteration": 1}

    def _review(self, state: _LoopState) -> _LoopState:
        review = self._reviewer.review(state["context"], state["artifact"])
        logger.info("%s: review found %d finding(s)", self._name, len(review.findings))
        return {"review": review}

    def _revise(self, state: _LoopState) -> _LoopState:
        iteration = state["iteration"] + 1
        logger.info("%s: revising (iteration %d)", self._name, iteration)
        artifact = self._author.revise(state["context"], state["artifact"], state["review"])
        return {"artifact": artifact, "iteration": iteration}

    def _next(self, state: _LoopState) -> str:
        if not state["review"].blocking():
            return END
        if state["iteration"] >= self._max_iterations:
            logger.warning("%s: max iterations reached with unresolved findings", self._name)
            return END
        return "revise"
