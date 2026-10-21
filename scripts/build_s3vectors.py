"""Embed every docs chunk with Titan V2 and upload it to an S3 Vectors index.

    uv run scripts/build_s3vectors.py --bucket fastapi-docs-vectors-XXXX [--index docs-titan-v2-256]

About 1,600 chunks x ~180 tokens = ~0.3M tokens, roughly $0.006 of Titan usage (Free plan credits).
"""

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

import boto3

from voice_rag_agent.config import ROOT
from voice_rag_agent.retrieval.aws import DIMENSIONS, TitanEmbedder


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bucket", required=True)
    parser.add_argument("--index", default=f"docs-titan-v2-{DIMENSIONS}")
    parser.add_argument("--region", default="us-east-2")
    args = parser.parse_args()

    chunks = [
        json.loads(line)
        for line in (ROOT / "data/index/chunks.jsonl").read_text().splitlines()
    ]
    embed = TitanEmbedder(args.region)
    s3v = boto3.client("s3vectors", region_name=args.region)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=8) as pool:
        vectors = list(pool.map(lambda c: embed(c["text"]), chunks))
    print(f"Embedded {len(vectors)} chunks in {time.perf_counter() - started:.1f}s")

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
