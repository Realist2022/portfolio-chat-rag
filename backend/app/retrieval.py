"""Which retriever the chat uses, built once from the settings.

The retrievers themselves live in the pipeline package (chat_pipeline.retrieval),
so the chat and the retrieval eval run exactly the same code: a score the eval
reports is the retrieval the visitor gets.
"""

from __future__ import annotations

from app.config import Settings


def build_retriever(cfg: Settings):
    """Qdrant when QDRANT_URL is set, else the newest local build, else None.

    Never raises: a chatbot that can only answer from the summary beats one that is
    down, and the warning is in the logs.
    """
    try:
        return _build(cfg)
    except Exception as e:
        print(f"Warning: retrieval unavailable ({e}). Answering from the summary only.")
        return None


def _build(cfg: Settings):
    from chat_pipeline import bundle, retrieval
    from chat_pipeline.embedders import OpenAIEmbedder

    if cfg.qdrant_url:
        from qdrant_client import QdrantClient

        embedder = OpenAIEmbedder()
        client = QdrantClient(url=cfg.qdrant_url, api_key=cfg.qdrant_api_key or None)
        print(f"Retrieval: Qdrant alias {retrieval.ALIAS}", flush=True)
        return retrieval.QdrantRetriever(
            client, retrieval.ALIAS, embedder, cfg.retrieval_per_doc_max, cfg.retrieval_fusion
        )

    builds = cfg.data_dir / "builds"
    if builds.exists() and any(builds.iterdir()):
        folder = bundle.latest_bundle(builds)
        chunks, vectors, manifest = bundle.load_bundle(folder)
        print(f"Retrieval: local build {folder.name} ({len(chunks)} chunks)", flush=True)
        return retrieval.MemoryRetriever(
            chunks, vectors, OpenAIEmbedder(), manifest["model"], cfg.retrieval_per_doc_max
        )

    print("Warning: no QDRANT_URL and no local build; answering from the summary only.")
    return None
