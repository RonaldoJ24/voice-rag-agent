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
# Eleven v4 Turbo: 90+ languages at ~100 ms, so one voice model serves EN and ES.
# (Flash v2 is English only, so Spanish answers came out with an English accent.)
TTS_MODEL = "eleven_v4_turbo"


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
                        "url": f"{base_url.rstrip('/')}/v1",
                        "model_id": model,
                        "api_key": {"secret_id": secret_id},
                        "api_type": "chat_completions",
                    },
                    "built_in_tools": {
                        name: {
                            "type": "system",
                            "name": name,
                            "description": "",
                            "params": {"system_tool_type": name},
                        }
                        for name in ("end_call", "language_detection")
                    },
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
        "platform_settings": PLATFORM_SETTINGS,
    }


# Private agent (signed URLs only). The page tags each call with customLlmExtraBody
# {"session_id"} so the trace panel can follow it; ElevenLabs ends the call with error
# 1008 unless the agent allows that override.
PLATFORM_SETTINGS = {
    "auth": {"enable_auth": True},
    "overrides": {"custom_llm_extra_body": True},
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
            prompt = agent["conversation_config"]["agent"]["prompt"]
            prompt["custom_llm"]["url"] = f"{args.base_url.rstrip('/')}/v1"
            body = {
                "conversation_config": {
                    "agent": {"prompt": prompt},
                    "tts": {"model_id": TTS_MODEL, "voice_id": VOICE_ID},
                },
                "platform_settings": PLATFORM_SETTINGS,
            }
            r = client.patch(f"{API}/agents/{s.elevenlabs_agent_id}", json=body)
            if r.status_code >= 400:
                raise SystemExit(f"Update failed {r.status_code}: {r.text[:800]}")
            print(
                f"Updated agent {s.elevenlabs_agent_id} -> {prompt['custom_llm']['url']}"
            )
            return

        existing = (
            client.get(f"{API}/secrets").raise_for_status().json().get("secrets", [])
        )
        secret_id = next(
            (x["secret_id"] for x in existing if x["name"] == "voice-rag-proxy-bearer"),
            None,
        )
        if not secret_id:
            secret = client.post(
                f"{API}/secrets",
                json={
                    "type": "new",
                    "name": "voice-rag-proxy-bearer",
                    "value": s.proxy_bearer_token,
                },
            )
            secret_id = secret.raise_for_status().json()["secret_id"]
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
