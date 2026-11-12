"""Writes the generated project to disk and commits it with the git workflow. Local only: no push, no execution."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional

from .assembler import main_branch
from .checks import safe_path
from .models import DevDocument, SourceFile


class GitRepository:
    def __init__(self, root: Path) -> None:
        self._root = root

    def run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        base = ["git", "-c", "user.name=Software Agent", "-c", "user.email=agent@localhost", "-c", "commit.gpgsign=false"]
        return subprocess.run(
            [*base, *args], cwd=self._root, check=check, capture_output=True, text=True, timeout=120
        )

    def is_repo(self) -> bool:
        return (self._root / ".git").exists()

    def init(self, branch: str) -> None:
        self.run("init", "-b", branch)

    def has_commits(self) -> bool:
        return self.run("rev-parse", "--verify", "HEAD", check=False).returncode == 0

    def has_changes(self) -> bool:
        return bool(self.run("status", "--porcelain").stdout.strip())

    def commit_all(self, message: str) -> bool:
        self.run("add", "-A")
        if not self.has_changes():
            return False
        self.run("commit", "-m", message)
        return True

    def checkout(self, branch: str) -> None:
        self.run("checkout", branch)

    def create_branch(self, branch: str) -> None:
        self.run("checkout", "-b", branch)

    def merge_no_ff(self, branch: str, message: str) -> None:
        self.run("merge", "--no-ff", "-m", message, branch)

    def delete_branch(self, branch: str) -> None:
        self.run("branch", "-d", branch)


class ProjectPublisher:
    def __init__(self, root: Path) -> None:
        self._root = root

    def publish(self, document: DevDocument, changed: set[str], previous: Optional[DevDocument]) -> list[str]:
        """Writes the project; returns a log of what was done."""
        log: list[str] = []
        self._root.mkdir(parents=True, exist_ok=True)
        git = GitRepository(self._root) if shutil.which("git") else None
        main = main_branch(document.git_workflow)

        if git is None:
            log.append("git is not installed; files were written without commits")
        elif not git.is_repo():
            git.init(main)
            log.append(f"Initialised a git repository on '{main}'")
        else:
            if git.has_changes():
                raise RuntimeError(f"{self._root} has uncommitted changes; commit or stash them first")
            git.checkout(main)

        for f in document.project_files:
            self._write(f)
        if git:
            first = not git.has_commits()
            if git.commit_all("chore: scaffold project" if first else "chore: update project files"):
                log.append(f"Committed the project files on '{main}'")

        for plan in document.commit_plan:
            if plan.component_id not in changed:
                continue
            if git:
                git.create_branch(plan.branch)
            for path in plan.files:
                f = self._file(document, path)
                if f:
                    self._write(f)
            if not git:
                log.append(f"Wrote {len(plan.files)} file(s) for {plan.component_id}")
                continue
            committed = git.commit_all(plan.message)
            git.checkout(main)
            if committed:
                git.merge_no_ff(plan.branch, f"Merge branch '{plan.branch}'")
                log.append(f"{plan.branch}: committed '{plan.message}' and merged into '{main}'")
            else:
                log.append(f"{plan.branch}: no changes to commit")
            git.delete_branch(plan.branch)

        removed = self._remove_stale(document, previous)
        if removed:
            if git and git.commit_all("chore: remove obsolete files"):
                log.append(f"Removed {len(removed)} obsolete file(s) on '{main}'")
            elif not git:
                log.append(f"Removed {len(removed)} obsolete file(s)")
        return log

    @staticmethod
    def _file(document: DevDocument, path: str) -> Optional[SourceFile]:
        return next((f for f in [*document.source_files, *document.test_files] if f.path == path), None)

    def _target(self, relative: str) -> Path:
        safe = safe_path(relative)
        if safe is None:
            raise ValueError(f"Refusing to write outside the project: {relative!r}")
        root = self._root.resolve()
        target = (root / safe).resolve()
        if root not in target.parents:
            raise ValueError(f"Refusing to write outside the project: {relative!r}")
        return target

    def _write(self, f: SourceFile) -> None:
        target = self._target(f.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f.content, encoding="utf-8", newline="\n")

    def _remove_stale(self, document: DevDocument, previous: Optional[DevDocument]) -> list[str]:
        if previous is None:
            return []
        old = {f.path for f in [*previous.project_files, *previous.source_files, *previous.test_files]}
        new = {f.path for f in [*document.project_files, *document.source_files, *document.test_files]}
        removed = []
        for path in sorted(old - new):
            try:
                target = self._target(path)
            except ValueError:
                continue
            if target.is_file():
                target.unlink()
                removed.append(path)
        return removed
