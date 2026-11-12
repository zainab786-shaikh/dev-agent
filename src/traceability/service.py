"""Rebuilds the traceability matrix from the latest saved artifacts and records the update."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..architecture.models import ArchitectureDocument
from ..dev.models import DevDocument
from ..lld.models import LldDocument
from ..prd.models import ProductRequirementsDocument
from ..srs.models import SoftwareRequirementsDocument
from ..sysrs.models import SystemRequirementsDocument
from ..testing.models import QaDocument
from .builder import Artifacts, build_matrix
from .models import HistoryEntry, TraceabilityMatrix
from .render import render_markdown

_DOCUMENTS = {
    "prd": ProductRequirementsDocument,
    "sysrs": SystemRequirementsDocument,
    "srs": SoftwareRequirementsDocument,
    "architecture": ArchitectureDocument,
    "lld": LldDocument,
    "dev": DevDocument,
    "testing": QaDocument,
}


def load_artifacts(output_dir: Path) -> tuple[Artifacts, dict[str, str], list[str]]:
    """The latest saved document of every stage, the file each came from, and notes about unreadable files."""
    documents, files, notes = {}, {}, []
    for name, cls in _DOCUMENTS.items():
        candidates = sorted((output_dir / name).glob(f"{name}_*.json"))
        if not candidates:
            continue
        path = candidates[-1]
        try:
            documents[name] = cls.model_validate(json.loads(path.read_text(encoding="utf-8"))[name])
            files[name] = path.name
        except (ValueError, KeyError) as exc:
            notes.append(f"Could not read {path.name}: {exc}")
    return Artifacts(**documents), files, notes


def _previous(path: Path) -> Optional[TraceabilityMatrix]:
    if not path.exists():
        return None
    try:
        return TraceabilityMatrix.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def refresh(output_dir: Path, trigger: str) -> TraceabilityMatrix:
    """Call after a stage saved its artifact; keeps one living matrix plus a history of its updates."""
    artifacts, files, notes = load_artifacts(output_dir)
    matrix = build_matrix(artifacts)

    folder = output_dir / "traceability"
    json_path = folder / "traceability.json"
    previous = _previous(json_path)
    now = datetime.now().isoformat(timespec="seconds")
    matrix.updated_at = now
    matrix.notes = notes
    matrix.history = [
        *(previous.history if previous else []),
        HistoryEntry(
            at=now, trigger=trigger, artifact=files.get(trigger, ""), nodes=len(matrix.nodes),
            edges=len(matrix.edges), gaps=len(matrix.gaps), broken=len(matrix.broken_links),
        ),
    ]

    folder.mkdir(parents=True, exist_ok=True)
    json_path.write_text(matrix.model_dump_json(indent=2), encoding="utf-8")
    (folder / "traceability.md").write_text(render_markdown(matrix), encoding="utf-8")
    return matrix
