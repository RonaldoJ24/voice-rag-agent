"""Answer eval: full agent turns on the frozen gold set, scored by code checks and a blind judge.

    uv run python eval/answer_eval.py --models claude-haiku-5-5,claude-sonnet-5-5 \
        [--retriever aws-dense] [--limit 6]

For every gold row and model, this runs one real agent turn (same loop the proxy runs,
same tools, the retriever named here), then:

- code checks: searched when it should, skipped search on small talk, cited a gold
  section, abstained on unanswerable rows, replied in the question's language, no URLs
  or code read aloud;
- an Opus 5.5 judge that sees the question, reference answer, retrieved sections and the
  spoken answer, but not which model wrote it, and returns pass or fail with reasons.

Writes eval/results/answers_<model>.jsonl, eval/results/answer_eval_summary.json and a
30-judgment spot-check sheet in eval/review/. Refuses to run if the gold set does not
match its freeze record.
"""

import argparse
import asyncio
import hashlib
import json
import random
import re
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from metrics import bootstrap_ci, paired_bootstrap_diff

from voice_rag_agent.agent import TurnResult, VoiceAgent, format_hits, guess_language
from voice_rag_agent.app import build_retriever
from voice_rag_agent.config import ROOT, get_settings
from voice_rag_agent.costs import Ledger
from voice_rag_agent.openai_compat import ChunkWriter, to_anthropic
from voice_rag_agent.trace import MemoryTraceBus, TurnTrace

GREETING = "Hi! Ask me anything about FastAPI, in English or Spanish."
JUDGE_MODEL = "claude-opus-5-5"

JUDGE_SYSTEM = """\
You grade a voice assistant that must answer FastAPI questions only from retrieved \
FastAPI documentation. You see the question, the kind of question, a reference answer \
written by a human from the docs, the documentation sections the assistant retrieved, \
and what the assistant said out loud. Grade strictly but fairly:

- answerable: "correct" means the spoken answer gets the key point of the reference \
answer right and says nothing wrong about FastAPI. Missing minor details is fine; a \
wrong or misleading statement is not. "grounded" means every factual claim about \
FastAPI is supported by the retrieved sections (ignore filler like "let me check the \
docs"). Pass only if both are true.
- unanswerable: the docs don't cover this. Pass only if the assistant clearly says the \
docs don't cover it (or that it can't find it) and does not present unsupported \
specifics as fact. Set correct and grounded to the same value as pass.
- smalltalk: pass if the reply is short, friendly and appropriate, and makes no \
made-up claims. Set correct and grounded to the same value as pass.

The answer is speech, so judge content, not formatting. Keep each reason to one \
sentence that names the specific problem, or says why it passed."""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "grounded": {"type": "boolean"},
        "pass": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["correct", "grounded", "pass", "reason"],
    "additionalProperties": False,
}


class RecordingRetriever:
    """Wraps a retriever and keeps every hit it returns, so the judge sees what Claude saw."""

    def __init__(self, inner):
        self.inner, self.name, self.hits = inner, inner.name, []

    def search(self, query, lang=None, k=5):
        hits = self.inner.search(query, lang, k)
        self.hits.extend(hits)
        return hits


def load_frozen_gold() -> list[dict]:
    freeze = json.loads((ROOT / "eval/gold.freeze.json").read_text())
    data = (ROOT / freeze["file"]).read_bytes()
    if hashlib.sha256(data).hexdigest() != freeze["sha256"]:
        raise SystemExit("eval/gold.jsonl does not match eval/gold.freeze.json")
    return [json.loads(x) for x in data.decode().splitlines() if x.strip()]


def code_checks(row: dict, result: TurnResult) -> dict:
    searched = bool(result.searches)
    text = result.text
    checks = {
        "language_matches": guess_language(text) == row["lang"],
        "no_urls_or_code": not re.search(
            r"https?://|[{}]|^\s*(def|import|from \S+ import) ", text, re.MULTILINE
        ),
    }
    if row["kind"] == "smalltalk":
        checks["skipped_search"] = not searched
    else:
        checks["searched"] = searched
    if row["kind"] == "answerable":
        checks["cited_gold_section"] = bool(
            set(result.cited) & set(row["gold_section_ids"])
        )
        checks["claimed_docs_answer"] = result.answered_from_docs is True
    if row["kind"] == "unanswerable":
        checks["abstained"] = result.answered_from_docs is False
    return checks


