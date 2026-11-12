import shutil
import subprocess

import pytest

from dev.checks import check_element_set, check_files, safe_path
from dev.models import CommitPlan, DevDocument, DevElementSet, GitWorkflow, SourceFile
from dev.publisher import ProjectPublisher

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git is not installed")


@pytest.mark.parametrize("path, expected", [
    ("src/app/main.py", "src/app/main.py"), ("./a/b.py", "a/b.py"), ("a\\b.py", "a/b.py"),
    ("../x.py", None), ("/etc/passwd", None), ("C:/x.py", None), ("a/../b.py", None),
    (".git/config", None), ("a/.GIT/x", None), ("a b.py", None), ("", None), ("x" * 201, None),
])
def test_safe_path(path, expected):
    assert safe_path(path) == expected


def _issues(files, **kwargs):
    return [f.issue for f in check_files(files, **kwargs)]


def test_checks_catch_syntax_errors_secrets_empty_and_duplicate_files():
    bad_py = SourceFile(path="a.py", content="def broken(:\n")
    assert "Python syntax error at line 1" in _issues([bad_py])[0]
    assert _issues([SourceFile(path="x.json", content="{oops")])[0].startswith("Invalid JSON")
    assert _issues([SourceFile(path="a.py", content="  \n")]) == ["File is empty"]
    twice = [SourceFile(path="a.py", content="x = 1"), SourceFile(path="./a.py", content="y = 2")]
    assert _issues(twice) == ["Path is used more than once"]

    credential = SourceFile(path="cfg.py", content='PASSWORD = "hunter2hunter2"\n')
    assert _issues([credential]) == ["Contains a hard-coded credential"]
    assert _issues([credential], is_test=True) == []  # fake credentials are normal in tests
    key = SourceFile(path="t.py", content="k = '-----BEGIN PRIVATE KEY-----'\n")
    assert _issues([key], is_test=True) == ["Contains a private key"]


def test_source_files_without_tests_are_flagged():
    findings = check_element_set(DevElementSet(source_files=[SourceFile(path="a.py", content="x = 1\n")]))
    assert [f.issue for f in findings] == ["There are source files but no unit tests"]


def _doc(api_body="v1", with_store=True):
    source = [SourceFile(path="api/app.py", content=f"x = '{api_body}'\n", component_id="COMP-1")]
    plan = [CommitPlan(component_id="COMP-1", branch="feature/api", message="feat(api): implement Api",
                       files=["api/app.py", "tests/test_app.py"])]
    if with_store:
        source.append(SourceFile(path="store/db.py", content="y = 1\n", component_id="COMP-2"))
        plan.append(CommitPlan(component_id="COMP-2", branch="feature/store", message="feat(store): implement Store",
                               files=["store/db.py"]))
    return DevDocument(
        title="t", overview="o", git_workflow=GitWorkflow(),
        project_files=[SourceFile(path="README.md", content="# readme\n")],
        source_files=source,
        test_files=[SourceFile(path="tests/test_app.py", content="def test_x():\n    assert True\n", component_id="COMP-1")],
        commit_plan=plan,
    )


def _git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout


@needs_git
def test_publish_commits_each_component_on_a_branch_and_merges_it(tmp_path):
    root = tmp_path / "project"
    log = ProjectPublisher(root).publish(_doc(), {"COMP-1", "COMP-2"}, None)

    assert (root / "api/app.py").exists() and (root / "store/db.py").exists() and (root / "README.md").exists()
    subjects = _git(root, "log", "--format=%s").splitlines()
    assert "chore: scaffold project" in subjects
    assert "feat(api): implement Api" in subjects and "Merge branch 'feature/api'" in subjects
    assert "Merge branch 'feature/store'" in subjects
    assert _git(root, "branch", "--format=%(refname:short)").split() == ["main"]  # merged branches are deleted
    assert any("feature/api" in line for line in log)


@needs_git
def test_publish_update_only_touches_changed_components_and_removes_obsolete_files(tmp_path):
    root = tmp_path / "project"
    publisher = ProjectPublisher(root)
    first = _doc()
    publisher.publish(first, {"COMP-1", "COMP-2"}, None)

    second = _doc("v2")
    publisher.publish(second, {"COMP-1"}, first)
    subjects = _git(root, "log", "--format=%s").splitlines()
    assert subjects.count("Merge branch 'feature/api'") == 2 and subjects.count("Merge branch 'feature/store'") == 1
    assert "v2" in (root / "api/app.py").read_text()

    third = _doc("v2", with_store=False)
    publisher.publish(third, set(), second)
    assert not (root / "store/db.py").exists()
    assert _git(root, "log", "-1", "--format=%s").strip() == "chore: remove obsolete files"


@needs_git
def test_publish_refuses_to_overwrite_uncommitted_work_and_paths_outside_the_project(tmp_path):
    root = tmp_path / "project"
    publisher = ProjectPublisher(root)
    publisher.publish(_doc(), {"COMP-1", "COMP-2"}, None)

    (root / "notes.txt").write_text("my own work", encoding="utf-8")
    with pytest.raises(RuntimeError, match="uncommitted"):
        publisher.publish(_doc("v2"), {"COMP-1"}, _doc())
    (root / "notes.txt").unlink()

    evil = _doc()
    evil.source_files[0] = SourceFile(path="../evil.py", content="x = 1\n", component_id="COMP-1")
    evil.commit_plan[0].files = ["../evil.py"]
    with pytest.raises(ValueError, match="outside the project"):
        ProjectPublisher(tmp_path / "other").publish(evil, {"COMP-1"}, None)
    assert not (tmp_path / "evil.py").exists()
