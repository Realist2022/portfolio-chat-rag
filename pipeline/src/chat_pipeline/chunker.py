"""Corpus documents -> Chunks.

Markdown is split at its headings, so a CV role or a README section is one chunk
with a breadcrumb of the headings above it ("Sonny's CV > Experience: ..."). Code
blocks are dropped: visitors ask what a project does, not for its shell commands,
and commands embed as noise. A section under MIN_WORDS is folded into the next one
(a heading with one intro line says little alone); one over MAX_WORDS is split at
paragraphs. Plain text is treated as markdown with no headings.

A projects .json (a list exported from the portfolio) becomes one document per
project, doc_id "<source doc_id>-<slug>", so retrieval can cap and cite each
project on its own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from chat_pipeline.schema import Chunk
from chat_pipeline.sources import Source, load_sources

MIN_WORDS = 25
MAX_WORDS = 350

HEADING = re.compile(r"^(#{1,4})\s+(.+?)\s*#*\s*$")
FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass
class Section:
    path: list[str]  # headings below the H1, outermost first (the H1 is the source title)
    text: str

    @property
    def words(self) -> int:
        return len(self.text.split())


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def sections(markdown: str) -> list[Section]:
    """Split at headings, outside code fences. Each section keeps its heading path."""
    found: list[Section] = []
    stack: list[tuple[int, str]] = []
    lines: list[str] = []
    in_fence = False

    def flush() -> None:
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
        if text:
            found.append(Section([h for lv, h in stack if lv > 1], text))
        lines.clear()

    for line in markdown.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING.match(line)
        if match:
            flush()
            level = len(match.group(1))
            stack = [(lv, h) for lv, h in stack if lv < level] + [(level, match.group(2))]
        else:
            lines.append(line)
    flush()
    return found


def fold_small(found: list[Section]) -> list[Section]:
    """Fold each section under MIN_WORDS into the next one (or the one before, if last).

    The folded text keeps its own heading as a lead-in, so "Interests and hobbies"
    still says what it is inside the section it joins.
    """

    def lead(section: Section) -> str:
        if section.path:
            return f"{section.path[-1]}: {section.text}"
        return section.text

    out: list[Section] = []
    carry: Section | None = None
    for section in found:
        if carry:
            section = Section(section.path, f"{lead(carry)}\n\n{section.text}")
            carry = None
        if section.words < MIN_WORDS:
            carry = section
        else:
            out.append(section)
    if carry:
        if out:
            out[-1] = Section(out[-1].path, f"{out[-1].text}\n\n{lead(carry)}")
        else:
            out.append(carry)
    return out


def split_large(section: Section) -> list[Section]:
    """Pack paragraphs into parts of at most MAX_WORDS; split a huge paragraph by words."""
    if section.words <= MAX_WORDS:
        return [section]
    pieces: list[str] = []
    for paragraph in section.text.split("\n\n"):
        words = paragraph.split()
        if len(words) <= MAX_WORDS:
            pieces.append(paragraph)
        else:
            pieces += [" ".join(words[i : i + MAX_WORDS]) for i in range(0, len(words), MAX_WORDS)]
    parts: list[str] = []
    current: list[str] = []
    for piece in pieces:
        if current and len(" ".join(current + [piece]).split()) > MAX_WORDS:
            parts.append("\n\n".join(current))
            current = []
        current.append(piece)
    if current:
        parts.append("\n\n".join(current))
    return [Section(section.path, part) for part in parts]


def chunk_markdown(markdown: str, source: Source) -> list[Chunk]:
    found = [part for s in fold_small(sections(markdown)) for part in split_large(s)]
    return [
        Chunk(
            id=f"{source.doc_id}::{n:04d}",
            text=s.text,
            heading=" > ".join([source.title, *s.path]),
            doc_id=source.doc_id,
            title=source.title,
            url=source.url,
            kind=source.kind,
            aliases=source.aliases,
        )
        for n, s in enumerate(found)
    ]


def chunk_projects(projects: list[dict], source: Source) -> list[Chunk]:
    chunks = []
    for project in projects:
        title = project["title"]
        links = project.get("links") or []
        stack = project.get("techStack") or []
        lines = [project["description"]]
        if stack:
            lines.append(f"Tech stack: {', '.join(stack)}.")
        if links:
            lines.append("Links: " + "; ".join(f"{x['label']} ({x['url']})" for x in links) + ".")
        github = next((x["url"] for x in links if "github.com" in x["url"]), "")
        doc_id = f"{source.doc_id}-{slug(title)}"
        chunks.append(
            Chunk(
                id=f"{doc_id}::0000",
                text="\n\n".join(lines),
                heading=f"Projects > {title}",
                doc_id=doc_id,
                title=title,
                url=github or (links[0]["url"] if links else source.url),
                kind=source.kind,
                aliases=source.aliases,
            )
        )
    return chunks


def chunk_source(corpus_dir: Path, source: Source) -> list[Chunk]:
    path = corpus_dir / source.path
    if path.suffix == ".json":
        return chunk_projects(json.loads(path.read_text(encoding="utf-8")), source)
    return chunk_markdown(path.read_text(encoding="utf-8"), source)


def build_chunks(corpus_dir: Path) -> list[Chunk]:
    chunks = [c for s in load_sources(corpus_dir) for c in chunk_source(corpus_dir, s)]
    ids = [c.id for c in chunks]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate chunk ids: {sorted(duplicates)}")
    return chunks
