"""The Chunk model, shared by the pipeline and (from phase 2) the backend.

Adapted from an earlier RAG pipeline's schema: store the verbatim text to show and
cite, embed a contextualised version with the heading and aliases in front.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field


class Chunk(BaseModel):
    id: str
    text: str = Field(min_length=1)  # verbatim: what is shown and cited
    heading: str = ""  # breadcrumb of headings above it

    doc_id: str  # from corpus/sources.yaml, never guessed
    title: str
    url: str = ""  # public link shown as the source
    kind: str  # profile | project | readme | faq
    aliases: list[str] = Field(default_factory=list)

    def text_to_embed(self) -> str:
        body = f"{self.heading}\n\n{self.text}" if self.heading else self.text
        if self.aliases:
            return f"{self.title} ({'; '.join(self.aliases)})\n{body}"
        return body

    def content_hash(self) -> str:
        """sha256 of text_to_embed(): the embedding cache key (phase 1)."""
        return hashlib.sha256(self.text_to_embed().encode("utf-8")).hexdigest()
