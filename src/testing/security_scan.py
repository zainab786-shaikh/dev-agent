"""Heuristic static security scan of generated source files. It reads text only and never runs the code."""
from __future__ import annotations

import re

from ..dev.checks import SECRET_PATTERNS
from ..dev.models import SourceFile
from .models import StaticFinding

_RULES = [
    (r"\beval\s*\(", "dynamic-eval", "high", "eval() runs arbitrary code"),
    (r"\bexec\s*\(", "dynamic-exec", "high", "exec() runs arbitrary code"),
    (r"shell\s*=\s*True|os\.system\s*\(|child_process\.exec\s*\(", "shell-injection", "high", "Shell command execution"),
    (r"pickle\.loads?\s*\(", "unsafe-deserialization", "high", "Deserializing untrusted data with pickle"),
    (r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false", "tls-verification-disabled", "high", "TLS verification is disabled"),
    (r"""\.execute\s*\(\s*f["']""", "sql-injection", "high", "SQL built with an f-string"),
    (r"""\.execute\s*\([^)]*["']\s*(?:\+|%)\s*\w""", "sql-injection", "high", "SQL built by concatenation"),
    (r"hashlib\.(?:md5|sha1)\s*\(", "weak-hash", "medium", "MD5 or SHA-1 is not suitable for security use"),
    (r"\.innerHTML\s*=", "xss", "medium", "Assigning innerHTML can enable cross-site scripting"),
    (r"\bdebug\s*=\s*True", "debug-enabled", "medium", "Debug mode enabled"),
]
_COMPILED = [(re.compile(pattern), rule, severity, detail) for pattern, rule, severity, detail in _RULES]


def scan_source(files: list[SourceFile]) -> list[StaticFinding]:
    findings: list[StaticFinding] = []
    for f in files:
        for number, line in enumerate(f.content.splitlines(), 1):
            for pattern, rule, severity, detail in _COMPILED:
                if pattern.search(line):
                    findings.append(StaticFinding(
                        path=f.path, component_id=f.component_id, line=number, rule=rule, severity=severity, detail=detail
                    ))
            for pattern, label, _ in SECRET_PATTERNS:
                if pattern.search(line):
                    findings.append(StaticFinding(
                        path=f.path, component_id=f.component_id, line=number, rule="hard-coded-secret",
                        severity="high", detail=f"Contains {label}",
                    ))
    return findings
