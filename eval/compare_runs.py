"""Compare two answer-eval conditions, each run twice, question by question.

    uv run python eval/compare_runs.py --a ,base2 --b code,code2

Each name is a results tag: "" is answers_<model>.jsonl, "code" is answers_<model>_code.jsonl.
A question's score in a condition is its mean judge pass over that condition's runs, so
the bootstrap resamples 68 questions, not 136 correlated rows. Flips between two runs of
the same condition show how much a rerun alone moves the result.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from metrics import paired_bootstrap_diff

from voice_rag_agent.config import ROOT

# Rows FAILURES.md (before this change) blamed on code examples missing from the chunks.
PREDICTED = {
    "claude-haiku-5-5": ["en-02", "en-05", "en-14", "en-16"],
    "claude-sonnet-5-5": ["en-02", "en-14"],
}


def load(model: str, tag: str) -> dict[str, dict]:
    suffix = f"_{tag}" if tag else ""
    path = ROOT / f"eval/results/answers_{model}{suffix}.jsonl"
    return {d["id"]: d for d in map(json.loads, path.read_text().splitlines()) if d}


def flips(runs: list[dict[str, dict]]) -> int:
    a, b = runs
    return sum(a[i]["judge"]["pass"] != b[i]["judge"]["pass"] for i in a)


def mean_pass(runs: list[dict[str, dict]], qid: str, key: str = "pass") -> float:
    return sum(float(r[qid]["judge"][key]) for r in runs) / len(runs)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="claude-haiku-5-5,claude-sonnet-5-5")
    ap.add_argument("--a", default=",base2", help="baseline run tags")
    ap.add_argument("--b", default="code,code2", help="variant run tags")
    ap.add_argument("--out", default="eval/results/compare_code_vs_base.json")
    args = ap.parse_args()

    report = {"a": args.a.split(","), "b": args.b.split(","), "models": {}}
    for model in args.models.split(","):
        a = [load(model, t) for t in report["a"]]
        b = [load(model, t) for t in report["b"]]
        ids = sorted(a[0])
        answerable = [i for i in ids if a[0][i]["kind"] == "answerable"]
        m = {
            "pass_a": round(sum(mean_pass(a, i) for i in ids) / len(ids), 3),
            "pass_b": round(sum(mean_pass(b, i) for i in ids) / len(ids), 3),
        }
        for key, rows in (
            ("pass", ids),
            ("correct", answerable),
            ("grounded", answerable),
        ):
            diff, lo, hi = paired_bootstrap_diff(
                [mean_pass(b, i, key) for i in rows],
                [mean_pass(a, i, key) for i in rows],
            )
            m[f"{key}_b_minus_a"] = {
                "diff": round(diff, 3),
                "ci95": [round(lo, 3), round(hi, 3)],
                "n_questions": len(rows),
            }
        m["flips_within_a"] = flips(a)
        m["flips_within_b"] = flips(b)
        m["flips_between"] = [
            sum(ra[i]["judge"]["pass"] != rb[i]["judge"]["pass"] for i in ids)
            for ra, rb in zip(a, b, strict=True)
        ]
        m["predicted_rows"] = {
            i: {
                "a": [r[i]["judge"]["pass"] for r in a],
                "b": [r[i]["judge"]["pass"] for r in b],
            }
            for i in PREDICTED.get(model, [])
        }
        tokens = {
            name: sum(r[i]["input_tokens"] for r in runs for i in ids)
            for name, runs in (("a", a), ("b", b))
        }
        usd = {
            name: sum(r[i]["usd"] for r in runs for i in ids) / (len(runs) * len(ids))
            for name, runs in (("a", a), ("b", b))
        }
        m["input_tokens_b_over_a"] = round(tokens["b"] / tokens["a"], 3)
        m["usd_per_turn"] = {k: round(v, 6) for k, v in usd.items()}
        report["models"][model] = m

    out = ROOT / args.out
    out.write_text(json.dumps(report, indent=2))
    for model, m in report["models"].items():
        print(f"== {model}")
        print(f"  pass  a {m['pass_a']:.3f}  b {m['pass_b']:.3f}")
        for key in ("pass", "correct", "grounded"):
            d = m[f"{key}_b_minus_a"]
            print(f"  {key:9} b-a {d['diff']:+.3f} {d['ci95']} n={d['n_questions']}")
        print(
            f"  flips within a {m['flips_within_a']}, within b {m['flips_within_b']}, "
            f"between {m['flips_between']}"
        )
        for qid, v in m["predicted_rows"].items():
            print(f"  predicted {qid}: a {v['a']} b {v['b']}")
        print(
            f"  input tokens b/a {m['input_tokens_b_over_a']}, usd/turn {m['usd_per_turn']}"
        )
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
