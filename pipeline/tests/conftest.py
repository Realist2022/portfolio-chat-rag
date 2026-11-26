from pathlib import Path

import pytest

from chat_pipeline.cli import main


@pytest.fixture(scope="session")
def built(tmp_path_factory) -> Path:
    """One offline build of the real corpus (hash embedder, local Qdrant) in a temp dir."""
    data = tmp_path_factory.mktemp("data")
    assert main(["build", "--embedder", "hash", "--data", str(data), "--promote"]) == 0
    return data
