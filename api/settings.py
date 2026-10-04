"""Runtime configuration read from environment variables; invalid values stop the start-up."""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self

ADAPTERS = ("mock", "dataset")
INTERPRETERS = ("rules", "anthropic", "openai_compatible")


@dataclass(frozen=True)
class Settings:
    adapter: str = "mock"
    llm: str = "rules"
    version: str = "dev"
    demo_db: str = ""
    state_db: str = ":memory:"
    # Without a configured secret every start gets a random one: sessions simply do not survive a restart.
    session_secret: str = field(default_factory=lambda: secrets.token_hex(32))
    analyst_key: str = field(default_factory=lambda: secrets.token_urlsafe(24))
    messages_per_minute: int = 30

    def __post_init__(self) -> None:
        if self.adapter not in ADAPTERS:
            raise ValueError(f"VERA_ADAPTER must be one of {ADAPTERS}")
        if self.llm not in INTERPRETERS:
            raise ValueError(f"VERA_LLM must be one of {INTERPRETERS}")
        if self.adapter == "dataset" and not self.demo_db:
            raise ValueError("VERA_DEMO_DB is required when VERA_ADAPTER is dataset")

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> Self:
        """Build the settings; empty variables fall back to the safe defaults."""
        values = {
            "adapter": env.get("VERA_ADAPTER"),
            "llm": env.get("VERA_LLM"),
            "version": env.get("VERA_VERSION"),
            "demo_db": env.get("VERA_DEMO_DB"),
            "state_db": env.get("VERA_STATE_DB"),
            "session_secret": env.get("SESSION_SECRET"),
            "analyst_key": env.get("VERA_ANALYST_KEY"),
        }
        return cls(**{name: value for name, value in values.items() if value})
