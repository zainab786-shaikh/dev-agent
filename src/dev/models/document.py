"""Schemas for the development artifacts: source code, unit tests and the git workflow."""
from __future__ import annotations

from pydantic import BaseModel, Field


class SourceFile(BaseModel):
    path: str = Field(description="Relative path inside the project, forward slashes, no leading slash")
    purpose: str = ""
    content: str = Field(description="Complete file content")
    component_id: str = Field(default="", description="Owning component; empty for project-level files")


class GitWorkflow(BaseModel):
    branching_model: str = Field(default="", description="e.g. trunk-based with short-lived feature branches")
    main_branch: str = "main"
    branch_pattern: str = Field(default="feature/{component}", description="Placeholders: {component}, {name}")
    commit_convention: str = Field(default="", description="e.g. Conventional Commits")
    commit_template: str = Field(
        default="feat({component}): implement {name}", description="One line; placeholders: {component}, {name}"
    )
    review_rules: list[str] = Field(default_factory=list, description="Pull request and CI requirements")


class DevScaffold(BaseModel):
    """Conventions the generated project follows; the language and tooling come from the verified decisions."""

    layout: list[str] = Field(
        default_factory=list,
        description="Project structure, module naming, test layout, error handling, logging, configuration",
    )
    git_workflow: GitWorkflow = Field(default_factory=GitWorkflow)


class DevElementSet(BaseModel):
    """Code derived for ONE architecture component."""

    source_files: list[SourceFile] = Field(default_factory=list)
    test_files: list[SourceFile] = Field(default_factory=list, description="Unit tests for the source files")
    dependencies: list[str] = Field(default_factory=list, description="Third-party packages the code needs")


class ProjectFileSet(BaseModel):
    """Project-level files: dependency manifest, README, .gitignore, CI pipeline, pull request template."""

    files: list[SourceFile] = Field(default_factory=list)


class CommitPlan(BaseModel):
    component_id: str
    branch: str
    message: str
    files: list[str] = Field(default_factory=list)


class DevDocument(BaseModel):
    title: str
    overview: str
    layout: list[str] = Field(default_factory=list)
    git_workflow: GitWorkflow = Field(default_factory=GitWorkflow)
    project_files: list[SourceFile] = Field(default_factory=list)
    source_files: list[SourceFile] = Field(default_factory=list)
    test_files: list[SourceFile] = Field(default_factory=list)
    component_dependencies: dict[str, list[str]] = Field(default_factory=dict)
    commit_plan: list[CommitPlan] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list, description="Files dropped or skipped, and why")
