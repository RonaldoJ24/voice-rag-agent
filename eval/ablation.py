"""Retrieval ablation: every retriever scored on the same Claude-written queries.

    uv run python eval/agent_query_eval.py --retriever local   # writes the query cache
    uv run python eval/ablation.py --retrievers local,dense,bm25[,aws,aws-dense]

Differences are paired (same 50 answerable questions, same queries), so the interval on
each gap reflects question sampling only, not query randomness. Costs nothing: Claude is
not called. aws and aws-dense need S3VECTORS_BUCKET and an aws login session.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from metrics import bootstrap_ci, first_hit_rank, paired_bootstrap_diff

from voice_rag_agent.app import build_retriever
from voice_rag_agent.config import ROOT, get_settings


def ranks(retriever, rows: list[dict], decisions: dict[str, dict]) -> list[int | None]:
    out = []
    for row in rows:
        d = decisions[row["id"]]
        if not d["searched"]:
            out.append(None)
            continue
        hits = retriever.search(d["query"], d["query_lang"] or row["lang"], 10)
        out.append(
            first_hit_rank([h.section_id for h in hits], row["gold_section_ids"])
        )
    return out


def scores(rs: list[int | None], k: int) -> list[float]:
    return [1.0 if r and r <= k else 0.0 for r in rs]


def mrr(rs: list[int | None]) -> list[float]:
    return [1.0 / r if r else 0.0 for r in rs]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=get_settings().agent_model)
    parser.add_argument("--retrievers", default="local,dense,bm25")
    args = parser.parse_args()

    gold = [
        json.loads(x) for x in (ROOT / "eval/gold.jsonl").read_text().splitlines() if x
    ]
    rows = [r for r in gold if r["kind"] == "answerable"]
    cache = ROOT / f"eval/results/queries_{args.model}.jsonl"
    decisions = {
        d["id"]: d for d in map(json.loads, cache.read_text().splitlines()) if d
    }

    names = args.retrievers.split(",")
    results = {}
    for name in names:
        retriever = build_retriever(name)
        results[name] = {
            "retriever": retriever.name,
            "ranks": ranks(retriever, rows, decisions),
        }

    base = names[0]
    table = []
    for name in names:
        rs = results[name]["ranks"]
        row = {"retriever": name, "name": results[name]["retriever"], "n": len(rs)}
        for label, values in (
            ("recall@1", scores(rs, 1)),
            ("recall@5", scores(rs, 5)),
            ("mrr@10", mrr(rs)),
        ):
            mean, lo, hi = bootstrap_ci(values)
            row[label] = {"mean": round(mean, 3), "ci95": [round(lo, 3), round(hi, 3)]}
        if name != base:
            diff, lo, hi = paired_bootstrap_diff(
                scores(rs, 5), scores(results[base]["ranks"], 5)
            )
            row[f"recall@5_minus_{base}"] = {
                "diff": round(diff, 3),
                "ci95": [round(lo, 3), round(hi, 3)],
            }
        table.append(row)

    out = ROOT / f"eval/results/ablation_{args.model}.json"
    out.write_text(
        json.dumps(
            {
                "model": args.model,
                "queries": str(cache.relative_to(ROOT)),
                "note": "Same Claude-written queries for every retriever. Answerable gold rows only.",
                "table": table,
                "ranks": {
                    n: dict(
                        zip([r["id"] for r in rows], results[n]["ranks"], strict=True)
                    )
                    for n in names
                },
            },
            indent=2,
        )
    )

    print(
        f"{'retriever':<12} {'recall@1':<20} {'recall@5':<20} {'mrr@10':<20} vs {base}"
    )
    for row in table:
        cells = {
            m: f"{row[m]['mean']:.2f} {row[m]['ci95']}"
            for m in ("recall@1", "recall@5", "mrr@10")
        }
        gap = row.get(f"recall@5_minus_{base}")
        print(
            f"{row['retriever']:<12} {cells['recall@1']:<20} {cells['recall@5']:<20} {cells['mrr@10']:<20} "
            + (f"{gap['diff']:+.2f} {gap['ci95']}" if gap else "-")
        )
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
