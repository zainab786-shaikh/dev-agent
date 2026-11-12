import json
import shutil
import subprocess
from pathlib import Path

import pytest

from architecture.models import ArchitectureComponent, ArchitectureDocument, ComponentDiagram, GlobalDecision
from dev import DevWorkflow
from dev.models import DevAnalysis, DevDocument, DevElementSet, DevScaffold, GitWorkflow, ProjectFileSet, SourceFile
from existing import load_existing
from lld.models import ApiEndpoint, LldDocument
from review_loop import ArtifactAuthor
from stubs import ApprovingReviewer, ScriptedInteraction, StubJudge, platform_proposal

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


class StubAuthor(ArtifactAuthor):
    def __init__(self, project_files=None):
        self.created, self.updated, self.project_calls = [], [], []
        self._project_files = project_files

    def analyze(self, *_):
        return DevAnalysis(summary="s", decision_proposals=[platform_proposal("Programming language")])

    def design_scaffold(self, *_):
        return DevScaffold(layout=["one package per component"], git_workflow=GitWorkflow(branching_model="trunk-based"))

    def create(self, context):
        self.created.append(context.component.id)
        return self._files(context)

    def update(self, context, existing):
        self.updated.append(context.component.id)
        return self._files(context)

    @staticmethod
    def _files(context):
        slug = context.component.name.lower()
        return DevElementSet(
            source_files=[SourceFile(path=f"{slug}/app.py", content=f"NAME = '{slug}'\n")],
            test_files=[SourceFile(path=f"tests/test_{slug}.py", content="def test_ok():\n    assert True\n")],
            dependencies=["requests"],
        )

    def revise(self, context, artifact, review):
        raise AssertionError("reviewer approves")

    def project_files(self, analysis, decisions, document, existing, problems):
        self.project_calls.append(problems)
        files = self._project_files(len(self.project_calls)) if self._project_files else [
            SourceFile(path="README.md", content="# project\n"), SourceFile(path="requirements.txt", content="requests\n")
        ]
        return ProjectFileSet(files=files)


def _architecture() -> ArchitectureDocument:
    return ArchitectureDocument(
        title="a", overview="o", solution_architecture=[GlobalDecision(topic="Cloud platform", decision="Azure")],
        components=[
            ArchitectureComponent(id="COMP-1", name="Api", responsibility="r", technology="AKS"),
            ArchitectureComponent(id="COMP-2", name="Store", responsibility="r", technology="Cosmos"),
            ArchitectureComponent(id="COMP-3", name="Blob", responsibility="managed service, no code"),
        ],
        component_diagram=ComponentDiagram(title="c", mermaid="flowchart LR"),
    )


def _lld(store_path="/v1/store") -> LldDocument:
    return LldDocument(
        title="l", overview="o",
        api_specifications=[
            ApiEndpoint(method="POST", path="/v1/api", summary="s", component_id="COMP-1"),
            ApiEndpoint(method="POST", path=store_path, summary="s", component_id="COMP-2"),
        ],
    )


def _run(tmp_path, author=None, existing=None, lld=None, confirms=None):
    author = author or StubAuthor()
    io = ScriptedInteraction(answers=[""], confirms=confirms)
    workflow = DevWorkflow(
        author, ApprovingReviewer(), io, tmp_path / "dev", 5, StubJudge(), project_dir=tmp_path / "dev" / "project"
    )
    return workflow.run(_architecture(), lld or _lld(), existing), author, io


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def _saved(result):
    return json.loads(Path(result["output_path"]).read_text())


def test_code_is_generated_per_component_and_committed_with_the_git_workflow(tmp_path):
    result, author, _ = _run(tmp_path)
    saved = _saved(result)
    project = tmp_path / "dev" / "project"

    assert author.created == ["COMP-1", "COMP-2"]  # COMP-3 has no detailed design, so no code
    assert [(p["branch"], p["message"]) for p in saved["dev"]["commit_plan"]] == [
        ("feature/api", "feat(api): implement Api"), ("feature/store", "feat(store): implement Store"),
    ]
    assert saved["dev"]["component_dependencies"] == {"COMP-1": ["requests"], "COMP-2": ["requests"]}
    assert (project / "api/app.py").exists() and (project / "tests/test_store.py").exists() and (project / "README.md").exists()
    subjects = _git(project, "log", "--format=%s").splitlines()
    assert "Merge branch 'feature/api'" in subjects and "chore: scaffold project" in subjects
    notes = Path(result["output_path"]).with_name(Path(result["output_path"]).stem + ".notes.md").read_text()
    assert "generated code was not executed" in notes and "Programming language" in notes


def test_nothing_is_written_when_the_user_declines(tmp_path):
    result, _, _ = _run(tmp_path, confirms=[True, False])  # confirm analysis, decline writing
    assert Path(result["output_path"]).exists()
    assert not (tmp_path / "dev" / "project").exists()


def test_update_rewrites_only_the_changed_component_and_starting_over_is_refused(tmp_path):
    _run(tmp_path)
    existing = load_existing(tmp_path / "dev", "dev", DevDocument, DevAnalysis)
    project = tmp_path / "dev" / "project"

    result, author, _ = _run(tmp_path, existing=existing, lld=_lld("/v2/store"))
    assert author.created == [] and author.updated == ["COMP-2"]
    assert {i["source_id"]: i["action"] for i in _saved(result)["items"]} == {"COMP-1": "reused", "COMP-2": "updated"}
    # identical content for the updated component leaves nothing to commit, and the api branch is untouched
    assert _git(project, "log", "--format=%s").splitlines().count("Merge branch 'feature/api'") == 1

    with pytest.raises(RuntimeError, match="already holds a project"):
        _run(tmp_path)  # no existing version given, but the project exists


def test_project_files_are_checked_retried_and_cannot_overwrite_component_code(tmp_path):
    def files(call):
        if call == 1:
            return [SourceFile(path="../escape.txt", content="x")]
        return [SourceFile(path="README.md", content="# ok\n"), SourceFile(path="api/app.py", content="# clash\n")]

    result, author, _ = _run(tmp_path, StubAuthor(files))
    saved = _saved(result)["dev"]

    assert len(author.project_calls) == 2 and author.project_calls[0] == []
    assert author.project_calls[1][0].area == "../escape.txt"  # the retry was told what was wrong
    assert [f["path"] for f in saved["project_files"]] == ["README.md", "api/app.py"]
    assert "api/app.py" not in [f["path"] for f in saved["source_files"]]
    assert any("a project file uses the same path" in w for w in saved["warnings"])
    assert not (tmp_path / "escape.txt").exists()


def test_components_skipped_by_a_declined_write_are_written_on_the_next_run(tmp_path):
    _run(tmp_path, confirms=[True, False])
    existing = load_existing(tmp_path / "dev", "dev", DevDocument, DevAnalysis)
    _run(tmp_path, existing=existing)
    assert (tmp_path / "dev" / "project" / "api/app.py").exists()
