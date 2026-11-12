"""Stable ids: an item that matches the previous version keeps its id; new items get a fresh number."""
from __future__ import annotations

import re
from typing import Callable, Hashable, Optional, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


def _number(item_id: str, prefix: str) -> int:
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d+)", item_id)
    return int(match.group(1)) if match else 0


def assign_ids(items: list[M], prefix: str, previous: list[M], key: Callable[[M], Hashable]) -> list[M]:
    known: dict[Hashable, str] = {}
    for p in previous:
        known.setdefault(key(p), getattr(p, "id"))

    ids: list[Optional[str]] = []
    used: set[str] = set()
    for item in items:
        previous_id = known.get(key(item))
        if previous_id and previous_id not in used:
            ids.append(previous_id)
            used.add(previous_id)
        else:
            ids.append(None)

    highest = max(
        [0, *(_number(getattr(p, "id"), prefix) for p in previous), *(_number(i, prefix) for i in ids if i)]
    )
    result = []
    for item, item_id in zip(items, ids):
        if item_id is None:
            highest += 1
            item_id = f"{prefix}-{highest}"
        result.append(item.model_copy(update={"id": item_id}))
    return result
