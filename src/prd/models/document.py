"""Schemas for the Product Requirements Document (PRD)."""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class Priority(str, Enum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"


class UserPersona(BaseModel):
    name: str = Field(description="User role, e.g. Customer, Administrator")
    description: str
    goals: list[str] = Field(default_factory=list)


class UserStory(BaseModel):
    id: str = Field(description="e.g. US-1")
    persona: str = Field(description="Name of a user from the PRD users list")
    goal: str = Field(description="I want to ...")
    benefit: str = Field(description="so that ...")
    requirement_ids: list[str] = Field(default_factory=list, description="Functional requirement ids covered")
    acceptance_criteria: list[str] = Field(default_factory=list)


class UseCase(BaseModel):
    id: str = Field(description="e.g. UC-1")
    title: str
    actor: str
    preconditions: list[str] = Field(default_factory=list)
    main_flow: list[str] = Field(default_factory=list, description="Ordered steps")
    alternate_flows: list[str] = Field(default_factory=list)
    postconditions: list[str] = Field(default_factory=list)


class UserJourney(BaseModel):
    id: str = Field(description="e.g. UJ-1")
    persona: str
    goal: str
    steps: list[str] = Field(default_factory=list, description="End-to-end steps the user takes")


class FunctionalScope(BaseModel):
    in_scope: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class AbuseCase(BaseModel):
    title: str
    description: str = Field(description="How a malicious or careless actor could misuse the system")
    mitigation: str = ""


class ProductSubRequirement(BaseModel):
    id: str = Field(description="e.g. FR-1.1")
    title: str
    description: str
    acceptance_criteria: list[str] = Field(default_factory=list)


class ProductRequirement(BaseModel):
    id: str = Field(description="e.g. FR-1 or NFR-1")
    title: str
    description: str
    priority: Priority = Priority.MUST
    acceptance_criteria: list[str] = Field(default_factory=list)
    sub_requirements: list[ProductSubRequirement] = Field(default_factory=list)


class ProductRequirementsDocument(BaseModel):
    title: str
    overview: str
    users: list[UserPersona] = Field(default_factory=list)
    functional_scope: FunctionalScope = Field(default_factory=FunctionalScope)
    functional_requirements: list[ProductRequirement] = Field(default_factory=list)
    user_stories: list[UserStory] = Field(default_factory=list)
    use_cases: list[UseCase] = Field(default_factory=list)
    user_journeys: list[UserJourney] = Field(default_factory=list)
    non_functional_requirements: list[ProductRequirement] = Field(default_factory=list)
    abuse_cases: list[AbuseCase] = Field(default_factory=list)
