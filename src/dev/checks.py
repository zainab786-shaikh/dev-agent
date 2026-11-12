"""Safety and sanity checks on generated files. Nothing generated is ever executed, only parsed."""
from __future__ import annotations

import ast
import json
import re
from typing import Optional

from ..models import ReviewFinding, Severity
from .models import DevElementSet, SourceFile

_SAFE_PATH = re.compile(r"[A-Za-z0-9_./\-]+")
SECRET_PATTERNS = [
    (re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "a private key", True),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "an AWS access key id", True),
    (
        re.compile(r"(?i)(?:password|passwd|secret|api[_-]?key|token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
        "a hard-coded credential",
        False,  # tests legitimately contain fake credentials
    ),
]


def safe_path(path: str) -> Optional[str]:
    """Normalized relative POSIX path, or None if it could escape the project or touch git internals."""
    p = path.strip().replace("\\", "/")
    while p.startswith("./"):
        p = p[2:]
    if not p or len(p) > 200 or not _SAFE_PATH.fullmatch(p):
        return None
    parts = p.split("/")
    if any(part in ("", ".", "..") or part.lower() == ".git" for part in parts):
        return None
    return p


def _finding(path: str, issue: str, recommendation: str) -> ReviewFinding:
    return ReviewFinding(severity=Severity.HIGH, area=path, issue=issue, recommendation=recommendation)


def check_files(files: list[SourceFile], *, is_test: bool = False, taken: Optional[set[str]] = None) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    seen = set(taken or ())
    for f in files:
        path = safe_path(f.path)
        if path is None:
            findings.append(_finding(f.path, "Unsafe or invalid path", "Use a relative path with letters, digits, _ - . / only"))
            continue
        if path in seen:
            findings.append(_finding(path, "Path is used more than once", "Give every file a unique path"))
        seen.add(path)

        if not f.content.strip():
            findings.append(_finding(path, "File is empty", "Write the complete file content"))
            continue
        if path.endswith(".py"):
            try:
                ast.parse(f.content)
            except SyntaxError as exc:
                findings.append(_finding(path, f"Python syntax error at line {exc.lineno}: {exc.msg}", "Fix the syntax"))
        elif path.endswith(".json"):
            try:
                json.loads(f.content)
            except ValueError as exc:
                findings.append(_finding(path, f"Invalid JSON: {exc}", "Fix the JSON"))
        for pattern, label, applies_to_tests in SECRET_PATTERNS:
            if (applies_to_tests or not is_test) and pattern.search(f.content):
                findings.append(
                    _finding(path, f"Contains {label}", "Read secrets from environment variables or a secret store")
                )
    return findings


def check_element_set(derived: DevElementSet) -> list[ReviewFinding]:
    findings = check_files(derived.source_files)
    findings += check_files(derived.test_files, is_test=True, taken={safe_path(f.path) or "" for f in derived.source_files})
    if derived.source_files and not derived.test_files:
        findings.append(_finding("tests", "There are source files but no unit tests", "Add unit tests for every public function or method"))
    return findings
