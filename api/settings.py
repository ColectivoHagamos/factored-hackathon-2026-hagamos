"""Runtime configuration read from environment variables; invalid values stop the start-up."""

import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Self

ADAPTERS = ("mock", "dataset")
# Only interpreters that exist are accepted, so /v1/health never reports one that is not in use.
INTERPRETERS = ("rules", "classifier", "anthropic")


@dataclass(frozen=True)
class Settings:
    adapter: str = "mock"
    llm: str = "rules"
    version: str = "dev"
    demo_db: str = ""
    state_db: str = ":memory:"
    # Without a configured secret every start gets a random one: sessions simply do not survive a restart.
    session_secret: str = field(default_factory=lambda: secrets.token_hex(32))
    # Empty: the demo analyst view is open, on purpose, for reviewers. Set: the analyst session requires it.
    analyst_key: str = ""
    # Accounts of the jury and the team, as "user:hash,..." (api/access.py); empty keeps the demo without a login.
    testers: str = field(default="", repr=False)
    messages_per_minute: int = 30
    # The language model of the anthropic interpreter (P41); the key never appears in a log or a repr.
    llm_api_key: str = field(default="", repr=False)
    # Required by keys that are not scoped to one workspace: they name it in every request.
    llm_workspace_id: str = ""
    llm_model: str = "claude-haiku-4-5-20251001"
    llm_max_spend_usd: float = 15.0
    llm_timeout_seconds: float = 3.0

    def __post_init__(self) -> None:
        if self.adapter not in ADAPTERS:
            raise ValueError(f"VERA_ADAPTER must be one of {ADAPTERS}")
        if self.llm not in INTERPRETERS:
            raise ValueError(f"VERA_LLM must be one of {INTERPRETERS}")
        if self.adapter == "dataset" and not self.demo_db:
            raise ValueError("VERA_DEMO_DB is required when VERA_ADAPTER is dataset")
        if self.llm_max_spend_usd <= 0 or self.llm_timeout_seconds <= 0:
            raise ValueError("LLM_MAX_SPEND_USD and the LLM timeout must be positive")

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
            "testers": env.get("VERA_TESTERS"),
            "llm_api_key": env.get("LLM_API_KEY"),
            "llm_workspace_id": env.get("LLM_WORKSPACE_ID"),
            "llm_model": env.get("LLM_MODEL"),
        }
        numbers = {
            "messages_per_minute": (env.get("VERA_MESSAGES_PER_MINUTE"), int),
            "llm_max_spend_usd": (env.get("LLM_MAX_SPEND_USD"), float),
        }
        settings = {name: value for name, value in values.items() if value}
        settings |= {name: parse(value) for name, (value, parse) in numbers.items() if value}
        return cls(**settings)
