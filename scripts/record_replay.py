"""Record scripted conversations through the real proxy for the page's replay mode.

    uv run scripts/record_replay.py            # writes web/replays/en.json and es.json

Each turn goes through the same /v1/chat/completions endpoint ElevenLabs calls (in process,
no server needed), with real Claude and real retrieval. The replay keeps the time of every
streamed text chunk and every trace event, so the page can play it back at true speed
without a microphone, a demo code or any API cost. The caller's side is typed text, not
speech, so speech recognition and voice timing are not part of the recording.
"""

import asyncio
import datetime as dt
import json
import time
import uuid

import httpx

GREETING = {
    "en": "Hi! Ask me anything about FastAPI.",
    "es": "¡Hola! Pregúntame lo que quieras sobre FastAPI.",
}
SCRIPTS = {
    "en": [
        "Hi! What can you help me with?",
        "How do I let people upload a file to my API?",
        "Can I accept several files in one request?",
    ],
    "es": [
        "¿Dónde pongo código que corre una vez al iniciar la app, como cargar un modelo?",
        "¿Y cómo lo pruebo?",
        "¿Cómo cobro pagos con Stripe en mi backend?",
    ],
}
END_CALL_TOOL = {
    "type": "function",
    "function": {
        "name": "end_call",
        "description": "End the call",
        "parameters": {"type": "object", "properties": {}},
    },
}


async def record(lang: str, client: httpx.AsyncClient, token: str) -> dict:
    session_id = f"replay-{lang}-{uuid.uuid4().hex[:6]}"
    history = [{"role": "assistant", "content": GREETING[lang]}]
    turns = []
    for question in SCRIPTS[lang]:
        history.append({"role": "user", "content": question})
        body = {
            "model": "custom",
            "stream": True,
            "messages": [{"role": "system", "content": "Platform prompt."}, *history],
            "tools": [END_CALL_TOOL],
            "elevenlabs_extra_body": {"session_id": session_id},
        }
        started, chunks, text = time.perf_counter(), [], ""
        async with client.stream(
            "POST",
            "/v1/chat/completions",
            json=body,
            headers={"Authorization": f"Bearer {token}"},
            timeout=60,
        ) as r:
            r.raise_for_status()
            async for line in r.aiter_lines():
                if not line.startswith("data: {"):
                    continue
                delta = json.loads(line[6:])["choices"][0]["delta"].get("content")
                if delta:
                    chunks.append(
                        [round((time.perf_counter() - started) * 1000), delta]
                    )
                    text += delta
        history.append({"role": "assistant", "content": text.strip()})
        turns.append({"user": question, "chunks": chunks})

    events = (await client.get(f"/trace/{session_id}")).json()["events"]
    by_turn: dict[str, list] = {}
    for e in events:
        by_turn.setdefault(e["turn_id"], []).append(e)
    # Trace turns come back in the order they happened, one per scripted question.
    for turn, evs in zip(turns, by_turn.values(), strict=True):
        turn["events"] = evs
    return {"lang": lang, "greeting": GREETING[lang], "turns": turns}


async def main() -> None:
    from voice_rag_agent.app import app
    from voice_rag_agent.config import ROOT, get_settings

    s = get_settings()
    out_dir = ROOT / "web/replays"
    out_dir.mkdir(exist_ok=True)
    transport = httpx.ASGITransport(app=app)
    # ASGITransport skips startup, so run the app's lifespan here to build the agent.
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(transport=transport, base_url="http://replay") as client,
    ):
        for lang in SCRIPTS:
            replay = await record(lang, client, s.proxy_bearer_token)
            replay["recorded"] = {
                "date": dt.date.today().isoformat(),
                "model": s.agent_model,
                "retriever": s.retriever,
                "s3vectors_index": s.s3vectors_index,
                "input": "typed text through the proxy (no speech recognition)",
            }
            path = out_dir / f"{lang}.json"
            path.write_text(json.dumps(replay, ensure_ascii=False, indent=1))
            spent = sum(
                e.get("usd", 0)
                for t in replay["turns"]
                for e in t["events"]
                if e["type"] == "answer_done"
            )
            print(
                f"{path.relative_to(ROOT)}: {len(replay['turns'])} turns, ${spent:.4f}"
            )
            for t in replay["turns"]:
                said = "".join(c[1] for c in t["chunks"])
                print(f"  > {t['user']}\n    {said[:220]}")


if __name__ == "__main__":
    asyncio.run(main())
