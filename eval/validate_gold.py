"""Check eval/gold.jsonl against data/chunks.jsonl: uv run python eval/validate_gold.py"""

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = {"answerable", "unanswerable", "smalltalk"}
FIELDS = {
    "id", "lang", "kind", "question", "style", "gold_section_ids",
    "reference_answer", "pair_id", "source_note",
}  # fmt: skip
EXPECTED = {
    ("answerable", "en"): 25, ("answerable", "es"): 25,
    ("unanswerable", "en"): 5, ("unanswerable", "es"): 5,
    ("smalltalk", "en"): 4, ("smalltalk", "es"): 4,
}  # fmt: skip


def main() -> int:
    sids: dict[str, set[str]] = {"en": set(), "es": set()}
    for line in (
        (ROOT / "data" / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ):
        c = json.loads(line)
        sids[c["lang"]].add(c["section_id"])
    rows = [
        json.loads(line)
        for line in (ROOT / "eval" / "gold.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]

    errors: list[str] = []
    ids = Counter(r["id"] for r in rows)
    errors += [f"duplicate id {i}" for i, n in ids.items() if n > 1]
    for r in rows:
        rid = r["id"]
        if set(r) != FIELDS:
            errors.append(f"{rid}: fields {sorted(set(r) ^ FIELDS)} differ from schema")
        if r["kind"] not in KINDS or r["lang"] not in ("en", "es"):
            errors.append(f"{rid}: bad kind/lang")
        if r["style"] not in ("spoken", "written"):
            errors.append(f"{rid}: bad style")
        if not r["question"].strip() or not r["source_note"].strip():
            errors.append(f"{rid}: empty question or source_note")
        gold = r["gold_section_ids"]
        if r["kind"] == "answerable":
            if not gold or len(gold) > 5:
                errors.append(f"{rid}: answerable needs 1-5 gold ids, has {len(gold)}")
            if not r["reference_answer"].strip():
                errors.append(f"{rid}: missing reference_answer")
            for g in gold:
                for lang in ("en", "es"):
                    if g not in sids[lang]:
                        errors.append(f"{rid}: gold {g} missing in {lang} chunks")
        else:
            if gold:
                errors.append(f"{rid}: {r['kind']} must have empty gold")
            if r["kind"] == "smalltalk" and r["reference_answer"]:
                errors.append(f"{rid}: smalltalk must have empty reference_answer")
    counts = Counter((r["kind"], r["lang"]) for r in rows)
    if counts != Counter(EXPECTED):
        errors.append(f"counts {dict(counts)} != expected {EXPECTED}")
    if len(rows) != 68:
        errors.append(f"expected 68 rows, got {len(rows)}")

    # pairs: exactly two rows, one per language, same gold
    pairs: dict[str, list[dict]] = {}
    for r in rows:
        if r["pair_id"]:
            pairs.setdefault(r["pair_id"], []).append(r)
    if len(pairs) != 6:
        errors.append(f"expected 6 pairs, got {len(pairs)}")
    for pid, members in pairs.items():
        if sorted(m["lang"] for m in members) != ["en", "es"]:
            errors.append(f"{pid}: needs one en and one es row")
        elif members[0]["gold_section_ids"] != members[1]["gold_section_ids"]:
            errors.append(f"{pid}: gold differs between languages")

    answerable = [r for r in rows if r["kind"] == "answerable"]
    pages = Counter(
        g.split("#")[0] for r in answerable for g in r["gold_section_ids"][:1]
    )
    all_pages = Counter(
        p for r in answerable for p in {g.split("#")[0] for g in r["gold_section_ids"]}
    )
    for page, n in all_pages.items():
        if n > 3:
            errors.append(f"page {page} used by {n} questions (max 3)")

    print("rows:", len(rows))
    for key in sorted(counts):
        print(f"  {key[0]:<13}{key[1]}: {counts[key]}")
    print("spoken share:", {
        lang: f"{sum(r['style'] == 'spoken' for r in answerable if r['lang'] == lang)}/25"
        for lang in ("en", "es")
    })  # fmt: skip
    area = Counter(
        (p.split("/")[0] if "/" in p else "top-level") for p in pages.elements()
    )
    print("page areas (primary gold page per answerable question):", dict(area))
    print(
        f"distinct gold pages: {len(all_pages)}; max questions per page: {max(all_pages.values())}"
    )
    print("pairs:", {pid: [m["id"] for m in ms] for pid, ms in sorted(pairs.items())})
    if errors:
        print(f"\n{len(errors)} problem(s):")
        for e in errors:
            print(" -", e)
        return 1
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
