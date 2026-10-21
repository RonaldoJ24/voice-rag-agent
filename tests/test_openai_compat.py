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


def test_agent_answers_after_recording_sources_first():
    """Sonnet sometimes calls record_sources before speaking; the loop must let it answer."""
    import asyncio
    from types import SimpleNamespace

    from voice_rag_agent.agent import TurnResult, VoiceAgent
    from voice_rag_agent.openai_compat import ChunkWriter
    from voice_rag_agent.trace import MemoryTraceBus, TurnTrace

    def block(kind, **kw):
        return SimpleNamespace(type=kind, **kw)

    rounds = [
        (
            "Let me check the docs.",
            [
                block(
                    "tool_use",
                    id="t1",
                    name="search_docs",
                    input={"query": "cors", "language": "en"},
                )
            ],
        ),
        (
            "",
            [
                block(
                    "tool_use",
                    id="t2",
                    name="record_sources",
                    input={"section_ids": ["a#b"], "answered_from_docs": True},
                )
            ],
        ),
        ("Add CORSMiddleware to your app.", []),
    ]

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
            content = (
                [block("text", text=self.text)] if self.text else []
            ) + self.tools
            return SimpleNamespace(
                content=content, usage=SimpleNamespace(input_tokens=1, output_tokens=1)
            )

    class Client:
        def __init__(self):
            self.messages = self

        def stream(self, **_):
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

    agent = VoiceAgent(Client(), Retriever(), Ledger(), "claude-sonnet-5-5")
    result = TurnResult()
    messages = [{"role": "user", "content": [{"type": "text", "text": "cors?"}]}]

    async def run():
        trace = TurnTrace(MemoryTraceBus(), "s", "t")
        async for _ in agent.run("", messages, [], trace, ChunkWriter("m"), result):
            pass

    asyncio.run(run())
    assert "CORSMiddleware" in result.text
    assert result.cited == ["a#b"]
