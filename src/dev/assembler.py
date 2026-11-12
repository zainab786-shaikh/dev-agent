"""Builds the final development document from per-component code (no LLM)."""
from __future__ import annotations

import re
from typing import Optional

from ..architecture.models import ArchitectureDocument
from .checks import safe_path
from .models import CommitPlan, DevAnalysis, DevDocument, DevElementSet, GitWorkflow, SourceFile

_BRANCH = re.compile(r"[A-Za-z0-9._/-]+")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "component"


def main_branch(workflow: GitWorkflow) -> str:
    return workflow.main_branch if _BRANCH.fullmatch(workflow.main_branch) and ".." not in workflow.main_branch else "main"


def branch_name(workflow: GitWorkflow, component_name: str) -> str:
    fallback = f"feature/{slug(component_name)}"
    try:
        name = workflow.branch_pattern.format(component=slug(component_name), name=slug(component_name))
    except (KeyError, IndexError, ValueError):
        return fallback
    valid = (
        _BRANCH.fullmatch(name)
        and ".." not in name
        and not name.startswith(("-", "/", "."))
        and not name.endswith(("/", ".", ".lock"))
        and name != main_branch(workflow)
    )
    return name if valid else fallback


def commit_message(workflow: GitWorkflow, component_name: str) -> str:
    fallback = f"feat({slug(component_name)}): implement {component_name}"
    try:
        text = workflow.commit_template.format(component=slug(component_name), name=component_name)
    except (KeyError, IndexError, ValueError):
        return fallback
    lines = text.strip().splitlines()
    return lines[0][:100] if lines and lines[0].strip() else fallback


class DevAssembler:
    def assemble(
        self,
        architecture: ArchitectureDocument,
        analysis: DevAnalysis,
        results: dict[str, DevElementSet],
        previous: Optional[DevDocument] = None,
    ) -> DevDocument:
        names = {c.id: c.name for c in architecture.components}
        sources: list[SourceFile] = []
        tests: list[SourceFile] = []
        dependencies: dict[str, list[str]] = {}
        plan: list[CommitPlan] = []
        warnings: list[str] = []
        taken: set[str] = set()

        for component_id, derived in results.items():
            written: list[str] = []
            for files, target in ((derived.source_files, sources), (derived.test_files, tests)):
                for f in files:
                    path = safe_path(f.path)
                    if path is None:
                        warnings.append(f"{component_id}: dropped file with unsafe path '{f.path}'")
                    elif path in taken:
                        warnings.append(f"{component_id}: '{path}' is already written by another component; skipped")
                    else:
                        taken.add(path)
                        target.append(f.model_copy(update={"path": path, "component_id": component_id}))
                        written.append(path)
            dependencies[component_id] = list(dict.fromkeys(d.strip() for d in derived.dependencies if d.strip()))
            name = names.get(component_id, component_id)
            plan.append(
                CommitPlan(
                    component_id=component_id,
                    branch=branch_name(analysis.git_workflow, name),
                    message=commit_message(analysis.git_workflow, name),
                    files=written,
                )
            )

        return DevDocument(
            title=f"Development Artifacts for {architecture.title}",
            overview=analysis.summary,
            layout=analysis.layout,
            git_workflow=analysis.git_workflow,
            project_files=previous.project_files if previous else [],
            source_files=sources,
            test_files=tests,
            component_dependencies=dependencies,
            commit_plan=plan,
            warnings=warnings,
        )

    @staticmethod
    def extract(document: DevDocument, component_id: str) -> DevElementSet:
        """The part of an existing document that was written for one component."""
        return DevElementSet(
            source_files=[f for f in document.source_files if f.component_id == component_id],
            test_files=[f for f in document.test_files if f.component_id == component_id],
            dependencies=document.component_dependencies.get(component_id, []),
        )
