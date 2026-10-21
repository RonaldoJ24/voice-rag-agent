"""Send one ElevenLabs-shaped request to the proxy and print the streamed answer and its trace.

uv run scripts/smoke_proxy.py "¿Cómo subo archivos?" [--base-url https://...]
"""

import argparse
import json
import uuid

import httpx

from voice_rag_agent.config import get_settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("question")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    session_id = f"smoke-{uuid.uuid4().hex[:6]}"
    body = {
        "model": "custom",
        "stream": True,
        "messages": [
            {"role": "system", "content": "Platform prompt."},
            {"role": "assistant", "content": "Hi! Ask me anything about FastAPI."},
            {"role": "user", "content": args.question},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "end_call",
                    "description": "End the call",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ],
        "elevenlabs_extra_body": {"session_id": session_id},
    }
    headers = {"Authorization": f"Bearer {get_settings().proxy_bearer_token}"}
    text, finish = "", None
    with httpx.stream(
        "POST",
        f"{args.base_url}/v1/chat/completions",
        json=body,
        headers=headers,
        timeout=60,
    ) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if line.startswith("data: {"):
                choice = json.loads(line[6:])["choices"][0]
                text += choice["delta"].get("content", "")
                finish = choice["finish_reason"] or finish
    print(f"SPOKEN: {text}\nFINISH: {finish}\n")
    for e in httpx.get(f"{args.base_url}/trace/{session_id}").json()["events"]:
        detail = {
            k: e[k]
            for k in (
                "action",
                "query",
                "language",
                "cited",
                "answered_from_docs",
                "usd",
            )
            if k in e
        }
        hits = [h["section_id"] for h in e.get("hits", [])][:3]
        print(f"{e['t_ms']:>6} ms  {e['type']:<16} {detail} {hits if hits else ''}")


if __name__ == "__main__":
    main()
