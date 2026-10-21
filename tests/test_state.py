from types import SimpleNamespace

import pytest

from voice_rag_agent.costs import DynamoLedger, SpendLimitReached
from voice_rag_agent.trace import MemoryTraceBus, TurnTrace


def test_memory_bus_returns_events_after_cursor_and_filters_by_session():
    bus = MemoryTraceBus()
    TurnTrace(bus, "a", "t1").emit("user_utterance", text="hola")
    first = bus.since()
    TurnTrace(bus, "b", "t2").emit("decision", action="search")

    assert [e["session_id"] for e in bus.since()] == ["a", "b"]
    assert [e["session_id"] for e in bus.since(first[-1]["cursor"])] == ["b"]
    assert [e["type"] for e in bus.since(session_id="a")] == ["user_utterance"]


def test_trace_errors_never_reach_the_caller():
    class Broken:
        def emit(self, *_):
            raise RuntimeError("store down")

    event = TurnTrace(Broken(), "a", "t1").emit("error", message="x")
    assert event["type"] == "error"


class FakeTable:
    def __init__(self):
        self.item = None

    def get_item(self, Key):
        return {"Item": self.item} if self.item else {}

    def update_item(self, Key, UpdateExpression, ExpressionAttributeValues):
        item = self.item or {"usd": 0, "responses": 0}
        item["usd"] += ExpressionAttributeValues[":usd"]
        item["responses"] += ExpressionAttributeValues[":one"]
        self.item = item


def test_dynamo_ledger_adds_up_and_pauses():
    ledger = DynamoLedger.__new__(DynamoLedger)
    ledger._table, ledger.pause_usd = FakeTable(), 0.001
    usage = SimpleNamespace(input_tokens=5000, output_tokens=1000)

    ledger.check()
    ledger.record("claude-haiku-5-5", usage, purpose="test")
    assert ledger.total() == pytest.approx(0.001)
    with pytest.raises(SpendLimitReached):
        ledger.check()
