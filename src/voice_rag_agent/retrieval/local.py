"""Local hybrid retriever: multilingual dense vectors + BM25, fused with RRF."""

import json
import math
import re
import unicodedata
from collections import defaultdict
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from .base import Hit

ROOT = Path(__file__).resolve().parents[3]
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
RRF_K = 60
POOL = 50  # candidates taken from each ranker before fusion

# Tiny EN/ES stopword list; BM25's IDF handles the rest.
STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "of",
        "to",
        "in",
        "on",
        "at",
        "for",
        "and",
        "or",
        "is",
        "are",
        "was",
        "be",
        "do",
        "does",
        "how",
        "what",
        "why",
        "can",
        "i",
        "my",
        "me",
        "it",
        "its",
        "with",
        "by",
        "as",
        "from",
        "that",
        "this",
        "these",
        "those",
        "you",
        "your",
        "we",
        "que",
        "de",
        "la",
        "el",
        "los",
        "las",
        "un",
        "una",
        "unos",
        "unas",
        "en",
        "y",
        "o",
        "es",
        "son",
        "se",
        "por",
        "para",
        "con",
        "del",
        "al",
        "lo",
        "como",
        "cual",
        "cuales",
        "mi",
        "me",
        "te",
        "tu",
        "su",
        "sus",
        "si",
        "no",
        "ya",
    ]
)
_TOKEN = re.compile(r"[^a-z0-9]+")

Embedder = Callable[[str], np.ndarray]


def tokenize(text: str) -> list[str]:
    """Lowercase, strip accents, split on non-alphanumerics, drop stopwords.

    Identifiers like `OAuth2PasswordBearer` stay whole (as `oauth2passwordbearer`).
    """
    folded = unicodedata.normalize("NFKD", text.lower())
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return [t for t in _TOKEN.split(folded) if t and t not in STOPWORDS]


class BM25:
    """Okapi BM25 over pre-tokenized documents (k1=1.5, b=0.75)."""

    def __init__(
        self,
        postings: dict[str, list[list[int]]],
        doc_len: Sequence[int],
        k1: float = 1.5,
        b: float = 0.75,
    ):
        self.k1, self.b = k1, b
        self.doc_len = np.asarray(doc_len, dtype=np.float32)
        self.n = len(self.doc_len)
        self.avgdl = float(self.doc_len.mean()) if self.n else 0.0
        self.postings = {
            t: (
                np.array([d for d, _ in p]),
                np.array([f for _, f in p], dtype=np.float32),
            )
            for t, p in postings.items()
        }
        self._raw = postings

    @classmethod
    def build(cls, docs: Sequence[Sequence[str]]) -> "BM25":
        postings: dict[str, list[list[int]]] = defaultdict(list)
        for i, toks in enumerate(docs):
            counts: dict[str, int] = defaultdict(int)
            for t in toks:
                counts[t] += 1
            for t, f in counts.items():
                postings[t].append([i, f])
        return cls(dict(postings), [len(d) for d in docs])

    def scores(self, query_tokens: Sequence[str]) -> np.ndarray:
        """BM25 score of every document for the query."""
        out = np.zeros(self.n, dtype=np.float32)
        for t in set(query_tokens):
            if t not in self.postings:
                continue
            ids, tf = self.postings[t]
            idf = math.log(1 + (self.n - len(ids) + 0.5) / (len(ids) + 0.5))
            norm = self.k1 * (1 - self.b + self.b * self.doc_len[ids] / self.avgdl)
            out[ids] += idf * tf * (self.k1 + 1) / (tf + norm)
        return out

    def to_json(self) -> dict:
        return {
            "k1": self.k1,
            "b": self.b,
            "doc_len": self.doc_len.astype(int).tolist(),
            "postings": self._raw,
        }

    @classmethod
    def from_json(cls, data: dict) -> "BM25":
        return cls(data["postings"], data["doc_len"], data["k1"], data["b"])


def make_embedder(
    cache_dir: Path, model: str = EMBED_MODEL
) -> tuple[Callable[[Sequence[str]], np.ndarray], Embedder]:
    """Load the fastembed model; return (embed many, embed one query), both normalized."""
    from fastembed import TextEmbedding

    te = TextEmbedding(model, cache_dir=str(cache_dir))

    def embed_many(texts: Sequence[str]) -> np.ndarray:
        vecs = np.array(list(te.embed(list(texts), batch_size=32)), dtype=np.float32)
        return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

    def embed_query(text: str) -> np.ndarray:
        return embed_many([text])[0]

    return embed_many, embed_query


