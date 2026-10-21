"""Settings read from the environment (and .env when present)."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    elevenlabs_agent_id: str = ""
    # Shared secret ElevenLabs sends as "Authorization: Bearer <token>". Empty disables the check (local only).
    proxy_bearer_token: str = ""

    agent_model: str = "claude-haiku-5-5"
    agent_effort: str = "low"
    agent_max_tokens: int = 1024
    max_tool_rounds: int = 3

    retriever: str = "local"
    index_dir: Path = ROOT / "data" / "index"
    top_k: int = 5

    spend_ledger: Path = ROOT / "costs" / "spend.jsonl"
    spend_cap_usd: float = 50.0
    spend_pause_usd: float = 40.0

    trace_log: Path = ROOT / "logs" / "traces.jsonl"


@lru_cache
def get_settings() -> Settings:
    return Settings()
