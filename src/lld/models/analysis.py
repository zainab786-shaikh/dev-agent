from __future__ import annotations

from pydantic import Field

from ...models import StageAnalysis
from .document import DataContract


class LldAnalysis(StageAnalysis):
    """Conventions and shared contracts every component's detailed design must follow."""

    conventions: list[str] = Field(
        default_factory=list,
        description="API versioning, naming, pagination, idempotency, id format, timestamp format, auth header",
    )
    shared_contracts: list[DataContract] = Field(
        default_factory=list, description="Common shapes such as the error response, pagination and ids"
    )
