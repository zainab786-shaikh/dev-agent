"""User interaction abstraction so the workflow is not tied to the console."""
from __future__ import annotations

from abc import ABC, abstractmethod


class UserInteraction(ABC):
    @abstractmethod
    def show(self, text: str) -> None: ...

    @abstractmethod
    def ask(self, prompt: str) -> str: ...

    @abstractmethod
    def confirm(self, prompt: str) -> bool: ...


class ConsoleInteraction(UserInteraction):
    def show(self, text: str) -> None:
        print(text)

    def ask(self, prompt: str) -> str:
        return input(f"{prompt}\n> ").strip()

    def confirm(self, prompt: str) -> bool:
        while True:
            answer = input(f"{prompt} [y/n]\n> ").strip().lower()
            if answer in {"y", "yes"}:
                return True
            if answer in {"n", "no"}:
                return False
