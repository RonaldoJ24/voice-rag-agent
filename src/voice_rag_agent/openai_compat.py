"""Translate between the OpenAI Chat Completions shape ElevenLabs speaks and Claude's Messages API."""

import json
import time
import uuid


def _text(content) -> str:
    """OpenAI content is a string or a list of parts; keep only the text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(part.get("text", "") for part in content if isinstance(part, dict))


def to_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """Split OpenAI messages into (system text, Claude messages).

    Assistant tool_calls become tool_use blocks and role "tool" messages become
    tool_result blocks, so ElevenLabs system tools (end_call, language detection)
    round-trip correctly.
    """
    system_parts: list[str] = []
    out: list[dict] = []

    def append(role: str, blocks: list[dict]) -> None:
        if not blocks:
            return
        if out and out[-1]["role"] == role:
            out[-1]["content"].extend(blocks)
        else:
            out.append({"role": role, "content": blocks})

    for msg in messages:
        role = msg.get("role")
        if role in ("system", "developer"):
            system_parts.append(_text(msg.get("content")))
        elif role == "user":
            text = _text(msg.get("content")).strip()
            if text:
                append("user", [{"type": "text", "text": text}])
        elif role == "assistant":
            blocks = []
            text = _text(msg.get("content")).strip()
            if text:
                blocks.append({"type": "text", "text": text})
            for call in msg.get("tool_calls") or []:
                fn = call.get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": call["id"],
                        "name": fn.get("name", ""),
                        "input": args,
                    }
                )
            append("assistant", blocks)
        elif role == "tool":
            append(
                "user",
                [
                    {
                        "type": "tool_result",
                        "tool_use_id": msg["tool_call_id"],
                        "content": _text(msg.get("content")) or "ok",
                    }
                ],
            )

    # Claude requires the conversation to start with a user turn.
    if out and out[0]["role"] != "user":
        out.insert(
            0, {"role": "user", "content": [{"type": "text", "text": "(call started)"}]}
        )
    return "\n\n".join(p for p in system_parts if p), out


def tools_to_anthropic(tools: list[dict] | None) -> list[dict]:
    converted = []
    for tool in tools or []:
        fn = tool.get("function", tool)
        params = fn.get("parameters") or {"type": "object", "properties": {}}
        converted.append(
            {
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": params,
            }
        )
    return converted


class ChunkWriter:
    """Builds OpenAI `chat.completion.chunk` SSE lines."""

    def __init__(self, model: str):
        self.id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
        self.model = model
        self.created = int(time.time())
        self._sent_role = False

    def _line(self, delta: dict, finish_reason: str | None = None) -> str:
        if not self._sent_role:
            delta = {"role": "assistant", **delta}
            self._sent_role = True
        payload = {
            "id": self.id,
            "object": "chat.completion.chunk",
            "created": self.created,
            "model": self.model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def text(self, text: str) -> str:
        return self._line({"content": text})

    def tool_calls(self, calls: list[dict]) -> str:
        """calls: [{"id", "name", "input"}] from Claude tool_use blocks."""
        return self._line(
            {
                "tool_calls": [
                    {
                        "index": i,
                        "id": c["id"],
                        "type": "function",
                        "function": {
                            "name": c["name"],
                            "arguments": json.dumps(c["input"]),
                        },
                    }
                    for i, c in enumerate(calls)
                ]
            }
        )

    def finish(self, reason: str) -> str:
        return self._line({}, finish_reason=reason) + "data: [DONE]\n\n"
