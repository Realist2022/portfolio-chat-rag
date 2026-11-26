"""Reads corpus/sources.yaml: what a human asserts about each document."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

KINDS = {"profile", "project", "readme", "faq"}


class Source(BaseModel):
    doc_id: str
    title: str
    kind: str
    path: str  # relative to corpus/
    url: str = ""
    aliases: list[str] = Field(default_factory=list)


def load_sources(corpus_dir: Path) -> list[Source]:
    data = yaml.safe_load((corpus_dir / "sources.yaml").read_text(encoding="utf-8")) or {}
    sources = [Source(**entry) for entry in data.get("sources", [])]
    seen: set[str] = set()
    for s in sources:
        if s.kind not in KINDS:
            raise ValueError(f"{s.doc_id}: unknown kind {s.kind!r}")
        if s.doc_id in seen:
            raise ValueError(f"duplicate doc_id {s.doc_id!r}")
        if not (corpus_dir / s.path).exists():
            raise ValueError(f"{s.doc_id}: {s.path} not found")
        seen.add(s.doc_id)
    return sources
