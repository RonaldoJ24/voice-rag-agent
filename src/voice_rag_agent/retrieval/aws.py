"""AWS retriever: Titan Text Embeddings V2 on Bedrock + S3 Vectors, fused with the same BM25.

Dense search runs on AWS (no model in the Lambda bundle). BM25 stays local because it
is a few MB of plain Python data. Vector keys are chunk_ids, so results join back to
the text in data/index/chunks.jsonl.
"""

import json
from pathlib import Path

import boto3
import numpy as np

from .local import BM25, POOL, LocalHybridRetriever, load_text_index, rrf, tokenize

TITAN_MODEL = "amazon.titan-embed-text-v2:0"
DIMENSIONS = 256


class TitanEmbedder:
    def __init__(self, region: str, dimensions: int = DIMENSIONS):
        self.client = boto3.client("bedrock-runtime", region_name=region)
        self.dimensions = dimensions

    def __call__(self, text: str) -> np.ndarray:
        body = {
            "inputText": text[:8000],
            "dimensions": self.dimensions,
            "normalize": True,
        }
        response = self.client.invoke_model(modelId=TITAN_MODEL, body=json.dumps(body))
        return np.array(
            json.loads(response["body"].read())["embedding"], dtype=np.float32
        )


class AwsHybridRetriever(LocalHybridRetriever):
    name = "aws-titan-s3vectors"
    use_bm25 = True

    def __init__(
        self, chunks: list[dict], bm25: BM25, bucket: str, index: str, region: str
    ):
        self.embedder = TitanEmbedder(region)
        super().__init__(
            chunks, np.zeros((len(chunks), 1), np.float32), bm25, self.embedder
        )
        self.s3v = boto3.client("s3vectors", region_name=region)
        self.bucket, self.index = bucket, index
        self.row = {c["chunk_id"]: i for i, c in enumerate(chunks)}

    @classmethod
    def load(
        cls, index_dir: str | Path, bucket: str, index: str, region: str
    ) -> "AwsHybridRetriever":
        chunks, bm25 = load_text_index(index_dir)
        return cls(chunks, bm25, bucket, index, region)

    def _candidates(self, query: str) -> tuple[dict[int, float], np.ndarray]:
        response = self.s3v.query_vectors(
            vectorBucketName=self.bucket,
            indexName=self.index,
            queryVector={"float32": self.embedder(query).tolist()},
            topK=POOL,
            returnDistance=True,
        )
        dense = np.full(len(self.chunks), -1.0, dtype=np.float32)
        dense_rank = []
        for v in response["vectors"]:
            i = self.row.get(v["key"])
            if i is not None:
                dense_rank.append(i)
                dense[i] = 1.0 - float(v["distance"])  # cosine distance -> similarity
        if not self.use_bm25:
            return rrf([dense_rank]), dense
        sparse = self.bm25.scores(tokenize(query))
        sparse_rank = [int(i) for i in np.argsort(-sparse)[:POOL] if sparse[i] > 0]
        return rrf([dense_rank, sparse_rank]), dense


class AwsDenseRetriever(AwsHybridRetriever):
    """Titan + S3 Vectors only, no BM25. Exists for the retrieval ablation."""

    name = "aws-titan-dense"
    use_bm25 = False
