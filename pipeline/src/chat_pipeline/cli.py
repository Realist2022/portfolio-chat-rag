"""`uv run chat-pipeline status`: list the corpus. Chunk, embed and index arrive in phase 1."""

from __future__ import annotations

import argparse
from pathlib import Path

from chat_pipeline.sources import load_sources

CORPUS = Path(__file__).resolve().parents[3] / "corpus"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chat-pipeline")
    parser.add_argument("command", choices=["status"])
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    args = parser.parse_args(argv)

    for s in load_sources(args.corpus):
        size = (args.corpus / s.path).stat().st_size
        print(f"{s.doc_id:<20} {s.kind:<8} {size:>7,} bytes  {s.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
