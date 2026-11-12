"""Settings loaded from the .env file."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]

ARTIFACTS = ("prd", "sysrs", "srs", "architecture", "lld", "dev", "testing", "profile")
ROLE_DEFAULTS = {"author": "qwen", "reviewer": "mistral"}


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    models: dict[str, str]
    agent_models: dict[tuple[str, str], str]
    temperature: float
    num_ctx: int
    timeout_seconds: float
    max_iterations: int
    output_dir: Path
    log_level: str

    def model_for(self, artifact: str, role: str) -> str:
        return self.agent_models[(artifact, role)]

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env")
        models = {
            "mistral": os.environ["MISTRAL_MODEL"],
            "qwen": os.environ["QWEN_MODEL"],
        }

        agent_models: dict[tuple[str, str], str] = {}
        for artifact in ARTIFACTS:
            for role, default in ROLE_DEFAULTS.items():
                variable = f"{artifact.upper()}_{role.upper()}_MODEL"
                choice = os.getenv(variable, default).lower()
                if choice not in models:
                    raise ValueError(f"{variable}='{choice}' is invalid; expected one of {sorted(models)}")
                agent_models[(artifact, role)] = models[choice]

        output_dir = Path(os.getenv("OUTPUT_DIR", "output"))
        if not output_dir.is_absolute():
            output_dir = PROJECT_ROOT / output_dir

        return cls(
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            models=models,
            agent_models=agent_models,
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.2")),
            num_ctx=int(os.getenv("MODEL_NUM_CTX", "4096")),
            timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "300")),
            max_iterations=int(os.getenv("MAX_AGENT_ITERATIONS", "5")),
            output_dir=output_dir,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
