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
