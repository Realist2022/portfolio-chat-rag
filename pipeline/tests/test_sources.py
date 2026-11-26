from pathlib import Path

import pytest

from chat_pipeline.cli import CORPUS, main
from chat_pipeline.schema import Chunk
from chat_pipeline.sources import load_sources


def test_corpus_sources_load():
    ids = {s.doc_id for s in load_sources(CORPUS)}
    assert {"profile-summary", "profile-cv"} <= ids


def test_status_runs(capsys):
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "profile-cv" in out and "project" in out


def test_bad_kind_is_rejected(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    (tmp_path / "sources.yaml").write_text(
        "sources:\n  - {doc_id: a, title: A, kind: blog, path: a.txt}\n"
    )
    with pytest.raises(ValueError, match="unknown kind"):
        load_sources(tmp_path)


def test_chunk_embeds_heading_and_aliases():
    c = Chunk(
        id="1",
        text="Scores CVs.",
        heading="Guestimator",
        doc_id="g",
        title="CV Guestimator",
        kind="project",
        aliases=["CV match"],
    )
    assert c.text_to_embed() == "CV Guestimator (CV match)\nGuestimator\n\nScores CVs."
    assert len(c.content_hash()) == 64
