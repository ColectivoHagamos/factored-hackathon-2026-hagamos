"""Runtime configuration read from environment variables; invalid values stop the start-up."""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Self

ADAPTERS = ("mock", "dataset")
INTERPRETERS = ("rules", "anthropic", "openai_compatible")


@dataclass(frozen=True)
class Settings:
    adapter: str = "mock"
    llm: str = "rules"
    version: str = "dev"

    def __post_init__(self) -> None:
        if self.adapter not in ADAPTERS:
            raise ValueError(f"VERA_ADAPTER must be one of {ADAPTERS}")
        if self.llm not in INTERPRETERS:
            raise ValueError(f"VERA_LLM must be one of {INTERPRETERS}")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Self:
        """Build the settings; empty variables fall back to the safe defaults."""
        return cls(
            adapter=env.get("VERA_ADAPTER") or cls.adapter,
            llm=env.get("VERA_LLM") or cls.llm,
            version=env.get("VERA_VERSION") or cls.version,
        )
