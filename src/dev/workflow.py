"""Development workflow: tooling and git workflow decided with the user, code and unit tests per component,
project files, then the project is written and committed (after the user agrees)."""
from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Any, Optional

from ..agents.decision_judge import DecisionJudge
from ..architecture.models import ArchitectureComponent, ArchitectureDocument, GlobalDecision
from ..existing import ExistingArtifact
from ..interaction import UserInteraction
from ..lld.assembler import LldAssembler
from ..lld.models import LldDocument
from ..lld.sources import component_requirement_ids
from ..per_item_workflow import PerItemWorkflow
from ..staged_workflow import StageState
from .assembler import DevAssembler
from .author_agent import DevAuthorAgent
from .checks import check_files, safe_path
from .models import DevAnalysis, DevContext, DevDocument, DevElementSet
from .publisher import ProjectPublisher
from .reviewer_agent import DevReviewerAgent
from .sources import dev_digest


class DevWorkflow(PerItemWorkflow):
    name = "dev"
    title = "Development Artifacts"

    def __init__(
        self,
        author: DevAuthorAgent,
        reviewer: DevReviewerAgent,
        interaction: UserInteraction,
        output_dir: Path,
        max_iterations: int,
        judge: DecisionJudge,
        project_dir: Path,
        assembler: Optional[DevAssembler] = None,
        publisher: Optional[ProjectPublisher] = None,
    ) -> None:
        self._author = author
        self._assembler = assembler or DevAssembler()
        self._project_dir = project_dir
        self._publisher = publisher or ProjectPublisher(project_dir)
        super().__init__(author, reviewer, interaction, output_dir, max_iterations, judge)

    def run(
        self,
        architecture: ArchitectureDocument,
        lld: LldDocument,
        existing: Optional[ExistingArtifact[DevDocument, DevAnalysis]] = None,
    ) -> StageState:
        if existing is None and (self._project_dir / ".git").exists():
            raise RuntimeError(
                f"{self._project_dir} already holds a project; update it (run without --new) "
                "or move it away before starting from scratch"
            )
        return self._execute({"architecture": architecture, "lld": lld}, existing)

    # --- analysis -------------------------------------------------------------
    def _analysis_call(self, state: StageState) -> DevAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        return self._author.analyze(
            inputs["architecture"], inputs["lld"], state["clarifications"], state["feedback"],
            state["decisions"], existing.analysis if existing else None,
        )

    def _elaborate(self, state: StageState) -> DevAnalysis:
        existing = state.get("existing")
        inputs = state["inputs"]
        scaffold = self._author.design_scaffold(
            inputs["architecture"], inputs["lld"], state["clarifications"], state["decisions"],
            existing.analysis if existing else None,
        )
        self._notes.step("Defined the layout conventions and the git workflow from the verified decisions")
        return state["analysis"].model_copy(update={"layout": scaffold.layout, "git_workflow": scaffold.git_workflow})

    def _describe(self, analysis: DevAnalysis) -> list[str]:
        git = analysis.git_workflow
        lines = ["\nLayout conventions:"]
        lines += [f"  - {item}" for item in analysis.layout]
        lines += [
            "\nGit workflow:",
            f"  - branching model: {git.branching_model} (main branch '{git.main_branch}')",
            f"  - branches: {git.branch_pattern}",
            f"  - commits: {git.commit_convention}, e.g. {git.commit_template}",
        ]
        lines += [f"  - rule: {rule}" for rule in git.review_rules]
        return lines

    def _inputs_digest(self, state: StageState) -> str:
        return dev_digest(state["inputs"]["architecture"], state["inputs"]["lld"])

    # --- per component -------------------------------------------------------
    def _context_for(self, state: StageState, component: ArchitectureComponent, design) -> DevContext:
        architecture, lld = state["inputs"]["architecture"], state["inputs"]["lld"]
        wanted = set(component_requirement_ids(architecture, component.id))
        decisions = [*architecture.solution_architecture]
        decisions += [
            GlobalDecision(topic=a.title, decision=a.decision, rationale=a.rationale)
            for a in architecture.decisions
            if wanted & set(a.requirement_ids)
        ]
        tiers = {c.id: c.tier.strip().lower() for c in architecture.components}
        tier = tiers.get(component.id, "")
        api_ids = {cid for cid, t in tiers.items() if t == "api"}
        data_ids = {cid for cid, t in tiers.items() if t == "data"}
        return DevContext(
            component=component,
            other_components=[c for c in architecture.components if c.id != component.id],
            design=design,
            shared_contracts=[c for c in lld.data_contracts if not c.component_id],
            server_apis=[a for a in lld.api_specifications if a.component_id in api_ids] if tier == "client" else [],
            server_contracts=[c for c in lld.data_contracts if c.component_id in api_ids] if tier == "client" else [],
            data_tables=[t for t in lld.database_schema.tables if t.component_id in data_ids] if tier == "api" else [],
            architecture_decisions=decisions,
            analysis=state["analysis"],
            clarifications=state["clarifications"],
            decisions=state["decisions"],
        )

    def _items(self, state: StageState) -> list[tuple[str, DevContext]]:
        architecture, lld = state["inputs"]["architecture"], state["inputs"]["lld"]
        items = []
        for component in architecture.components:
            design = LldAssembler.extract(lld, component.id)
            if not self._is_empty(design):  # components with no detailed design have nothing to implement
                items.append((component.id, self._context_for(state, component, design)))
        return items

    def _extract(self, document: DevDocument, source_id: str) -> DevElementSet:
        return self._assembler.extract(document, source_id)

    def _assemble(self, state: StageState, results: dict[str, DevElementSet], previous: Any) -> DevDocument:
        return self._assembler.assemble(state["inputs"]["architecture"], state["analysis"], results, previous)

    # --- project files -------------------------------------------------------
    def _finalize(self, state: StageState, document: DevDocument) -> DevDocument:
        existing = state.get("existing")
        old_files = existing.document.project_files if existing else []
        problems = []
        files = []
        for _ in range(2):  # one automatic retry with the problems found
            files = self._author.project_files(state["analysis"], state["decisions"], document, old_files, problems).files
            problems = check_files(files)
            if not problems:
                break

        bad = {p.area for p in problems}
        warnings = list(document.warnings)
        kept = []
        for f in files:
            path = safe_path(f.path)
            if path is None or path in bad or f.path in bad:
                warnings.append(f"Project file '{f.path}' dropped: it failed the automatic checks")
            else:
                kept.append(f.model_copy(update={"path": path, "component_id": ""}))

        claimed = {f.path for f in kept}
        sources = [f for f in document.source_files if f.path not in claimed]
        tests = [f for f in document.test_files if f.path not in claimed]
        for f in [*document.source_files, *document.test_files]:
            if f.path in claimed:
                warnings.append(f"'{f.path}' from {f.component_id} dropped: a project file uses the same path")
        return document.model_copy(
            update={
                "project_files": kept,
                "source_files": sources,
                "test_files": tests,
                "commit_plan": [
                    p.model_copy(update={"files": [x for x in p.files if x not in claimed]}) for p in document.commit_plan
                ],
                "warnings": warnings,
            }
        )

    # --- publish -------------------------------------------------------------
    def _on_disk(self, document: DevDocument, paths: list[str]) -> bool:
        """Whether the files already exist unchanged in the project, e.g. not skipped by an earlier declined write."""
        files = {f.path: f for f in [*document.source_files, *document.test_files]}
        for path in paths:
            target = self._project_dir / path
            if path in files and (not target.is_file() or target.read_text(encoding="utf-8") != files[path].content):
                return False
        return True

    def _publish(self, state: StageState) -> dict:
        document: DevDocument = state["document"]
        existing = state.get("existing")
        changed = {r["source_id"] for r in state["items"] if r["action"] in ("created", "updated")}
        changed |= {p.component_id for p in document.commit_plan if not self._on_disk(document, p.files)}
        total = len(document.project_files) + len(document.source_files) + len(document.test_files)

        self._io.show(f"\nGenerated {total} file(s): {len(document.source_files)} source, "
                      f"{len(document.test_files)} test, {len(document.project_files)} project-level.")
        for warning in document.warnings:
            self._io.show(f"  warning: {warning}")
        deps = sorted({d for deps in document.component_dependencies.values() for d in deps})
        if deps:
            self._io.show(f"  dependencies: {', '.join(deps)}")
        for plan in document.commit_plan:
            if plan.component_id in changed:
                self._io.show(f"  {plan.branch}: '{plan.message}' ({len(plan.files)} file(s))")

        if not self._io.confirm(f"\nWrite the project to {self._project_dir} and commit it with this git workflow?"):
            self._notes.step("The user chose not to write the project; only the artifact was saved")
            return {}
        try:
            log = self._publisher.publish(document, changed, existing.document if existing else None)
        except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as exc:
            detail = getattr(exc, "stderr", None) or exc
            self._io.show(f"  The project was not written: {detail}")
            self._notes.step(f"Writing the project failed: {detail}")
            return {}
        for line in log:
            self._io.show(f"  {line}")
            self._notes.step(f"Project: {line}")
        self._notes.step(f"Wrote the project to {self._project_dir}; generated code was not executed")
        return {}
