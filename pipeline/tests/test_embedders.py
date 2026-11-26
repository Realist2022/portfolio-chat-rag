from chat_pipeline.embedders import CachedEmbedder, HashEmbedder


def test_a_text_is_embedded_once(tmp_path):
    inner = HashEmbedder()
    cached = CachedEmbedder(inner, tmp_path / "cache.sqlite")
    first = cached.embed(["alpha", "beta"])
    second = cached.embed(["beta", "alpha", "gamma"])
    assert inner.calls == [["alpha", "beta"], ["gamma"]]
    assert second[:2] == [first[1], first[0]]


def test_a_different_model_never_reads_another_models_vectors(tmp_path):
    path = tmp_path / "cache.sqlite"
    CachedEmbedder(HashEmbedder(dimensions=8), path).embed(["alpha"])
    other = HashEmbedder(dimensions=16)
    CachedEmbedder(other, path).embed(["alpha"])
    assert other.calls == [["alpha"]]


def test_queries_bypass_the_cache(tmp_path):
    inner = HashEmbedder()
    cached = CachedEmbedder(inner, tmp_path / "cache.sqlite")
    cached.embed_query("q")
    cached.embed_query("q")
    assert len(inner.calls) == 2
