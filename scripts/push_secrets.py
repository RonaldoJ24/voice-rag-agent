"""Copy the deploy secrets from .env to SSM Parameter Store as SecureStrings.

    uv run scripts/push_secrets.py

Standard parameters are free, and values never appear on a command line or in the
CloudFormation template. Creates DEMO_ACCESS_CODE in .env first if it is missing.
"""

import secrets

import boto3

from voice_rag_agent.config import ROOT, get_settings

PREFIX = "/voice-rag-agent/"
NAMES = [
    "ANTHROPIC_API_KEY",
    "ELEVENLABS_API_KEY",
    "ELEVENLABS_AGENT_ID",
    "PROXY_BEARER_TOKEN",
    "DEMO_ACCESS_CODE",
]


def main() -> None:
    s = get_settings()
    if not s.demo_access_code:
        code = secrets.token_hex(3)
        with (ROOT / ".env").open("a") as f:
            f.write(f"DEMO_ACCESS_CODE={code}\n")
        s.demo_access_code = code
        print("Added DEMO_ACCESS_CODE to .env")

    ssm = boto3.client("ssm", region_name=s.aws_region)
    for name in NAMES:
        value = getattr(s, name.lower())
        if not value:
            raise SystemExit(f"{name} is empty in .env")
        ssm.put_parameter(
            Name=PREFIX + name, Value=value, Type="SecureString", Overwrite=True
        )
        print(f"Stored {PREFIX}{name}")


if __name__ == "__main__":
    main()
