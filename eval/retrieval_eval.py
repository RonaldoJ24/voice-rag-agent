"""Retrieval eval of the local hybrid retriever on eval/gold.jsonl.

uv run python eval/retrieval_eval.py

Queries are the RAW question text. In production Claude rewrites the query
before searching, so these numbers are a conservative baseline, not the
end-to-end retrieval quality.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from metrics import bootstrap_ci, first_hit_rank, mrr_at_k, recall_at_k

from voice_rag_agent.retrieval.local import LocalHybridRetriever

K = 10
OUT = ROOT / "eval" / "results" / "retrieval_local_rawquery.json"
HEADER = (
    "RAW-QUESTION retrieval baseline (local hybrid, k=10). In production Claude rewrites the "
    "query before searching, so treat these numbers as conservative."
)


def load_gold() -> list[dict]:
    path = ROOT / "eval" / "gold.jsonl"
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def run_setting(retriever, rows: list[dict], cross_lingual: bool) -> list[dict]:
    results = []
    for row in rows:
        lang = None if cross_lingual else row["lang"]
        hits = retriever.search(row["question"], lang=lang, k=K)
        ranked = [h.section_id for h in hits]
        gold = row["gold_section_ids"]
        results.append(
            {
                "id": row["id"],
                "lang": row["lang"],
                "style": row["style"],
                "pair_id": row["pair_id"],
                "question": row["question"],
                "gold": gold,
                "rank": first_hit_rank(ranked, gold, K),
                "recall@1": recall_at_k(ranked, gold, 1),
                "recall@5": recall_at_k(ranked, gold, 5),
                "mrr@10": mrr_at_k(ranked, gold, K),
                "top5": [(h.section_id, h.lang, round(h.score, 4)) for h in hits[:5]],
            }
        )
    return results


def summarize(results: list[dict]) -> dict:
    out = {"n": len(results)}
    for metric in ("recall@1", "recall@5", "mrr@10"):
        mean, lo, hi = bootstrap_ci([r[metric] for r in results])
        out[metric] = {"mean": round(mean, 4), "lo": round(lo, 4), "hi": round(hi, 4)}
    return out


def slices(results: list[dict]) -> dict:
    groups = {
        "overall": results,
        "en": [r for r in results if r["lang"] == "en"],
        "es": [r for r in results if r["lang"] == "es"],
        "spoken": [r for r in results if r["style"] == "spoken"],
        "written": [r for r in results if r["style"] == "written"],
    }
    return {name: summarize(rs) for name, rs in groups.items()}


def pair_report(results: list[dict]) -> dict:
    by_pair: dict[str, list[dict]] = {}
    for r in results:
        if r["pair_id"]:
            by_pair.setdefault(r["pair_id"], []).append(r)
    rows = {}
    for pid, members in sorted(by_pair.items()):
        m = {x["lang"]: x for x in members}
        rows[pid] = {
            "en_id": m["en"]["id"],
            "es_id": m["es"]["id"],
            "en_rank": m["en"]["rank"],
            "es_rank": m["es"]["rank"],
            "both_hit@5": bool(m["en"]["recall@5"] and m["es"]["recall@5"]),
            "both_hit@1": bool(m["en"]["recall@1"] and m["es"]["recall@1"]),
        }
    return {
        "pairs": rows,
        "both_hit@5": sum(p["both_hit@5"] for p in rows.values()),
        "both_hit@1": sum(p["both_hit@1"] for p in rows.values()),
        "n_pairs": len(rows),
    }


def unanswerable_scores(retriever, rows: list[dict], answerable: list[dict]) -> dict:
    """Top-1 fused score for unanswerable vs answerable questions (for threshold ideas)."""

    def top1(rs):
        return [
            retriever.search(r["question"], lang=r["lang"], k=1)[0].score for r in rs
        ]

    un = [r for r in rows if r["kind"] == "unanswerable"]
    a, u = top1(answerable), top1(un)
    return {
        "answerable_top1_mean": round(sum(a) / len(a), 5),
        "answerable_top1_min": round(min(a), 5),
        "unanswerable_top1_mean": round(sum(u) / len(u), 5),
        "unanswerable_top1_max": round(max(u), 5),
    }


def fmt(s: dict, metric: str) -> str:
    v = s[metric]
    return f"{v['mean']:.2f} [{v['lo']:.2f},{v['hi']:.2f}]"


def print_table(name: str, sl: dict) -> None:
    print(f"\n{name}")
    print(f"  {'slice':<9}{'n':>3}  {'recall@1':<17}{'recall@5':<17}{'MRR@10':<17}")
    for key, s in sl.items():
        print(
            f"  {key:<9}{s['n']:>3}  {fmt(s, 'recall@1'):<17}"
            f"{fmt(s, 'recall@5'):<17}{fmt(s, 'mrr@10'):<17}"
        )


def main() -> None:
    rows = load_gold()
    answerable = [r for r in rows if r["kind"] == "answerable"]
    retriever = LocalHybridRetriever.load(str(ROOT / "data" / "index"))

    same = run_setting(retriever, answerable, cross_lingual=False)
    cross = run_setting(retriever, answerable, cross_lingual=True)
    report = {
        "header": HEADER,
        "k": K,
        "same_language": {
            "slices": slices(same),
            "pairs": pair_report(same),
            "per_question": same,
        },
        "cross_lingual": {
            "slices": slices(cross),
            "pairs": pair_report(cross),
            "per_question": cross,
        },
        "unanswerable_vs_answerable_top1": unanswerable_scores(
            retriever, rows, answerable
        ),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print(HEADER)
    print_table(
        "same-language (lang = question language)", report["same_language"]["slices"]
    )
    print_table("cross-lingual (lang=None)", report["cross_lingual"]["slices"])
    for name in ("same_language", "cross_lingual"):
        p = report[name]["pairs"]
        print(
            f"\n{name} pairs: both hit@5 {p['both_hit@5']}/{p['n_pairs']}, "
            f"both hit@1 {p['both_hit@1']}/{p['n_pairs']}"
        )
        for pid, v in p["pairs"].items():
            print(f"  {pid}: en rank {v['en_rank']}, es rank {v['es_rank']}")
    off_lang = {
        lang: sum(r["top5"][0][1] != lang for r in cross if r["lang"] == lang)
        for lang in ("en", "es")
    }
    print(
        "\ncross-lingual top-1 hit in the other language's chunk (of 25 each):",
        off_lang,
    )
    report["cross_lingual"]["top1_other_language_chunk"] = off_lang
    OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        "\ntop-1 score, answerable vs unanswerable:",
        report["unanswerable_vs_answerable_top1"],
    )

    n_miss = sum(r["rank"] is None for r in same)
    print(f"\nsame-language misses outside top {K}: {n_miss}/{len(same)}")
    print(
        "cross-lingual section order identical to same-language:",
        all(
            [t[0] for t in a["top5"]] == [t[0] for t in b["top5"]]
            for a, b in zip(same, cross)
        ),
        "(lang only breaks ties between the EN and ES chunk of one section)",
    )
    print("\nworst 5 misses (same-language):")
    worst = sorted(
        same, key=lambda r: (r["rank"] is not None, r["rank"] or 0, r["id"])
    )[:5]
    for r in worst:
        print(f"- {r['id']} rank={r['rank']}: {r['question']}")
        print(f"    gold: {r['gold']}")
        print(f"    got : {[t[0] for t in r['top5'][:3]]}")
    print(f"\nwrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
