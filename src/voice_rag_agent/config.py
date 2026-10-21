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
    aws_region: str = "us-east-1"
    s3vectors_bucket: str = ""
    s3vectors_index: str = "docs-titan-v2-256"

    spend_ledger: Path = ROOT / "costs" / "spend.jsonl"
    spend_cap_usd: float = 50.0
    spend_pause_usd: float = 40.0

    trace_log: Path = ROOT / "logs" / "traces.jsonl"

    # "local" keeps trace events in memory and spend in costs/spend.jsonl. "dynamodb" keeps
    # both in one table, which Lambda needs because each request may hit a new instance.
    state_backend: str = "local"
    dynamodb_table: str = ""
    # Visitors type this code before /api/session hands out a signed URL. Empty = open.
    demo_access_code: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
