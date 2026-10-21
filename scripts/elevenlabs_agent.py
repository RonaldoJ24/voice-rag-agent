"""Create or update the private ElevenLabs agent that uses this proxy as its Custom LLM.

    uv run scripts/elevenlabs_agent.py --base-url https://<tunnel-or-lambda-host>

First run creates a workspace secret for the proxy's Bearer token and a new agent,
then writes ELEVENLABS_AGENT_ID to .env. Later runs only update the proxy URL.
"""

import argparse
import json
import re

import httpx

from voice_rag_agent.config import ROOT, get_settings

API = "https://api.elevenlabs.io/v1/convai"
VOICE_ID = (
    "DODLEQrClDo8wCz460ld"  # Lauren B, the voice already used in the explainer videos
)
TTS_MODEL = "eleven_flash_v2_5"  # lowest-latency multilingual TTS (EN and ES)


def agent_config(base_url: str, secret_id: str, model: str) -> dict:
    return {
        "name": "FastAPI Docs Voice Agent",
        "conversation_config": {
            "agent": {
                "first_message": "Hi! Ask me anything about FastAPI, in English or Spanish.",
                "language": "en",
                "prompt": {
                    "prompt": "Answers come from the custom LLM, which follows its own instructions.",
                    "llm": "custom-llm",
                    "custom_llm": {
                        "url": f"{base_url.rstrip('/')}/v1/chat/completions",
                        "model_id": model,
                        "api_key": {"secret_id": secret_id},
                        "api_type": "chat_completions",
                    },
                    "built_in_tools": {"end_call": {}, "language_detection": {}},
                },
            },
            "language_presets": {
                "es": {
                    "overrides": {
                        "agent": {
                            "first_message": "¡Hola! Pregúntame lo que quieras sobre FastAPI.",
                            "language": "es",
                        }
                    }
                }
            },
            "tts": {"model_id": TTS_MODEL, "voice_id": VOICE_ID},
            "conversation": {"max_duration_seconds": 180},
        },
        "platform_settings": {"auth": {"enable_auth": True}},
    }


def save_env(key: str, value: str) -> None:
    env = ROOT / ".env"
    text = env.read_text() if env.exists() else ""
    line = f"{key}={value}"
    text = (
        re.sub(rf"^{key}=.*$", line, text, flags=re.MULTILINE)
        if re.search(rf"^{key}=", text, re.MULTILINE)
        else text + f"\n{line}\n"
    )
    env.write_text(text)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base-url", required=True, help="Public HTTPS base URL of the proxy"
    )
    args = parser.parse_args()

    s = get_settings()
    headers = {"xi-api-key": s.elevenlabs_api_key}
    with httpx.Client(timeout=30, headers=headers) as client:
        if s.elevenlabs_agent_id:
            agent = (
                client.get(f"{API}/agents/{s.elevenlabs_agent_id}")
                .raise_for_status()
                .json()
            )
            llm = agent["conversation_config"]["agent"]["prompt"]["custom_llm"]
            llm["url"] = f"{args.base_url.rstrip('/')}/v1/chat/completions"
            body = {"conversation_config": {"agent": {"prompt": {"custom_llm": llm}}}}
            client.patch(
                f"{API}/agents/{s.elevenlabs_agent_id}", json=body
            ).raise_for_status()
            print(f"Updated agent {s.elevenlabs_agent_id} -> {llm['url']}")
            return

        secret = client.post(
            f"{API}/secrets",
            json={
                "type": "new",
                "name": "voice-rag-proxy-bearer",
                "value": s.proxy_bearer_token,
            },
        )
        secret.raise_for_status()
        secret_id = secret.json()["secret_id"]
        created = client.post(
            f"{API}/agents/create",
            json=agent_config(args.base_url, secret_id, s.agent_model),
        )
        if created.status_code >= 400:
            raise SystemExit(
                f"Create failed {created.status_code}: {created.text[:800]}"
            )
        agent_id = created.json()["agent_id"]
        save_env("ELEVENLABS_AGENT_ID", agent_id)
        effective = client.get(f"{API}/agents/{agent_id}").json()["conversation_config"]
        print(f"Created agent {agent_id}")
        print(
            json.dumps(
                {
                    "agent": effective["agent"]["prompt"].get("built_in_tools"),
                    "tts": effective["tts"],
                },
                indent=2,
            )[:1500]
        )


if __name__ == "__main__":
    main()
