"""Loads artifacts saved by earlier workflows so later ones can build on them."""
from __future__ import annotations

import json
from pathlib import Path

from .prd.models import ProductRequirementsDocument
from .architecture.models import ArchitectureDocument
from .dev.models import DevDocument
from .lld.models import LldDocument
from .srs.models import SoftwareRequirementsDocument
from .sysrs.models import SystemRequirementsDocument


def latest_artifact_file(directory: Path, prefix: str) -> Path:
    files = sorted(directory.glob(f"{prefix}_*.json"))
    if not files:
        raise FileNotFoundError(f"No saved '{prefix}' artifact found in {directory}; generate one first")
    return files[-1]


def load_prd(path: Path) -> ProductRequirementsDocument:
    return ProductRequirementsDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["prd"])


def load_sysrs(path: Path) -> SystemRequirementsDocument:
    return SystemRequirementsDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["sysrs"])


def load_srs(path: Path) -> SoftwareRequirementsDocument:
    return SoftwareRequirementsDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["srs"])


def load_architecture(path: Path) -> ArchitectureDocument:
    return ArchitectureDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["architecture"])


def load_lld(path: Path) -> LldDocument:
    return LldDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["lld"])


def load_dev(path: Path) -> DevDocument:
    return DevDocument.model_validate(json.loads(path.read_text(encoding="utf-8"))["dev"])
