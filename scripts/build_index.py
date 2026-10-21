"""Build data/index/ (embeddings, BM25 stats, chunk metadata) from data/chunks.jsonl."""

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np

from voice_rag_agent.retrieval.local import BM25, EMBED_MODEL, make_embedder, tokenize

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chunks", type=Path, default=ROOT / "data" / "chunks.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "index")
    ap.add_argument("--model", default=EMBED_MODEL)
    args = ap.parse_args()

    t0 = time.perf_counter()
    chunks = [
        json.loads(line)
        for line in args.chunks.read_text(encoding="utf-8").splitlines()
    ]
    print(f"read {len(chunks)} chunks")

    t = time.perf_counter()
    bm25 = BM25.build([tokenize(c["text"]) for c in chunks])
    print(f"bm25: {len(bm25.postings)} terms in {time.perf_counter() - t:.2f}s")

    t = time.perf_counter()
    embed_many, _ = make_embedder(args.out.parent / "cache", args.model)
    print(f"model ready in {time.perf_counter() - t:.1f}s")
    t = time.perf_counter()
    vectors = embed_many([c["text"] for c in chunks])
    print(f"embedded {vectors.shape} in {time.perf_counter() - t:.1f}s")

    args.out.mkdir(parents=True, exist_ok=True)
    np.save(args.out / "embeddings.npy", vectors.astype(np.float32))
    (args.out / "bm25.json").write_text(json.dumps(bm25.to_json()))
    shutil.copyfile(args.chunks, args.out / "chunks.jsonl")
    (args.out / "meta.json").write_text(
        json.dumps({"model": args.model, "n_chunks": len(chunks)}, indent=2)
    )
    print(f"wrote {args.out} in {time.perf_counter() - t0:.1f}s total")


if __name__ == "__main__":
    main()
