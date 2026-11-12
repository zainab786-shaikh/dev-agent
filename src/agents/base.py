"""Base class that gives every agent schema-validated LLM output with retries."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TypeVar

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, ValidationError

from .prompts import APP_NOTE

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    profile_aware = False  # True for agents whose prompts must follow the three-tier application profile

    def __init__(self, llm: BaseChatModel, max_retries: int = 2) -> None:
        self._llm = llm
        self._max_retries = max_retries

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    def _invoke(self, schema: type[T], user_prompt: str) -> T:
        structured = self._llm.with_structured_output(schema, method="json_schema")
        messages: list[BaseMessage] = [
            SystemMessage(content=self.system_prompt + (f" {APP_NOTE}" if self.profile_aware else "")),
            HumanMessage(content=user_prompt),
        ]
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                result = structured.invoke(messages)
                if isinstance(result, schema):
                    return result
                return schema.model_validate(result)
            except (ValidationError, ValueError, TypeError) as exc:
                last_error = exc
                logger.warning("%s: invalid output (attempt %d): %s", self.name, attempt + 1, exc)
                messages.append(
                    HumanMessage(content=f"Your previous output was invalid: {exc}. Return valid JSON only.")
                )
        raise RuntimeError(f"{self.name} failed to produce valid output") from last_error
