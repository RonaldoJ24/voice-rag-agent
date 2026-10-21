"""Trace events: one schema feeds the live panel, the eval logs and the latency tables.

Every event is {"session_id", "turn_id", "type", "t_ms", "cursor", ...payload}, where t_ms
is milliseconds since the turn started (the moment the proxy received the request) and
cursor orders events across sessions. Readers poll with the last cursor they saw.

Two stores with the same interface: in memory for local runs, DynamoDB on Lambda, where
the request that writes events and the one that streams them can land on different
instances.
"""

import json
import logging
import threading
import time
from collections import deque
from pathlib import Path

log = logging.getLogger(__name__)

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


def _cursor() -> str:
    return f"{time.time_ns():020d}"


class MemoryTraceBus:
    def __init__(self, log_path: Path | None = None, keep: int = 5000):
        self._events: deque = deque(maxlen=keep)
        self._lock = threading.Lock()
        self._log_path = log_path

    def emit(self, session_id: str, event: dict) -> None:
        assert event["type"] in EVENT_TYPES, event["type"]
        with self._lock:
            event = {"session_id": session_id, "cursor": _cursor(), **event}
            self._events.append(event)
        if self._log_path:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with self._log_path.open("a") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def since(self, cursor: str = "", session_id: str | None = None) -> list[dict]:
        with self._lock:
            events = [e for e in self._events if e["cursor"] > cursor]
        return [e for e in events if session_id in (None, e["session_id"])]


class DynamoTraceBus:
    """One partition ("trace") sorted by cursor. Fine for a demo; items expire after 7 days."""

    def __init__(self, table_name: str, region: str):
        import boto3

        self._table = boto3.resource("dynamodb", region_name=region).Table(table_name)

    def emit(self, session_id: str, event: dict) -> None:
        assert event["type"] in EVENT_TYPES, event["type"]
        event = {"session_id": session_id, "cursor": _cursor(), **event}
        self._table.put_item(
            Item={
                "pk": "trace",
                "sk": event["cursor"],
                "body": json.dumps(event, ensure_ascii=False),
                "expires_at": int(time.time()) + 7 * 86400,
            }
        )

    def since(self, cursor: str = "", session_id: str | None = None) -> list[dict]:
        from boto3.dynamodb.conditions import Key

        response = self._table.query(
            KeyConditionExpression=Key("pk").eq("trace") & Key("sk").gt(cursor or "0"),
            Limit=200,
        )
        events = [json.loads(item["body"]) for item in response["Items"]]
        return [e for e in events if session_id in (None, e["session_id"])]


class TurnTrace:
    """Helper bound to one turn so callers only pass the payload."""

    def __init__(self, bus, session_id: str, turn_id: str):
        self.bus, self.session_id, self.turn_id = bus, session_id, turn_id
        self.start = time.perf_counter()

    def ms(self) -> int:
        return int((time.perf_counter() - self.start) * 1000)

    def emit(self, type_: str, **payload) -> dict:
        event = {"turn_id": self.turn_id, "type": type_, "t_ms": self.ms(), **payload}
        try:
            self.bus.emit(self.session_id, event)
        except Exception:  # tracing must never break the spoken answer
            log.exception("could not store trace event %s", type_)
        return event
