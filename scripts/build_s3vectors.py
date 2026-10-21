"""Embed every docs chunk with Titan V2 and upload it to an S3 Vectors index.

    uv run scripts/build_s3vectors.py --bucket fastapi-docs-vectors-XXXX [--index docs-titan-v2-256]

About 1,600 chunks x ~180 tokens = ~0.3M tokens, roughly $0.006 of Titan usage (Free plan credits).
Resumable: embeddings are cached in data/cache/titan_v2_256.jsonl.
"""

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import boto3
import numpy as np

from voice_rag_agent.config import ROOT
from voice_rag_agent.retrieval.aws import DIMENSIONS, TitanEmbedder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--index", default=f"docs-titan-v2-{DIMENSIONS}")
    parser.add_argument("--region", default="us-east-2")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()

    chunks = [
        json.loads(line)
        for line in (ROOT / "data/index/chunks.jsonl").read_text().splitlines()
    ]
    embed = TitanEmbedder(args.region)
    s3v = boto3.client("s3vectors", region_name=args.region)

    # Progress is saved per chunk, so a throttled or interrupted run resumes where it stopped.
    cache_path = ROOT / "data/cache/titan_v2_256.jsonl"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    done = {}
    if cache_path.exists():
        for line in cache_path.read_text().splitlines():
            row = json.loads(line)
            done[row["chunk_id"]] = row["vector"]
    todo = [c for c in chunks if c["chunk_id"] not in done]
    print(f"{len(done)} chunks already embedded, {len(todo)} to go")

    started = time.perf_counter()
    lock = threading.Lock()
    with cache_path.open("a") as cache, ThreadPoolExecutor(args.workers) as pool:

        def work(chunk: dict) -> None:
            vector = embed(chunk["text"]).tolist()
            with lock:
                done[chunk["chunk_id"]] = vector
                cache.write(
                    json.dumps({"chunk_id": chunk["chunk_id"], "vector": vector}) + "\n"
                )

        list(pool.map(work, todo))
    vectors = [np.array(done[c["chunk_id"]], dtype=np.float32) for c in chunks]
    print(f"Embedded {len(todo)} chunks in {time.perf_counter() - started:.1f}s")

    batch = []
    for chunk, vec in zip(chunks, vectors, strict=True):
        batch.append(
            {
                "key": chunk["chunk_id"],
                "data": {"float32": vec.tolist()},
                "metadata": {"lang": chunk["lang"], "section_id": chunk["section_id"]},
            }
        )
        if len(batch) == 500:
            s3v.put_vectors(
                vectorBucketName=args.bucket, indexName=args.index, vectors=batch
            )
            batch = []
    if batch:
        s3v.put_vectors(
            vectorBucketName=args.bucket, indexName=args.index, vectors=batch
        )
    print(f"Uploaded to s3vectors://{args.bucket}/{args.index}")


if __name__ == "__main__":
    main()
