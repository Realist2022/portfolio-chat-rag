"""Embedding providers, and the cache that means each text is paid for once.

Ported from ingestion-emdedding-model. Documents and queries must go through the
same model: vectors from two models live in unrelated spaces and mixing them
returns confident nonsense, not an error. So every embedder names its model and
dimensions, the build manifest records them, and the cache keys on them.

HashEmbedder is a deterministic, offline stand-in (hashed bag of words). Tests
and CI use it so they need no key; its scores say nothing about real quality.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path
from typing import Protocol

import numpy as np

from chat_pipeline.keywords import term_id, tokens

OPENAI_MODEL = "text-embedding-3-small"
OPENAI_DIMENSIONS = 1536
LOOKUP_BATCH = 500  # SQLite caps the number of ? in one statement


class Embedder(Protocol):
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class MissingKey(RuntimeError):
    """No OPENAI_API_KEY: an error, not an exit, so a server can report it and carry on."""


class OpenAIEmbedder:
    def __init__(self, model: str = OPENAI_MODEL, dimensions: int = OPENAI_DIMENSIONS):
        key = (os.environ.get("OPENAI_API_KEY") or "").strip()
        if not key:
            raise MissingKey(
                "No OPENAI_API_KEY found. Put it in .env at the repo root, or pass "
                "--embedder hash for an offline run (meaningless scores)."
            )
        from openai import OpenAI

        self.client = OpenAI(api_key=key)
        self.model = model
        self.dimensions = dimensions

    def embed(self, texts: list[str], batch_size: int = 100) -> list[list[float]]:
        vectors: list[list[float]] = []
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            response = self.client.embeddings.create(model=self.model, input=batch)
            # The API may return results out of order; index is authoritative.
            vectors += [d.embedding for d in sorted(response.data, key=lambda d: d.index)]
        return vectors

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class HashEmbedder:
    """Hashed bag of words, L2-normalised. Deterministic, free, offline."""

    def __init__(self, dimensions: int = 256):
        self.model = f"hash-bow-{dimensions}"
        self.dimensions = dimensions
        self.calls: list[list[str]] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        out = []
        for text in texts:
            vector = np.zeros(self.dimensions)
            for term in tokens(text):
                vector[term_id(term) % self.dimensions] += 1.0
            norm = np.linalg.norm(vector)
            out.append((vector / norm if norm else vector).tolist())
        return out

    def embed_query(self, text: str) -> list[float]:
        return self.embed([text])[0]


class CachedEmbedder:
    """Only new or edited text reaches the provider. Deleting the file is always safe."""

    def __init__(self, inner: Embedder, path: Path):
        self.inner = inner
        self.path = path
        self.model = inner.model
        self.dimensions = inner.dimensions

    def key(self, text: str) -> str:
        raw = f"{self.model}\0{self.dimensions}\0{text}".encode()
        return hashlib.sha256(raw).hexdigest()

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path)
        db.execute(
            "CREATE TABLE IF NOT EXISTS vectors (key TEXT PRIMARY KEY, vector BLOB NOT NULL)"
        )
        return db

    def embed(self, texts: list[str]) -> list[list[float]]:
        keys = [self.key(t) for t in texts]
        db = self.connect()
        try:
            found: dict[str, list[float]] = {}
            unique = list(dict.fromkeys(keys))
            for start in range(0, len(unique), LOOKUP_BATCH):
                batch = unique[start : start + LOOKUP_BATCH]
                rows = db.execute(
                    f"SELECT key, vector FROM vectors WHERE key IN ({','.join('?' * len(batch))})",
                    batch,
                )
                found.update({k: np.frombuffer(b, dtype=np.float64).tolist() for k, b in rows})
            missing = {k: t for k, t in zip(keys, texts, strict=True) if k not in found}
            print(f"  embedding cache: {len(unique) - len(missing)} cached, {len(missing)} new")
            if missing:
                fresh = dict(zip(missing, self.inner.embed(list(missing.values())), strict=True))
                with db:
                    db.executemany(
                        "INSERT OR REPLACE INTO vectors (key, vector) VALUES (?, ?)",
                        [(k, np.asarray(v, dtype=np.float64).tobytes()) for k, v in fresh.items()],
                    )
                found.update(fresh)
        finally:
            db.close()
        return [found[k] for k in keys]

    def embed_query(self, text: str) -> list[float]:
        return self.inner.embed_query(text)  # one-off and cheap: not worth caching


class QueryMemo:
    """Remembers query vectors for one process, so an eval sweep embeds each question once."""

    def __init__(self, inner: Embedder):
        self.inner, self.model, self.dimensions = inner, inner.model, inner.dimensions
        self.seen: dict[str, list[float]] = {}

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self.inner.embed(texts)

    def embed_query(self, text: str) -> list[float]:
        if text not in self.seen:
            self.seen[text] = self.inner.embed_query(text)
        return self.seen[text]


def make_embedder(name: str, cache: Path | None) -> Embedder:
    inner: Embedder = OpenAIEmbedder() if name == "openai" else HashEmbedder()
    return CachedEmbedder(inner, cache) if cache else inner
