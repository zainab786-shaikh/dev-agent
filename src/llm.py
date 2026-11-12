"""Factory for local chat models served by Ollama."""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_ollama import ChatOllama

from .config import Settings


class LLMFactory:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def create(self, model: str) -> BaseChatModel:
        s = self._settings
        return ChatOllama(
            model=model,
            base_url=s.ollama_base_url,
            temperature=s.temperature,
            num_ctx=s.num_ctx,
            client_kwargs={"timeout": s.timeout_seconds},
        )