async def run_turn(client, ledger, retriever, model: str, row: dict) -> dict:
    s = get_settings()
    recorder = RecordingRetriever(retriever)
    agent = VoiceAgent(
        client,
        recorder,
        ledger,
        model,
        s.agent_effort,
        s.agent_max_tokens,
        s.max_tool_rounds,
        s.top_k,
    )
    # Same shape ElevenLabs sends: the greeting it already spoke, then the question.
    system, messages = to_anthropic(
        [
            {"role": "assistant", "content": GREETING},
            {"role": "user", "content": row["question"]},
        ]
    )
    bus = MemoryTraceBus()
    result = TurnResult()
    trace = TurnTrace(bus, f"eval-{row['id']}", row["id"])
    async for _ in agent.run(system, messages, [], trace, ChunkWriter(model), result):
        pass
    errors = [e for e in bus.since() if e["type"] == "error"]
    return {
        "id": row["id"],
        "model": model,
        "kind": row["kind"],
        "lang": row["lang"],
        "style": row["style"],
        "question": row["question"],
        "answer": result.text.strip(),
        "cited": result.cited,
        "answered_from_docs": result.answered_from_docs,
        "searches": result.searches,
        "first_token_ms": result.first_token_ms,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "usd": round(result.usd, 6),
        "errors": [e.get("message") for e in errors],
        "checks": code_checks(row, result),
        "_hits": recorder.hits,
    }


async def judge(client, ledger, row: dict, turn: dict) -> dict:
    ledger.check()
    seen = {}
    for h in turn["_hits"]:
        seen.setdefault(h.section_id, h)
    prompt = (
        f"Kind: {row['kind']}\n"
        f"Question ({row['lang']}): {row['question']}\n\n"
        f"Reference answer: {row.get('reference_answer') or '(none)'}\n\n"
        f"Retrieved sections:\n{format_hits(list(seen.values())) if seen else '(the assistant did not search)'}\n\n"
        f"What the assistant said:\n{turn['answer'] or '(nothing)'}"
    )
    msg = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=4000,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": JUDGE_SCHEMA},
        },
    )
    ledger.record(JUDGE_MODEL, msg.usage, purpose="eval_judge")
    text = next(b.text for b in msg.content if b.type == "text")
    return json.loads(text)


def rate(values: list[float]) -> dict:
    mean, lo, hi = bootstrap_ci(values)
    return {
        "n": len(values),
        "mean": round(mean, 3),
        "ci95": [round(lo, 3), round(hi, 3)],
    }


