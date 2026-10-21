"""Draw the stratified 20-row review sample of the gold set (fixed seed) as Markdown.

uv run python eval/review/sample_gold.py > eval/review/gold_sample_v1.md
"""

import json
import random

from voice_rag_agent.config import ROOT

PLAN = {
    ("answerable", "en"): 7,
    ("answerable", "es"): 7,
    ("unanswerable", "en"): 2,
    ("unanswerable", "es"): 2,
    ("smalltalk", "en"): 1,
    ("smalltalk", "es"): 1,
}


def main() -> None:
    rows = [
        json.loads(x) for x in (ROOT / "eval/gold.jsonl").read_text().splitlines() if x
    ]
    urls = {}
    for line in (ROOT / "data/index/chunks.jsonl").read_text().splitlines():
        c = json.loads(line)
        urls.setdefault((c["section_id"], c["lang"]), c["url"])

    rng = random.Random(20261020)
    picked = []
    for (kind, lang), n in PLAN.items():
        group = [r for r in rows if r["kind"] == kind and r["lang"] == lang]
        picked += sorted(rng.sample(group, n), key=lambda r: r["id"])

    print("# Gold set review sample v1 (20 of 68 rows, seed 20261020)\n")
    print("For each row, check three things and mark it OK or write the fix:")
    print(
        "1. The question sounds like something a real person would ask (spoken rows are casual on purpose)."
    )
    print("2. The gold sections really answer it (open the links).")
    print("3. The reference answer is correct and complete for those sections.\n")
    print(
        "Unanswerable rows should NOT be answerable from the FastAPI docs. Small-talk rows should need no search.\n"
    )
    for r in picked:
        print(f"## {r['id']} ({r['kind']}, {r['lang']}, {r['style']})\n")
        print(f"**Question:** {r['question']}\n")
        if r["gold_section_ids"]:
            links = [
                f"[{s}]({urls.get((s, r['lang'])) or urls.get((s, 'en'), '')})"
                for s in r["gold_section_ids"]
            ]
            print("**Gold sections:** " + ", ".join(links) + "\n")
        if r.get("reference_answer"):
            print(f"**Reference answer:** {r['reference_answer']}\n")
        print("**Verdict:** OK / fix: \n")


if __name__ == "__main__":
    main()
