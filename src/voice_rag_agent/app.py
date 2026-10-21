"""HTTP surface: the Custom LLM endpoint ElevenLabs calls, the trace feed, and the demo page."""

import logging
import secrets
import uuid
from contextlib import asynccontextmanager

import anthropic
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from .agent import TurnResult, VoiceAgent
from .config import ROOT, get_settings
from .costs import DynamoLedger, Ledger
from .openai_compat import ChunkWriter, to_anthropic, tools_to_anthropic
from .retrieval.base import Retriever
from .trace import DynamoTraceBus, MemoryTraceBus, TurnTrace, trace_cursor


def build_retriever(name: str) -> Retriever:
    if name == "local":
        from .retrieval.local import LocalHybridRetriever

        return LocalHybridRetriever.load(get_settings().index_dir)
    if name == "bm25":
        from .retrieval.local import Bm25Retriever

        return Bm25Retriever.load(get_settings().index_dir)
    if name == "aws":
        from .retrieval.aws import AwsHybridRetriever

        s = get_settings()
        return AwsHybridRetriever.load(
            s.index_dir, s.s3vectors_bucket, s.s3vectors_index, s.aws_region
        )
    raise ValueError(f"Unknown retriever {name!r}")


def build_state(s):
    """Trace store and spend ledger for this deployment (see Settings.state_backend)."""
    if s.state_backend == "local":
        return MemoryTraceBus(log_path=s.trace_log), Ledger(
            s.spend_ledger, s.spend_pause_usd
        )
    if s.state_backend == "dynamodb":
        return DynamoTraceBus(s.dynamodb_table, s.aws_region), DynamoLedger(
            s.dynamodb_table, s.aws_region, s.spend_pause_usd
        )
    raise ValueError(f"Unknown state backend {s.state_backend!r}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    app.state.bus, ledger = build_state(s)
    app.state.agent = VoiceAgent(
        client=anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None),
        retriever=build_retriever(s.retriever),
        ledger=ledger,
        model=s.agent_model,
        effort=s.agent_effort,
        max_tokens=s.agent_max_tokens,
        max_rounds=s.max_tool_rounds,
        top_k=s.top_k,
    )
    yield


app = FastAPI(title="Voice RAG agent", lifespan=lifespan)
log = logging.getLogger("uvicorn.error")


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
    log.info("custom LLM request: extra body keys %s", sorted(extra))
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


@app.get("/trace")
async def trace_feed(request: Request, session_id: str, after: str = ""):
    """One session's events newer than cursor `after`. The live panel polls this.

    session_id is required so one visitor never sees another visitor's questions.
    """
    events = await run_in_threadpool(request.app.state.bus.since, after, session_id)
    cursor = events[-1]["cursor"] if events else after
    return {"events": events, "cursor": cursor}


@app.get("/trace/{session_id}")
async def trace_session(session_id: str, request: Request):
    """Every stored event of one session (used by the smoke scripts)."""
    events = await run_in_threadpool(request.app.state.bus.since, "", session_id)
    return {"session_id": session_id, "events": events}


@app.get("/api/session")
async def new_session(x_demo_code: str | None = Header(default=None)):
    """Signed URL for the private ElevenLabs agent plus a session ID that tags this call's trace."""
    s = get_settings()
    if s.demo_access_code and not secrets.compare_digest(
        x_demo_code or "", s.demo_access_code
    ):
        raise HTTPException(status_code=401, detail="wrong demo code")
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
    return {
        "signed_url": r.json()["signed_url"],
        "session_id": uuid.uuid4().hex[:12],
        # The panel polls from here, so older calls never show up in this one.
        "cursor": trace_cursor(),
    }


@app.get("/health")
async def health(request: Request):
    agent: VoiceAgent = request.app.state.agent
    return JSONResponse(
        {
            "ok": True,
            "model": agent.model,
            "retriever": agent.retriever.name,
            "spent_usd": round(await run_in_threadpool(agent.ledger.total), 4),
        }
    )


@app.get("/")
async def index():
    return FileResponse(ROOT / "web" / "index.html")
