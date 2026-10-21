"""Trace events: one schema feeds the live panel, the eval logs and the latency tables.

Every event is {"session_id", "turn_id", "type", "t_ms", ...payload}, where t_ms is
milliseconds since the turn started (the moment the proxy received the request).
"""

import asyncio
import json
import time
from collections import defaultdict, deque
from pathlib import Path

EVENT_TYPES = {
    "user_utterance",
    "decision",
    "tool_call",
    "retrieval_hits",
    "llm_first_token",
    "answer_done",
    "external_tool",
    "error",
}


class TraceBus:
    """In-memory store plus live subscribers. Swapped for DynamoDB on AWS."""

    def __init__(self, log_path: Path | None = None, keep_per_session: int = 500):
        self._events: dict[str, deque] = defaultdict(
            lambda: deque(maxlen=keep_per_session)
        )
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)
        self._log_path = log_path
        self.latest_session: str | None = None

    def emit(self, session_id: str, event: dict) -> None:
        assert event["type"] in EVENT_TYPES, event["type"]
        event = {"session_id": session_id, **event}
        self._events[session_id].append(event)
        self.latest_session = session_id
        for queue in list(self._subscribers[session_id]) + list(self._subscribers["*"]):
            queue.put_nowait(event)
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def events(self, session_id: str, after: int = 0) -> list[dict]:
        return list(self._events.get(session_id, []))[after:]

    def subscribe(self, session_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[session_id].discard(queue)


class TurnTrace:
    """Helper bound to one turn so callers only pass the payload."""

    def __init__(self, bus: TraceBus, session_id: str, turn_id: str):
        self.bus, self.session_id, self.turn_id = bus, session_id, turn_id
        self.start = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)

    def emit(self, type_: str, **payload) -> dict:
        event = {"turn_id": self.turn_id, "type": type_, "t_ms": self.ms(), **payload}
        self.bus.emit(self.session_id, event)
        return event
