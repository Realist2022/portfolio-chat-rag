"""A build's output on disk: chunks.json, vectors.npy and manifest.json.

The same shape as the Toitū twin's bundle. Qdrant is the live index; the bundle
is the record of what went into it, and what the in-memory baseline reads.
vectors[i] belongs to chunks[i] and every vector is L2-normalised.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from chat_pipeline.schema import Chunk


def new_build_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%d-%H%M%S")


def normalise(vectors: list[list[float]]) -> np.ndarray:
    array = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    return array / np.where(norms == 0, 1, norms)


def write_bundle(folder: Path, chunks: list[Chunk], vectors: np.ndarray, manifest: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    np.save(folder / "vectors.npy", vectors)
    rows = [c.model_dump() for c in chunks]
    (folder / "chunks.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), "utf-8")
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), "utf-8")


def load_bundle(folder: Path) -> tuple[list[Chunk], np.ndarray, dict]:
    chunks = [Chunk(**row) for row in json.loads((folder / "chunks.json").read_text("utf-8"))]
    vectors = np.load(folder / "vectors.npy")
    manifest = json.loads((folder / "manifest.json").read_text("utf-8"))
    if len(chunks) != len(vectors):
        raise ValueError(f"{folder}: {len(chunks)} chunks but {len(vectors)} vectors")
    return chunks, vectors, manifest


def latest_bundle(builds: Path) -> Path:
    found = sorted(p for p in builds.glob("*") if (p / "manifest.json").exists())
    if not found:
        raise SystemExit(f"No build in {builds}. Run `uv run chat-pipeline build` first.")
    return found[-1]
