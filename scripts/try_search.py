"""Try the local retriever: uv run scripts/try_search.py "how do I add a dependency" --lang en"""

import argparse
import time

from voice_rag_agent.retrieval.local import LocalHybridRetriever


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("query")
    ap.add_argument("--lang", choices=["en", "es"])
    ap.add_argument("-k", type=int, default=5)
    ap.add_argument("--index", default="data/index")
    args = ap.parse_args()

    t = time.perf_counter()
    retriever = LocalHybridRetriever.load(args.index)
    load_s = time.perf_counter() - t
    t = time.perf_counter()
    hits = retriever.search(args.query, lang=args.lang, k=args.k)
    query_ms = (time.perf_counter() - t) * 1000

    for h in hits:
        snippet = h.text.split("\n\n", 1)[-1][:100].replace("\n", " ")
        print(f"{h.section_id}  [{h.lang}]  {h.score:.4f}  {h.heading}  | {snippet}")
    print(f"(load {load_s:.2f}s, first query {query_ms:.0f} ms)")


if __name__ == "__main__":
    main()
