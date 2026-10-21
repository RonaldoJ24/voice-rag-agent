"""HTTP surface: the Custom LLM endpoint ElevenLabs calls, the trace feed, and the demo page."""

import asyncio
import json
import secrets
import uuid
from contextlib import asynccontextmanager

import anthropic
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .agent import TurnResult, VoiceAgent
from .config import ROOT, get_settings
from .costs import Ledger
from .openai_compat import ChunkWriter, to_anthropic, tools_to_anthropic
from .retrieval.base import Retriever
from .trace import TraceBus, TurnTrace


def build_retriever(name: str) -> Retriever:
    if name == "local":
        from .retrieval.local import LocalHybridRetriever

        return LocalHybridRetriever.load(get_settings().index_dir)
    raise ValueError(f"Unknown retriever {name!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.bus = TraceBus(log_path=s.trace_log)
    app.state.agent = VoiceAgent(
        client=anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None),
        retriever=build_retriever(s.retriever),
        ledger=Ledger(s.spend_ledger, s.spend_pause_usd),
        model=s.agent_model,
        effort=s.agent_effort,
        max_tokens=s.agent_max_tokens,
        max_rounds=s.max_tool_rounds,
        top_k=s.top_k,
    )
    yield


app = FastAPI(title="Voice RAG agent", lifespan=lifespan)


def _check_bearer(authorization: str | None) -> None:
    token = get_settings().proxy_bearer_token
    if token and not secrets.compare_digest(authorization or "", f"Bearer {token}"):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/v1/chat/completions")
async def chat_completions(
    request: Request, authorization: str | None = Header(default=None)
):
    """OpenAI-compatible streaming endpoint used by the ElevenLabs Custom LLM setting."""
    _check_bearer(authorization)
    body = await request.json()
    extra = body.get("elevenlabs_extra_body") or {}
    session_id = str(
        extra.get("session_id") or extra.get("conversation_id") or "latest"
    )
    system, messages = to_anthropic(body.get("messages", []))
    if not messages:
        raise HTTPException(status_code=400, detail="no messages")

    agent: VoiceAgent = request.app.state.agent
    trace = TurnTrace(request.app.state.bus, session_id, turn_id=uuid.uuid4().hex[:8])
    writer = ChunkWriter(model=agent.model)
    stream = agent.run(
        system,
        messages,
        tools_to_anthropic(body.get("tools")),
        trace,
        writer,
        TurnResult(),
    )
    return StreamingResponse(
        stream, media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.get("/trace/{session_id}")
async def trace_poll(session_id: str, request: Request, after: int = 0):
    """Polling fallback: events after index `after`."""
    bus: TraceBus = request.app.state.bus
    if session_id == "latest" and bus.latest_session:
        session_id = bus.latest_session
    return {"session_id": session_id, "events": bus.events(session_id, after)}


@app.get("/trace/{session_id}/stream")
async def trace_stream(session_id: str, request: Request):
    """Server-sent events for the live panel. Use session "*" to follow every session."""
    bus: TraceBus = request.app.state.bus
    queue = bus.subscribe(session_id)

    async def events():
        try:
            yield ": connected\n\n"
            while not await request.is_disconnected():
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            bus.unsubscribe(session_id, queue)

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@app.get("/api/session")
async def new_session():
    """Signed URL for the private ElevenLabs agent plus a session ID that tags this call's trace."""
    s = get_settings()
    if not (s.elevenlabs_api_key and s.elevenlabs_agent_id):
        raise HTTPException(status_code=503, detail="ElevenLabs agent not configured")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            "https://api.elevenlabs.io/v1/convai/conversation/get-signed-url",
            params={"agent_id": s.elevenlabs_agent_id},
            headers={"xi-api-key": s.elevenlabs_api_key},
        )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="could not get a signed URL")
    return {"signed_url": r.json()["signed_url"], "session_id": uuid.uuid4().hex[:12]}


@app.get("/health")
async def health(request: Request):
    agent: VoiceAgent = request.app.state.agent
    return JSONResponse(
        {
            "ok": True,
            "model": agent.model,
            "retriever": agent.retriever.name,
            "spent_usd": round(agent.ledger.total(), 4),
        }
    )


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")
