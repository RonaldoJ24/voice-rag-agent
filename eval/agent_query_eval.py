"""Retrieval as it runs in production: Claude writes the search query, then the retriever runs it.

For each gold row this makes Claude's first-round call only (the one that decides whether
to search and with what query), then searches with that query. It also scores the
decision: doc questions should search, small talk should not.

    uv run python eval/agent_query_eval.py [--model claude-haiku-5-5] [--retriever local]
        [--reuse-queries]

Claude's queries are saved to eval/results/queries_<model>.jsonl, so other retrievers can
be scored on exactly the same queries (see eval/ablation.py).

Cost on Haiku 5.5: about $0.01 for the 68 rows.
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from metrics import bootstrap_ci, first_hit_rank

from voice_rag_agent.agent import model_params
from voice_rag_agent.app import build_retriever
from voice_rag_agent.config import ROOT, get_settings
from voice_rag_agent.costs import Ledger
from voice_rag_agent.prompts import RECORD_SOURCES_TOOL, SEARCH_DOCS_TOOL, SYSTEM_PROMPT

GREETING = "Hi! Ask me anything about FastAPI, in English or Spanish."


async def first_round(
    client, ledger, model: str, row: dict, sem: asyncio.Semaphore
) -> dict:
    async with sem:
        ledger.check()
        msg = await client.messages.create(
            model=model,
            max_tokens=512,
            system=SYSTEM_PROMPT,
            tools=[SEARCH_DOCS_TOOL, RECORD_SOURCES_TOOL],
            messages=[
                {"role": "user", "content": "(call started)"},
                {"role": "assistant", "content": GREETING},
                {"role": "user", "content": row["question"]},
            ],
            **model_params(model, get_settings().agent_effort),
        )
    ledger.record(model, msg.usage, purpose="eval_query_rewrite")
    search = next(
        (
            b.input
            for b in msg.content
            if b.type == "tool_use" and b.name == "search_docs"
        ),
        None,
    )
    said = "".join(b.text for b in msg.content if b.type == "text").strip()
    return {
        "id": row["id"],
        "searched": search is not None,
        "query": (search or {}).get("query"),
        "query_lang": (search or {}).get("language"),
        "said": said,
    }


def summarize(name: str, values: list[float]) -> dict:
    mean, lo, hi = bootstrap_ci(values)
    return {
        "metric": name,
        "n": len(values),
        "mean": round(mean, 3),
        "ci95": [round(lo, 3), round(hi, 3)],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=get_settings().agent_model)
    parser.add_argument("--retriever", default="local")
    parser.add_argument(
        "--reuse-queries",
        action="store_true",
        help="Score the queries Claude wrote last time instead of asking again",
    )
    args = parser.parse_args()

    s = get_settings()
    rows = [
        json.loads(line)
        for line in (ROOT / "eval/gold.jsonl").read_text().splitlines()
        if line.strip()
    ]
    ledger = Ledger(s.spend_ledger, s.spend_pause_usd)
    cache = ROOT / f"eval/results/queries_{args.model}.jsonl"
    if args.reuse_queries and cache.exists():
        decisions = [json.loads(x) for x in cache.read_text().splitlines() if x]
        print(f"Reusing {len(decisions)} cached queries from {cache.relative_to(ROOT)}")
    else:
        client = anthropic.AsyncAnthropic(api_key=s.anthropic_api_key or None)
        sem = asyncio.Semaphore(8)
        decisions = await asyncio.gather(
            *(first_round(client, ledger, args.model, r, sem) for r in rows)
        )
        cache.write_text(
            "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in decisions)
        )
    retriever = build_retriever(args.retriever)

    per_row = []
    for row, d in zip(rows, decisions, strict=True):
        rank = None
        if row["kind"] == "answerable" and d["searched"]:
            hits = retriever.search(d["query"], d["query_lang"] or row["lang"], 10)
            rank = first_hit_rank([h.section_id for h in hits], row["gold_section_ids"])
        per_row.append(
            {
                **d,
                "kind": row["kind"],
                "lang": row["lang"],
                "style": row["style"],
                "rank": rank,
            }
        )

    answerable = [r for r in per_row if r["kind"] == "answerable"]
    report = {
        "model": args.model,
        "retriever": retriever.name,
        "note": "Claude writes the search query (production path). A row that did not search counts as a miss.",
        "decision": [
            summarize(
                "searched_when_doc_question",
                [
                    1.0 if r["searched"] else 0.0
                    for r in per_row
                    if r["kind"] != "smalltalk"
                ],
            ),
            summarize(
                "skipped_search_on_smalltalk",
                [
                    0.0 if r["searched"] else 1.0
                    for r in per_row
                    if r["kind"] == "smalltalk"
                ],
            ),
            summarize(
                "spoke_filler_before_search",
                [1.0 if r["said"] else 0.0 for r in per_row if r["searched"]],
            ),
        ],
        "retrieval": [],
    }
    slices = {"overall": answerable}
    for key in ("lang", "style"):
        for value in sorted({r[key] for r in answerable}):
            slices[f"{key}={value}"] = [r for r in answerable if r[key] == value]
    for label, group in slices.items():
        for k in (1, 5):
            report["retrieval"].append(
                {
                    "slice": label,
                    **summarize(
                        f"recall@{k}",
                        [1.0 if r["rank"] and r["rank"] <= k else 0.0 for r in group],
                    ),
                }
            )
        report["retrieval"].append(
            {
                "slice": label,
                **summarize(
                    "mrr@10", [1.0 / r["rank"] if r["rank"] else 0.0 for r in group]
                ),
            }
        )

    out = ROOT / f"eval/results/retrieval_{args.retriever}_agentquery_{args.model}.json"
    out.write_text(
        json.dumps({"summary": report, "rows": per_row}, indent=2, ensure_ascii=False)
    )
    for d in report["decision"]:
        print(f"{d['metric']:<30} {d['mean']:.2f} {d['ci95']} n={d['n']}")
    for r in report["retrieval"]:
        print(
            f"{r['slice']:<14} {r['metric']:<9} {r['mean']:.2f} {r['ci95']} n={r['n']}"
        )
    misses = [r for r in answerable if not r["rank"] or r["rank"] > 5]
    print(f"\nMisses outside top 5 ({len(misses)}):")
    for r in misses:
        print(f"  {r['id']}: query={r['query']!r} rank={r['rank']}")
    print(f"\nTotal spend so far: ${ledger.total():.4f}  ->  {out.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