def rrf(rankings: Sequence[Sequence[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal rank fusion of several best-first lists of doc indices."""
    fused: dict[int, float] = defaultdict(float)
    for ranking in rankings:
        for rank, idx in enumerate(ranking, start=1):
            fused[idx] += 1.0 / (k + rank)
    return dict(fused)


class LocalHybridRetriever:
    """Dense + BM25 search over the chunk index, one hit per section."""

    name = "local-hybrid"

    def __init__(
        self,
        chunks: list[dict],
        doc_vectors: np.ndarray,
        bm25: BM25,
        embed_query: Embedder,
    ):
        self.chunks = chunks
        self.doc_vectors = doc_vectors
        self.bm25 = bm25
        self.embed_query = embed_query
        self.by_section: dict[str, list[int]] = defaultdict(list)
        for i, c in enumerate(chunks):
            self.by_section[c["section_id"]].append(i)

    @classmethod
    def load(cls, index_dir: str | Path = "data/index") -> "LocalHybridRetriever":
        """Load an index written by scripts/build_index.py."""
        d = Path(index_dir)
        if not d.is_absolute():
            d = ROOT / d
        meta = json.loads((d / "meta.json").read_text())
        chunks = [
            json.loads(line)
            for line in (d / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
        ]
        vectors = np.load(d / "embeddings.npy")
        bm25 = BM25.from_json(json.loads((d / "bm25.json").read_text()))
        _, embed_query = make_embedder(d.parent / "cache", meta["model"])
        return cls(chunks, vectors, bm25, embed_query)

    def _candidates(self, query: str) -> tuple[dict[int, float], np.ndarray]:
        """Fused scores for the top candidates, plus the full dense score vector."""
        dense = self.doc_vectors @ self.embed_query(query)
        sparse = self.bm25.scores(tokenize(query))
        rankings = [np.argsort(-dense)[:POOL].tolist()]
        hits = np.argsort(-sparse)[:POOL]
        rankings.append([int(i) for i in hits if sparse[i] > 0])
        return rrf(rankings), dense

    def search(self, query: str, lang: str | None = None, k: int = 5) -> list[Hit]:
        """Top k sections, best first; `lang` picks which language's chunk to show."""
        fused, dense = self._candidates(query)
        ranked = sorted(fused, key=lambda i: -fused[i])

        sections: dict[
            str, list[int]
        ] = {}  # section_id -> candidate chunk indices, best first
        for i in ranked:
            sections.setdefault(self.chunks[i]["section_id"], []).append(i)

        hits = []
        for sid, idxs in sections.items():
            score = fused[idxs[0]]  # the section's best chunk score
            chosen = next((i for i in idxs if self.chunks[i]["lang"] == lang), idxs[0])
            if lang and self.chunks[chosen]["lang"] != lang:
                # No chunk in the wanted language among the candidates: take the
                # one in that language closest to the query, if the section has any.
                same_lang = [
                    i for i in self.by_section[sid] if self.chunks[i]["lang"] == lang
                ]
                if same_lang:
                    chosen = max(same_lang, key=lambda i: dense[i])
            hits.append((score, chosen))
        hits.sort(key=lambda h: -h[0])
        return [self._hit(i, s) for s, i in hits[:k]]

    def _hit(self, idx: int, score: float) -> Hit:
        c = self.chunks[idx]
        return Hit(
            section_id=c["section_id"],
            page=c["page"],
            lang=c["lang"],
            title=c["title"],
            heading=c["heading"],
            url=c["url"],
            text=c["text"],
            score=float(score),
        )


def load_text_index(index_dir: str | Path) -> tuple[list[dict], BM25]:
    """Chunks and BM25 only, for retrievers that do not keep dense vectors locally."""
    d = Path(index_dir)
    d = d if d.is_absolute() else ROOT / d
    chunks = [
        json.loads(line)
        for line in (d / "chunks.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return chunks, BM25.from_json(json.loads((d / "bm25.json").read_text()))


class Bm25Retriever(LocalHybridRetriever):
    """Keyword search only. Fallback for Lambda when Bedrock embeddings are unavailable."""

    name = "bm25"

    def __init__(self, chunks: list[dict], bm25: BM25):
        super().__init__(chunks, np.zeros((len(chunks), 1), np.float32), bm25, None)

    @classmethod
    def load(cls, index_dir: str | Path = "data/index") -> "Bm25Retriever":
        return cls(*load_text_index(index_dir))

    def _candidates(self, query: str) -> tuple[dict[int, float], np.ndarray]:
        sparse = self.bm25.scores(tokenize(query))
        ranking = [int(i) for i in np.argsort(-sparse)[:POOL] if sparse[i] > 0]
        # BM25 scores stand in for dense ones when picking a same-language chunk.
        return rrf([ranking]), sparse


class DenseRetriever(LocalHybridRetriever):
    """Embeddings only, no BM25. Exists for the retrieval ablation."""

    name = "dense-minilm"

    def _candidates(self, query: str) -> tuple[dict[int, float], np.ndarray]:
        dense = self.doc_vectors @ self.embed_query(query)
        return rrf([np.argsort(-dense)[:POOL].tolist()]), dense
