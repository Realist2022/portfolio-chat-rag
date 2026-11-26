import pytest

from chat_pipeline import retrieval
from chat_pipeline.bundle import latest_bundle, load_bundle
from chat_pipeline.cli import QUESTIONS, main
from chat_pipeline.embedders import HashEmbedder
from chat_pipeline.evaluate import Case, load_cases, run
from chat_pipeline.keywords import query_sparse, tokens


def test_tokens_fold_plurals_and_drop_stopwords():
    assert tokens("What are Sonny's projects using LoRA?") == ["sonny", "project", "using", "lora"]
    assert query_sparse("the a of") == ([], [])


def test_bundle_matches_the_collection(built):
    chunks, vectors, manifest = load_bundle(latest_bundle(built / "builds"))
    assert len(chunks) == len(vectors) == manifest["count"]
    client = retrieval.qdrant_client(built / "qdrant")
    try:
        live = retrieval.live_collection(client)
        assert live == retrieval.COLLECTION_PREFIX + manifest["build_id"]
        assert client.count(live).count == len(chunks)
    finally:
        client.close()


@pytest.mark.parametrize("kind", ["qdrant", "memory"])
def test_both_retrievers_find_an_exact_name_and_cap_per_document(built, kind):
    client = retrieval.qdrant_client(built / "qdrant")
    try:
        embedder = HashEmbedder()
        if kind == "qdrant":
            r = retrieval.QdrantRetriever(client, retrieval.live_collection(client), embedder)
        else:
            chunks, vectors, m = load_bundle(latest_bundle(built / "builds"))
            r = retrieval.MemoryRetriever(chunks, vectors, embedder, m["model"])
        hits = r.search("Has he worked with SonarQube?", k=5)
        headings = [h.chunk.heading for h in hits[:3]]
        assert "Sonny's CV > Experience: Software Engineer at Foodstuffs" in headings
        many = r.search("Guestimator fine-tuning model", k=10)
        docs = [h.chunk.doc_id for h in many]
        assert max(docs.count(d) for d in docs) <= retrieval.PER_DOC_MAX
    finally:
        client.close()


def test_a_collection_built_with_another_model_is_refused(built):
    client = retrieval.qdrant_client(built / "qdrant")
    try:
        with pytest.raises(SystemExit, match="built with hash-bow-256"):
            retrieval.QdrantRetriever(client, retrieval.ALIAS, HashEmbedder(dimensions=64))
    finally:
        client.close()


def test_golden_questions_name_real_documents(built):
    chunks, _, _ = load_bundle(latest_bundle(built / "builds"))
    for case in load_cases(QUESTIONS):
        for expectation in case.expect:
            doc_id, _, heading = expectation.partition("#")
            assert any(
                c.doc_id == doc_id and heading.lower() in c.heading.lower() for c in chunks
            ), f"{case.id}: {expectation} matches no chunk"


def test_eval_scores_and_reports(built, capsys):
    assert main(["eval", "--embedder", "hash", "--data", str(built)]) == 0
    out = capsys.readouterr().out
    assert "qdrant (hash-bow-256)" in out and "memory (hash-bow-256)" in out and "mrr" in out


class Fixed:
    name, model = "fixed", "m"

    def __init__(self, hits):
        self.hits = hits

    def search(self, question, k=5):
        return self.hits


def test_metrics(built):
    chunks, _, _ = load_bundle(latest_bundle(built / "builds"))
    by_doc = {c.doc_id: c for c in chunks}
    hits = [retrieval.Hit(by_doc[d], 1.0) for d in ["profile-about", "project-growise-app"]]
    cases = [
        Case("a", "q", ["project-growise-app"]),
        Case("b", "q", ["profile-about"]),
        Case("c", "q", ["readme-ft-model2"]),
        Case("oos", "q", []),
    ]
    result = run(Fixed(hits), cases)
    assert result["cases"] == 3
    assert result["hit@1"] == round(1 / 3, 3)
    assert result["hit@5"] == round(2 / 3, 3)
    assert result["mrr"] == round((0.5 + 1) / 3, 3)


def test_prune_keeps_the_live_collection(tmp_path):
    from chat_pipeline.bundle import normalise
    from chat_pipeline.chunker import build_chunks
    from chat_pipeline.cli import CORPUS

    chunks = build_chunks(CORPUS)[:3]
    vectors = normalise(HashEmbedder().embed([c.text for c in chunks]))
    client = retrieval.qdrant_client(tmp_path / "q")
    try:
        names = [f"{retrieval.COLLECTION_PREFIX}2026010{i}" for i in range(1, 6)]
        for n in names:
            retrieval.index_chunks(client, n, chunks, vectors, {"model": "hash-bow-256"})
        retrieval.promote(client, names[0])
        deleted = retrieval.prune(client, keep=2)
        assert deleted == names[1:3]
        left = {c.name for c in client.get_collections().collections}
        assert left == {names[0], *names[3:]}
    finally:
        client.close()
