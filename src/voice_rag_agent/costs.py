"""Claude prices and a spend ledger that stops work before the budget runs out."""

import json
import time
from dataclasses import dataclass
from pathlib import Path

# USD per 1M tokens, first-party Claude API (checked 2026-10-20).
PRICES = {
    "claude-haiku-5-5": {
        "input": 0.10,
        "output": 0.50,
        "cache_read": 0.01,
        "cache_write": 0.125,
    },
    "claude-sonnet-5-5": {
        "input": 2.00,
        "output": 10.00,
        "cache_read": 0.20,
        "cache_write": 2.50,
    },
    "claude-opus-5-5": {
        "input": 4.00,
        "output": 20.00,
        "cache_read": 0.20,
        "cache_write": 5.00,
    },
}


class SpendLimitReached(RuntimeError):
    pass


def cost_usd(model: str, usage) -> float:
    """Cost of one response, from its `usage` object."""
    p = PRICES[model]
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    return (
        usage.input_tokens * p["input"]
        + usage.output_tokens * p["output"]
        + cache_read * p["cache_read"]
        + cache_write * p["cache_write"]
    ) / 1_000_000


@dataclass
class Ledger:
    path: Path
    pause_usd: float

    def total(self) -> float:
        if not self.path.exists():
            return 0.0
        with self.path.open() as f:
            return sum(json.loads(line)["usd"] for line in f if line.strip())

    def check(self) -> None:
        spent = self.total()
        if spent >= self.pause_usd:
            raise SpendLimitReached(
                f"Spent ${spent:.2f}, pause threshold is ${self.pause_usd:.2f}"
            )

    def record(self, model: str, usage, purpose: str) -> float:
        usd = cost_usd(model, usage)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": round(time.time(), 3),
            "model": model,
            "purpose": purpose,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "usd": round(usd, 6),
        }
        with self.path.open("a") as f:
            f.write(json.dumps(row) + "\n")
        return usd
