from __future__ import annotations

from pydantic import Field

from ...models import StageAnalysis
from .document import QaStrategy


class QaAnalysis(StageAnalysis):
    """Proposal the user confirms; the strategy is written after the decisions are verified."""

    strategy: QaStrategy = Field(default_factory=QaStrategy)
