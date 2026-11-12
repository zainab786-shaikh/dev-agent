from __future__ import annotations

from ...models import StageAnalysis
from .document import DevScaffold


class DevAnalysis(StageAnalysis, DevScaffold):
    """Proposal the user confirms before code is generated; the scaffold is filled in after the decisions."""
