from chat_pipeline.chunker import MAX_WORDS, build_chunks, chunk_markdown, chunk_projects
from chat_pipeline.cli import CORPUS
from chat_pipeline.sources import Source

SOURCE = Source(doc_id="doc", title="Doc", kind="readme", path="doc.md", url="https://x")
WORDS = " ".join(["word"] * 30)


def test_splits_at_headings_with_a_breadcrumb():
    md = f"# Doc\n\n{WORDS}\n\n## Setup\n\n{WORDS}\n\n### Docker\n\n{WORDS}\n"
    chunks = chunk_markdown(md, SOURCE)
    assert [c.heading for c in chunks] == ["Doc", "Doc > Setup", "Doc > Setup > Docker"]
    assert [c.id for c in chunks] == ["doc::0000", "doc::0001", "doc::0002"]
    assert all(c.url == "https://x" for c in chunks)


def test_code_blocks_are_dropped_and_their_hashes_are_not_headings():
    md = f"## Run\n\n{WORDS}\n\n```bash\n# Full pipeline\nuv run thing\n```\n"
    [chunk] = chunk_markdown(md, SOURCE)
    assert "uv run" not in chunk.text and chunk.heading == "Doc > Run"


def test_a_small_section_folds_into_the_next_with_its_heading():
    md = f"## Intro\n\nShort.\n\n## Body\n\n{WORDS}\n\n## Hobbies\n\nGym.\n"
    chunks = chunk_markdown(md, SOURCE)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("Intro: Short.") and chunks[0].text.endswith("Hobbies: Gym.")


def test_a_large_section_is_split_at_paragraphs():
    para = " ".join(["w"] * 200)
    chunks = chunk_markdown(f"## Big\n\n{para}\n\n{para}\n\n{para}\n", SOURCE)
    assert len(chunks) == 3
    assert all(len(c.text.split()) <= MAX_WORDS for c in chunks)


def test_each_project_is_its_own_document():
    source = Source(doc_id="project", title="Project", kind="project", path="p.json")
    projects = [
        {
            "title": "Z App — Station Locator",
            "description": "Maps.",
            "techStack": ["React"],
            "links": [
                {"label": "Video", "url": "https://youtu.be/x"},
                {"label": "Code", "url": "https://github.com/a/b"},
            ],
        }
    ]
    [chunk] = chunk_projects(projects, source)
    assert chunk.doc_id == "project-z-app-station-locator"
    assert chunk.url == "https://github.com/a/b"  # GitHub preferred as the citation
    assert "Tech stack: React." in chunk.text


def test_the_real_corpus_chunks_without_contact_details():
    chunks = build_chunks(CORPUS)
    assert len(chunks) > 40
    assert {"profile-cv", "project-growise-app", "readme-ft-model2"} <= {c.doc_id for c in chunks}
    assert not [c.id for c in chunks if "@gmail" in c.text or "+64" in c.text]
