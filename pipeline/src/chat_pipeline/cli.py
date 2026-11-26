"""The pipeline's commands. Run from the repo root with `uv run chat-pipeline <command>`.

  status   list the corpus
  chunks   chunk the corpus and print what each document became
  build    chunk, embed (cached), write a bundle and index a new Qdrant collection
  search   ask a question, print the top chunks
  eval     score retrieval on evals/retrieval/questions.json

--embedder openai (default) needs OPENAI_API_KEY in .env; --embedder hash runs
offline with meaningless scores, for tests and trying the commands out.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

from chat_pipeline import bundle as bundles
from chat_pipeline import retrieval
from chat_pipeline.chunker import build_chunks
from chat_pipeline.embedders import make_embedder
from chat_pipeline.evaluate import load_cases, report, run
from chat_pipeline.sources import load_sources

ROOT = Path(__file__).resolve().parents[3]
CORPUS = ROOT / "corpus"
DATA = ROOT / "data"
QUESTIONS = ROOT / "evals" / "retrieval" / "questions.json"
BASELINES = ROOT / "evals" / "retrieval" / "baselines"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="chat-pipeline")
    parser.add_argument("command", choices=["status", "chunks", "build", "search", "eval"])
    parser.add_argument("question", nargs="?", help="for search")
    parser.add_argument("--corpus", type=Path, default=CORPUS)
    parser.add_argument("--data", type=Path, default=DATA)
    parser.add_argument("--questions", type=Path, default=QUESTIONS)
    parser.add_argument("--embedder", choices=["openai", "hash"], default="openai")
    parser.add_argument("--retriever", choices=["qdrant", "memory", "both"], default="both")
    parser.add_argument("--promote", action="store_true", help="build: point the alias at it")
    parser.add_argument("--save-baseline", action="store_true", help="eval: pin these scores")
    parser.add_argument("-k", type=int, default=5)
    args = parser.parse_args(argv)
    load_dotenv(ROOT / ".env")

    if args.command == "status":
        for s in load_sources(args.corpus):
            size = (args.corpus / s.path).stat().st_size
            print(f"{s.doc_id:<24} {s.kind:<8} {size:>7,} bytes  {s.title}")
        return 0

    if args.command == "chunks":
        chunks = build_chunks(args.corpus)
        for c in chunks:
            print(f"{c.id:<40} {len(c.text.split()):>4} words  {c.heading}")
        print(f"{len(chunks)} chunks from {len({c.doc_id for c in chunks})} documents")
        return 0

    embedder = make_embedder(args.embedder, args.data / "cache" / "embeddings.sqlite")
    client = retrieval.qdrant_client(args.data / "qdrant")
    try:
        if args.command == "build":
            return build(args, embedder, client)
        retrievers = pick_retrievers(args, embedder, client)
        if args.command == "search":
            if not args.question:
                parser.error("search needs a question")
            for r in retrievers:
                print(f"== {r.name}")
                for hit in r.search(args.question, k=args.k):
                    print(f"  {hit.score:.3f}  {hit.chunk.id:<36} {hit.chunk.heading}")
            return 0
        return evaluate(args, retrievers)
    finally:
        client.close()


def build(args, embedder, client) -> int:
    chunks = build_chunks(args.corpus)
    build_id = bundles.new_build_id()
    vectors = bundles.normalise(embedder.embed([c.text_to_embed() for c in chunks]))
    manifest = {
        "build_id": build_id,
        "model": embedder.model,
        "dimensions": embedder.dimensions,
        "count": len(chunks),
        "documents": sorted({c.doc_id for c in chunks}),
    }
    folder = args.data / "builds" / build_id
    bundles.write_bundle(folder, chunks, vectors, manifest)
    collection = retrieval.COLLECTION_PREFIX + build_id
    meta = {k: manifest[k] for k in ("build_id", "model", "dimensions", "count")}
    retrieval.index_chunks(client, collection, chunks, vectors, meta)
    print(f"Built {len(chunks)} chunks -> {folder.relative_to(args.data.parent)} and {collection}")
    if args.promote:
        previous = retrieval.promote(client, collection)
        print(f"Alias {retrieval.ALIAS} -> {collection} (was {previous or 'unset'})")
    else:
        print(
            f"Not live. Check it with `eval`, then `build --promote` to switch {retrieval.ALIAS}."
        )
    for name in retrieval.prune(client):
        print(f"Deleted old collection {name}")
    return 0


def pick_retrievers(args, embedder, client) -> list[retrieval.Retriever]:
    folder = bundles.latest_bundle(args.data / "builds")
    picked: list[retrieval.Retriever] = []
    if args.retriever in ("qdrant", "both"):
        # The live alias if set, else the newest build: eval checks a build before promotion.
        collection = retrieval.live_collection(client) if args.command == "search" else None
        collection = collection or retrieval.COLLECTION_PREFIX + folder.name
        picked.append(retrieval.QdrantRetriever(client, collection, embedder))
    if args.retriever in ("memory", "both"):
        chunks, vectors, manifest = bundles.load_bundle(folder)
        picked.append(retrieval.MemoryRetriever(chunks, vectors, embedder, manifest["model"]))
    return picked


def evaluate(args, retrievers) -> int:
    cases = load_cases(args.questions)
    for r in retrievers:
        result = run(r, cases)
        path = BASELINES / f"{r.name}.json"
        baseline = json.loads(path.read_text("utf-8")) if path.exists() else None
        print(report(result, baseline))
        if args.save_baseline:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(result, indent=2) + "\n", "utf-8")
            print(f"Pinned {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
