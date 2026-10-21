"""One spoken turn: Claude decides whether to search, answers from the hits, and cites them.

Text streams to ElevenLabs as soon as Claude writes it. Every step is also emitted as a
trace event, which is what the live panel and the evals read.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import anthropic

from .costs import Ledger, SpendLimitReached, cost_usd
from .openai_compat import ChunkWriter
from .prompts import (
    INTERNAL_TOOLS,
    RECORD_SOURCES_TOOL,
    SEARCH_DOCS_TOOL,
    SYSTEM_PROMPT,
)
from .retrieval.base import Hit, Retriever
from .trace import TurnTrace

SPANISH_HINTS = re.compile(
    r"[¿¡ñáéíóú]|\b(cómo|como|qué|que|para|una|los|las|del|puedo|hago)\b", re.IGNORECASE
)


def guess_language(text: str) -> str:
    return "es" if len(SPANISH_HINTS.findall(text)) >= 2 else "en"


def model_params(model: str, effort: str) -> dict:
    """Latency-first settings per model.

    Measured 2026-10-20 on Haiku 5.5 at effort low: with adaptive thinking the first
    response was a silent tool call (no spoken filler); with thinking disabled the
    filler phrase started at ~580 ms. Speech needs the filler, so thinking is off.
    """
    if model.startswith("claude-sonnet-5-5"):
        return {
            "thinking": {"type": "between_tools"},
            "output_config": {"effort": effort},
        }
    return {"thinking": {"type": "disabled"}, "output_config": {"effort": effort}}


def format_hits(hits: list[Hit]) -> str:
    if not hits:
        return "No matching sections."
    return "\n\n".join(
        f"[section_id: {h.section_id} | lang: {h.lang} | {h.title} > {h.heading}]\n{h.text}"
        for h in hits
    )


@dataclass
class TurnResult:
    text: str = ""
    cited: list[str] = field(default_factory=list)
    answered_from_docs: bool | None = None
    searches: list[dict] = field(default_factory=list)
    external_calls: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    usd: float = 0.0
    first_token_ms: int | None = None


class VoiceAgent:
    def __init__(
        self,
        client: anthropic.AsyncAnthropic,
        retriever: Retriever,
        ledger: Ledger,
        model: str,
        effort: str = "low",
        max_tokens: int = 1024,
        max_rounds: int = 3,
        top_k: int = 5,
    ):
        self.client, self.retriever, self.ledger = client, retriever, ledger
        self.model, self.effort, self.max_tokens = model, effort, max_tokens
        self.max_rounds, self.top_k = max_rounds, top_k

    async def run(
        self,
        platform_system: str,
        messages: list[dict],
        platform_tools: list[dict],
        trace: TurnTrace,
        writer: ChunkWriter,
        result: TurnResult | None = None,
    ) -> AsyncIterator[str]:
        """Yield OpenAI SSE lines for one turn. `result` collects what the evals need."""
        result = result if result is not None else TurnResult()
        last_user = next(
            (
                b["text"]
                for m in reversed(messages)
                if m["role"] == "user"
                for b in m["content"]
                if b["type"] == "text"
            ),
            "",
        )
        trace.emit("user_utterance", text=last_user, language=guess_language(last_user))

        system = SYSTEM_PROMPT + (
            f"\n\nPlatform notes:\n{platform_system}" if platform_system else ""
        )
        tools = [SEARCH_DOCS_TOOL, RECORD_SOURCES_TOOL] + [
            t for t in platform_tools if t["name"] not in INTERNAL_TOOLS
        ]
        convo = list(messages)

        try:
            for round_no in range(1, self.max_rounds + 1):
                self.ledger.check()
                preamble = ""
                async with self.client.messages.stream(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=system,
                    messages=convo,
                    tools=tools,
                    **model_params(self.model, self.effort),
                ) as stream:
                    async for event in stream:
                        if event.type == "text":
                            if result.first_token_ms is None:
                                result.first_token_ms = trace.ms()
                                trace.emit("llm_first_token", round=round_no)
                            preamble += event.text
                            result.text += event.text
                            yield writer.text(event.text)
                    final = await stream.get_final_message()

                usd = self.ledger.record(self.model, final.usage, purpose="agent_turn")
                result.input_tokens += final.usage.input_tokens
                result.output_tokens += final.usage.output_tokens
                result.usd += usd

                tool_uses = [b for b in final.content if b.type == "tool_use"]
                for block in tool_uses:
                    if block.name == "record_sources":
                        result.cited = list(block.input.get("section_ids", []))
                        result.answered_from_docs = bool(
                            block.input.get("answered_from_docs")
                        )

                external = [b for b in tool_uses if b.name not in INTERNAL_TOOLS]
                if external:
                    calls = [
                        {"id": b.id, "name": b.name, "input": b.input} for b in external
                    ]
                    result.external_calls.extend(calls)
                    trace.emit(
                        "external_tool",
                        calls=[{"name": c["name"], "input": c["input"]} for c in calls],
                    )
                    yield writer.tool_calls(calls)
                    break

                searches = [b for b in tool_uses if b.name == "search_docs"]
                if not searches:
                    if round_no == 1 and not tool_uses:
                        trace.emit(
                            "decision", action="answer_directly", said=preamble.strip()
                        )
                    break

                tool_results = []
                for block in searches:
                    query = str(block.input.get("query", "")).strip()
                    lang = (
                        block.input.get("language")
                        if block.input.get("language") in ("en", "es")
                        else None
                    )
                    trace.emit("decision", action="search", said=preamble.strip())
                    trace.emit(
                        "tool_call", tool="search_docs", query=query, language=lang
                    )
                    started = trace.ms()
                    hits = await asyncio.to_thread(
                        self.retriever.search, query, lang, self.top_k
                    )
                    trace.emit(
                        "retrieval_hits",
                        retriever=self.retriever.name,
                        ms=trace.ms() - started,
                        hits=[
                            {k: v for k, v in h.to_dict().items() if k != "text"}
                            | {"score": round(h.score, 4)}
                            for h in hits
                        ],
                    )
                    result.searches.append(
                        {
                            "query": query,
                            "language": lang,
                            "section_ids": [h.section_id for h in hits],
                        }
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": format_hits(hits),
                        }
                    )
                # record_sources in the same response still needs a result so the history stays valid.
                for block in tool_uses:
                    if block.name == "record_sources":
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": "recorded",
                            }
                        )
                convo += [
                    {"role": "assistant", "content": final.content},
                    {"role": "user", "content": tool_results},
                ]
                if result.text and not result.text.endswith((" ", "\n")):
                    result.text += " "
                    yield writer.text(" ")

            trace.emit(
                "answer_done",
                text=result.text.strip(),
                cited=result.cited,
                answered_from_docs=result.answered_from_docs,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                usd=round(result.usd, 6),
                first_token_ms=result.first_token_ms,
                model=self.model,
            )
            yield writer.finish("tool_calls" if result.external_calls else "stop")

        except (SpendLimitReached, anthropic.APIError) as exc:
            trace.emit("error", where="llm", message=str(exc)[:300])
            sorry = "Sorry, I hit a problem on my side. Please try again in a moment."
            result.text += sorry
            yield writer.text(sorry)
            yield writer.finish("stop")


__all__ = ["TurnResult", "VoiceAgent", "cost_usd", "guess_language"]
