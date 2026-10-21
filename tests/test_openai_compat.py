import json

from voice_rag_agent.openai_compat import ChunkWriter, to_anthropic, tools_to_anthropic


def test_tool_calls_round_trip_as_tool_use_and_tool_result():
    system, msgs = to_anthropic(
        [
            {"role": "system", "content": "be brief"},
            {"role": "assistant", "content": "Hi! Ask me about FastAPI."},
            {"role": "user", "content": "bye"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "end_call", "arguments": "{}"},
                    }
                ],
            },
            {"role": "tool", "tool_call_id": "call_1", "content": "ended"},
        ]
    )
    assert system == "be brief"
    assert (
        msgs[0]["role"] == "user"
    )  # synthetic opener because the call starts with the agent's greeting
    assert msgs[1]["content"][0]["text"].startswith("Hi!")
    assert msgs[3]["content"][0] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "end_call",
        "input": {},
    }
    assert msgs[4]["content"][0]["type"] == "tool_result"


def test_tools_and_chunks_have_openai_shape():
    tools = tools_to_anthropic(
        [
            {
                "type": "function",
                "function": {"name": "end_call", "parameters": {"type": "object"}},
            }
        ]
    )
    assert tools == [
        {"name": "end_call", "description": "", "input_schema": {"type": "object"}}
    ]
    w = ChunkWriter("claude-haiku-5-5")
    first = json.loads(w.text("Hola").removeprefix("data: "))
    assert first["choices"][0]["delta"] == {"role": "assistant", "content": "Hola"}
    tail = w.finish("stop")
    assert tail.endswith("data: [DONE]\n\n")


def test_speakable_drops_markdown_marks():
    from voice_rag_agent.agent import speakable

    assert speakable("use `app.add_middleware` **now**") == "use app.add middleware now"


def _tool(id_, name, **input_):
    from types import SimpleNamespace

    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def _run_scripted(rounds, **agent_kw):
    """Run VoiceAgent against scripted model rounds of (text, tool_uses).

    Returns the TurnResult and the keyword arguments of every model call.
    """
    import asyncio
    from types import SimpleNamespace

    from voice_rag_agent.agent import TurnResult, VoiceAgent
    from voice_rag_agent.openai_compat import ChunkWriter
    from voice_rag_agent.trace import MemoryTraceBus, TurnTrace

    calls = []

    class Stream:
        def __init__(self, text, tools):
            self.text, self.tools = text, tools

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return False

        def __aiter__(self):
            async def gen():
                if self.text:
                    yield SimpleNamespace(type="text", text=self.text)

            return gen()

        async def get_final_message(self):
            text = [SimpleNamespace(type="text", text=self.text)] if self.text else []
            return SimpleNamespace(
                content=text + self.tools,
                usage=SimpleNamespace(input_tokens=1, output_tokens=1),
            )

    class Client:
        def __init__(self):
            self.messages = self

        def stream(self, **kw):
            calls.append(kw)
            return Stream(*rounds.pop(0))

    class Ledger:
        def check(self):
            pass

        def record(self, *_args, **_kw):
            return 0.0

    class Retriever:
        name = "fake"

        def search(self, *_):
            return []

    agent = VoiceAgent(Client(), Retriever(), Ledger(), "claude-sonnet-5-5", **agent_kw)
    result = TurnResult()
    messages = [{"role": "user", "content": [{"type": "text", "text": "cors?"}]}]

    async def run():
        trace = TurnTrace(MemoryTraceBus(), "s", "t")
        async for _ in agent.run("", messages, [], trace, ChunkWriter("m"), result):
            pass

    asyncio.run(run())
    return result, calls


def test_agent_answers_after_recording_sources_first():
    """Sonnet sometimes calls record_sources before speaking; the loop must let it answer."""
    result, _ = _run_scripted(
        [
            (
                "Let me check the docs.",
                [_tool("t1", "search_docs", query="cors", language="en")],
            ),
            (
                "",
                [
                    _tool(
                        "t2",
                        "record_sources",
                        section_ids=["a#b"],
                        answered_from_docs=True,
                    )
                ],
            ),
            ("Add CORSMiddleware to your app.", []),
        ]
    )
    assert "CORSMiddleware" in result.text
    assert result.cited == ["a#b"]


def test_agent_speaks_after_using_every_tool_round():
    """Two searches and early sources use up the rounds; a tools-off round still answers."""
    result, calls = _run_scripted(
        [
            ("Let me check.", [_tool("t1", "search_docs", query="forms")]),
            ("One more look.", [_tool("t2", "search_docs", query="Form data")]),
            ("", [_tool("t3", "record_sources", section_ids=["f#d"])]),
            ("Declare the fields with Form.", []),
        ],
        max_rounds=3,
    )
    assert "Form" in result.text.split("look.")[-1]
    assert len(calls) == 4
    assert calls[-1]["tool_choice"] == {"type": "none"}
    assert all("tool_choice" not in c for c in calls[:-1])
