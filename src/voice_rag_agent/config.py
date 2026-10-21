"""Settings read from the environment (and .env when present)."""

import os
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
    aws_region: str = "us-east-2"
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


def load_ssm_secrets(prefix: str) -> None:
    """On Lambda, secrets live in SSM Parameter Store as SecureStrings, not in the template.

    /voice-rag-agent/ANTHROPIC_API_KEY becomes the ANTHROPIC_API_KEY environment variable.
    """
    import boto3

    pages = (
        boto3.client("ssm")
        .get_paginator("get_parameters_by_path")
        .paginate(Path=prefix, WithDecryption=True)
    )
    for page in pages:
        for param in page["Parameters"]:
            os.environ.setdefault(param["Name"].removeprefix(prefix), param["Value"])


@lru_cache
def get_settings() -> Settings:
    if prefix := os.environ.get("SSM_SECRETS_PREFIX"):
        load_ssm_secrets(prefix)
    return Settings()
