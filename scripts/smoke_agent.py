"""Run one text turn through the agent with a fake retriever. Costs a fraction of a cent on Haiku."""

import asyncio
import json
import sys

import anthropic

from voice_rag_agent.agent import TurnResult, VoiceAgent
from voice_rag_agent.config import get_settings
from voice_rag_agent.costs import Ledger
from voice_rag_agent.openai_compat import ChunkWriter
from voice_rag_agent.retrieval.base import Hit
from voice_rag_agent.trace import TraceBus, TurnTrace


class FakeRetriever:
    name = "fake"

    def search(self, query, lang=None, k=5):
        return [
            Hit(
                "tutorial/background-tasks.md#using-backgroundtasks",
                "tutorial/background-tasks.md",
                "en",
                "Background Tasks",
                "Using BackgroundTasks",
                "https://fastapi.tiangolo.com/tutorial/background-tasks/",
                "Declare a parameter of type BackgroundTasks in your path operation function and call "
                "background_tasks.add_task(func, *args). FastAPI runs the task after sending the response.",
                0.9,
            )
        ]


async def main(question: str):
    s = get_settings()
    bus = TraceBus()
    agent = VoiceAgent(
        anthropic.AsyncAnthropic(),
        FakeRetriever(),
        Ledger(s.spend_ledger, s.spend_pause_usd),
        model=sys.argv[2] if len(sys.argv) > 2 else s.agent_model,
    )
    result = TurnResult()
    trace = TurnTrace(bus, "smoke", "t1")
    async for _ in agent.run(
        "",
        [{"role": "user", "content": [{"type": "text", "text": question}]}],
        [],
        trace,
        ChunkWriter(agent.model),
        result,
    ):
        pass
    for e in bus.events("smoke"):
        print(
            json.dumps(
                {k: v for k, v in e.items() if k not in ("session_id", "turn_id")},
                ensure_ascii=False,
            )[:300]
        )
    print(
        f"cited={result.cited} answered_from_docs={result.answered_from_docs} usd={result.usd:.6f}"
    )


asyncio.run(main(sys.argv[1]))