def summarize(turns: list[dict]) -> dict:
    out = {"judge_pass": {}, "checks": {}, "cost": {}}
    slices = {"overall": turns}
    for key in ("kind", "lang"):
        for value in sorted({t[key] for t in turns}):
            slices[f"{key}={value}"] = [t for t in turns if t[key] == value]
    for label, group in slices.items():
        out["judge_pass"][label] = rate(
            [1.0 if t["judge"]["pass"] else 0.0 for t in group]
        )
    answerable = [t for t in turns if t["kind"] == "answerable"]
    out["judge_correct_answerable"] = rate(
        [1.0 if t["judge"]["correct"] else 0.0 for t in answerable]
    )
    out["judge_grounded_answerable"] = rate(
        [1.0 if t["judge"]["grounded"] else 0.0 for t in answerable]
    )
    names = sorted({k for t in turns for k in t["checks"]})
    for name in names:
        vals = [1.0 if t["checks"][name] else 0.0 for t in turns if name in t["checks"]]
        out["checks"][name] = rate(vals)
    ft = sorted(t["first_token_ms"] for t in turns if t["first_token_ms"] is not None)
    out["cost"] = {
        "turns": len(turns),
        "usd_total": round(sum(t["usd"] for t in turns), 4),
        "usd_per_turn": round(sum(t["usd"] for t in turns) / len(turns), 6),
        "first_token_ms_p50": ft[len(ft) // 2] if ft else None,
        "first_token_ms_p90": ft[int(len(ft) * 0.9)] if ft else None,
        "turns_with_errors": sum(1 for t in turns if t["errors"]),
    }
    return out


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", default="claude-haiku-5-5,claude-sonnet-5-5")
    parser.add_argument("--retriever", default="aws-dense")
    parser.add_argument(
        "--limit", type=int, default=0, help="Only the first N rows (pilot)"
    )
    args = parser.parse_args()

    s = get_settings()
    rows = load_frozen_gold()
    if args.limit:
        rng = random.Random(1)
        rows = sorted(rng.sample(rows, args.limit), key=lambda r: r["id"])
    gold = {r["id"]: r for r in rows}
    client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None)
    ledger = Ledger(s.spend_ledger, s.spend_pause_usd)
    retriever = build_retriever(args.retriever)
    start_spend = ledger.total()
    sem = asyncio.Semaphore(4)

    async def one(model: str, row: dict) -> dict:
        async with sem:
            ledger.check()
            turn = await run_turn(client, ledger, retriever, model, row)
            turn["judge"] = await judge(client, ledger, row, turn)
            del turn["_hits"]
            return turn

    models = args.models.split(",")
    by_model = {}
    for model in models:
        turns = await asyncio.gather(*(one(model, r) for r in rows))
        by_model[model] = turns
        suffix = "_pilot" if args.limit else ""
        path = ROOT / f"eval/results/answers_{model}{suffix}.jsonl"
        path.write_text(
            "".join(json.dumps(t, ensure_ascii=False) + "\n" for t in turns)
        )

    summary = {
        "gold": "eval-freeze-v1",
        "retriever": retriever.name,
        "judge": JUDGE_MODEL,
        "rows": len(rows),
        "models": {m: summarize(t) for m, t in by_model.items()},
        "judge_and_eval_usd": round(ledger.total() - start_spend, 4),
    }
    if len(models) == 2:
        a, b = (by_model[m] for m in models)
        pa = [1.0 if t["judge"]["pass"] else 0.0 for t in a]
        pb = [1.0 if t["judge"]["pass"] else 0.0 for t in b]
        diff, lo, hi = paired_bootstrap_diff(pb, pa)
        summary["paired_pass_diff"] = {
            "which": f"{models[1]} minus {models[0]}",
            "diff": round(diff, 3),
            "ci95": [round(lo, 3), round(hi, 3)],
        }

    if not args.limit:
        (ROOT / "eval/results/answer_eval_summary.json").write_text(
            json.dumps(summary, indent=2)
        )
        # Spot-check sheet: 30 judgments across both models for a human to confirm.
        pool = [t for turns in by_model.values() for t in turns]
        sample = random.Random(20261020).sample(pool, min(30, len(pool)))
        lines = [
            "# Judge spot-check v1 (30 random judgments, models hidden)\n",
            "For each row, say whether you agree with the judge's verdict. Disagreements measure judge error.\n",
        ]
        for i, t in enumerate(sorted(sample, key=lambda t: t["id"]), 1):
            g = gold[t["id"]]
            lines += [
                f"## {i}. {t['id']} ({t['kind']}, {t['lang']})\n",
                f"**Question:** {t['question']}\n",
                f"**Reference answer:** {g.get('reference_answer') or '(none)'}\n",
                f"**Spoken answer:** {t['answer']}\n",
                f"**Judge:** {'PASS' if t['judge']['pass'] else 'FAIL'}. {t['judge']['reason']}\n",
                "**Agree?** yes / no: \n",
            ]
        (ROOT / "eval/review/judge_spotcheck_v1.md").write_text("\n".join(lines))

    for model in models:
        m = summary["models"][model]
        print(f"\n== {model}")
        for label, r in m["judge_pass"].items():
            print(f"  judge pass {label:<20} {r['mean']:.2f} {r['ci95']} n={r['n']}")
        print(
            f"  correct (answerable)            {m['judge_correct_answerable']['mean']:.2f} {m['judge_correct_answerable']['ci95']}"
        )
        print(
            f"  grounded (answerable)           {m['judge_grounded_answerable']['mean']:.2f} {m['judge_grounded_answerable']['ci95']}"
        )
        for name, r in m["checks"].items():
            print(f"  check {name:<26} {r['mean']:.2f} n={r['n']}")
        print(f"  cost {m['cost']}")
    if "paired_pass_diff" in summary:
        d = summary["paired_pass_diff"]
        print(f"\n{d['which']}: judge pass {d['diff']:+.2f} {d['ci95']}")
    print(
        f"\nSpend for this run: ${summary['judge_and_eval_usd']:.4f} (ledger total ${ledger.total():.4f})"
    )


if __name__ == "__main__":
    asyncio.run(main())
