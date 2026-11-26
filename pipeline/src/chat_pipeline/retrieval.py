"""Two retrievers behind one interface, so the eval can compare them.

QdrantRetriever is the production path: dense + sparse BM25 in one Qdrant query,
fused with Reciprocal Rank Fusion. Each build is a new collection; the alias
(ALIAS) is switched to it only when asked (and, from phase 4, only after the eval
gate passes), so a bad build never reaches the live chatbot and rollback is one
alias switch.

MemoryRetriever is the Toitū twin's approach, kept as a baseline: a numpy dot
product plus weighted BM25 over the bundle. At ~60 chunks it is as good as any
database; the point of the comparison is to show Qdrant earns its place.

Both apply the same diversity rule: at most per_doc_max chunks from one document.
`chat-pipeline eval --sweep` compares the settings below in one run.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from chat_pipeline.embedders import Embedder
from chat_pipeline.keywords import KeywordIndex, document_sparse, keyword_text, query_sparse, tokens
from chat_pipeline.schema import Chunk

ALIAS = "portfolio-chunks"
COLLECTION_PREFIX = "portfolio-chunks-"
DENSE, SPARSE = "dense", "bm25"
PER_DOC_MAX = 2
FUSION = "rrf"  # Qdrant's fusion: "rrf" (by rank) or "dbsf" (by normalised score)
KEYWORD_WEIGHT = 0.10  # the twin's measured weight; re-tune on this corpus's eval


class ModelMismatch(ValueError):
    """The index was built with another embedding model: its scores would be nonsense."""


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


class Retriever(Protocol):
    name: str
    model: str
    embedder: Embedder

    def search(self, question: str, k: int = 5) -> list[Hit]: ...


def diversify(hits: list[Hit], k: int, per_doc_max: int = PER_DOC_MAX) -> list[Hit]:
    taken: dict[str, int] = {}
    out = []
    for hit in hits:
        if taken.get(hit.chunk.doc_id, 0) >= per_doc_max:
            continue
        taken[hit.chunk.doc_id] = taken.get(hit.chunk.doc_id, 0) + 1
        out.append(hit)
        if len(out) == k:
            break
    return out


class MemoryRetriever:
    def __init__(
        self,
        chunks: list[Chunk],
        vectors: np.ndarray,
        embedder: Embedder,
        model: str,
        per_doc_max: int = PER_DOC_MAX,
    ):
        self.name = "memory" if per_doc_max == PER_DOC_MAX else f"memory cap {per_doc_max}"
        self.per_doc_max = per_doc_max
        if embedder.model != model:
            raise ModelMismatch(
                f"Bundle was built with {model}, but the embedder is {embedder.model}."
            )
        self.chunks, self.vectors, self.embedder, self.model = chunks, vectors, embedder, model
        self.keywords = KeywordIndex(chunks)

    def search(self, question: str, k: int = 5) -> list[Hit]:
        query = np.asarray(self.embedder.embed_query(question), dtype=np.float32)
        query /= np.linalg.norm(query) or 1.0
        scores = self.vectors @ query
        bm25 = self.keywords.scores(question)
        if bm25.max() > 0:
            scores = scores + KEYWORD_WEIGHT * bm25 / bm25.max()
        order = np.argsort(-scores)
        hits = [Hit(self.chunks[i], float(scores[i])) for i in order]
        return diversify(hits, k, self.per_doc_max)


def qdrant_client(local_path: Path):
    """Qdrant Cloud when QDRANT_URL is set, else an embedded store on disk."""
    from qdrant_client import QdrantClient

    url = (os.environ.get("QDRANT_URL") or "").strip()
    if url:
        return QdrantClient(url=url, api_key=os.environ.get("QDRANT_API_KEY") or None)
    local_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(local_path))


def point_id(chunk_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))


def index_chunks(client, collection: str, chunks: list[Chunk], vectors: np.ndarray, meta: dict):
    """A new collection holding this build. Never touches the live alias."""
    from qdrant_client import models as m

    client.create_collection(
        collection,
        vectors_config={DENSE: m.VectorParams(size=vectors.shape[1], distance=m.Distance.COSINE)},
        sparse_vectors_config={SPARSE: m.SparseVectorParams(modifier=m.Modifier.IDF)},
        metadata=meta,
    )
    terms = [tokens(keyword_text(c)) for c in chunks]
    average = sum(map(len, terms)) / max(len(terms), 1)
    points = []
    for chunk, vector, words in zip(chunks, vectors, terms, strict=True):
        ids, weights = document_sparse(words, average)
        points.append(
            m.PointStruct(
                id=point_id(chunk.id),
                vector={
                    DENSE: vector.tolist(),
                    SPARSE: m.SparseVector(indices=ids, values=weights),
                },
                payload=chunk.model_dump(),
            )
        )
    client.upsert(collection, points=points, wait=True)


def promote(client, collection: str, alias: str = ALIAS) -> str | None:
    """Point the alias at this collection in one atomic call. Returns the previous one."""
    from qdrant_client import models as m

    previous = live_collection(client, alias)
    ops = []
    if previous:
        ops.append(m.DeleteAliasOperation(delete_alias=m.DeleteAlias(alias_name=alias)))
    ops.append(
        m.CreateAliasOperation(
            create_alias=m.CreateAlias(collection_name=collection, alias_name=alias)
        )
    )
    client.update_collection_aliases(change_aliases_operations=ops)
    return previous


def prune(client, keep: int = 3) -> list[str]:
    """Delete all but the newest `keep` builds. The live one is never deleted."""
    live = live_collection(client)
    names = sorted(
        c.name for c in client.get_collections().collections if c.name.startswith(COLLECTION_PREFIX)
    )
    old = [n for n in names[:-keep] if n != live] if keep else [n for n in names if n != live]
    for name in old:
        client.delete_collection(name)
    return old


def live_collection(client, alias: str = ALIAS) -> str | None:
    for a in client.get_aliases().aliases:
        if a.alias_name == alias:
            return a.collection_name
    return None


class QdrantRetriever:
    def __init__(
        self,
        client,
        collection: str,
        embedder: Embedder,
        per_doc_max: int = PER_DOC_MAX,
        fusion: str = FUSION,
    ):
        self.client, self.collection, self.embedder = client, collection, embedder
        self.per_doc_max, self.fusion = per_doc_max, fusion
        defaults = (per_doc_max, fusion) == (PER_DOC_MAX, FUSION)
        self.name = "qdrant" if defaults else f"qdrant {fusion} cap {per_doc_max}"
        meta = client.get_collection(collection).config.metadata or {}
        self.model = meta.get("model", "")
        if self.model != embedder.model:
            raise ModelMismatch(
                f"{collection} was built with {self.model or 'an unknown model'}, "
                f"but the embedder is {embedder.model}."
            )

    def search(self, question: str, k: int = 5) -> list[Hit]:
        from qdrant_client import models as m

        dense = self.embedder.embed_query(question)
        ids, weights = query_sparse(question)
        prefetch = [m.Prefetch(query=dense, using=DENSE, limit=k * 4)]
        if ids:
            sparse = m.SparseVector(indices=ids, values=weights)
            prefetch.append(m.Prefetch(query=sparse, using=SPARSE, limit=k * 4))
        result = self.client.query_points(
            self.collection,
            prefetch=prefetch,
            query=m.FusionQuery(fusion=m.Fusion.DBSF if self.fusion == "dbsf" else m.Fusion.RRF),
            limit=k * 4,
            with_payload=True,
        )
        hits = [Hit(Chunk(**p.payload), p.score) for p in result.points]
        return diversify(hits, k, self.per_doc_max)
