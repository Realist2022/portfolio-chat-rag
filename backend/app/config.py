"""Every setting the backend reads, in one place, read once from the environment.

On Cloud Run the secrets (OPENAI_API_KEY, CHAT_API_KEY, PUSHOVER_*) come from
Secret Manager as environment variables; see terraform/. Locally they come from
a .env file next to where you run uvicorn.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The chat model. Behind a setting so the evals, not a code change, decide a swap.
    openai_api_key: str = ""
    chat_model: str = "gpt-4o-mini"
    max_reply_tokens: int = 600
    max_tool_rounds: int = 3

    # The portfolio's /api/chat route sends this as a bearer token. Empty means no
    # check, which is only for local development: Terraform always sets it.
    chat_api_key: str = ""

    # Comma-separated sites allowed to call the API from a browser. The portfolio
    # calls it server to server, so in production this can stay narrow.
    allowed_origins: str = "http://localhost:3000"

    # Per-IP rate limit, per instance: a speed bump, not a wall. The portfolio's
    # route has its own limit in front of this one.
    rate_limit: int = 20
    rate_window_seconds: int = 600

    max_message_chars: int = 1000
    max_history_messages: int = 12

    pushover_token: str = ""
    pushover_user: str = ""

    # The short summary that is always in the prompt; everything else is retrieved.
    corpus_dir: Path = REPO_ROOT / "corpus"

    # Retrieval. With QDRANT_URL set, the live alias in Qdrant Cloud; without it, the
    # newest local build in data/builds/ (run `uv run chat-pipeline build`). The
    # defaults are the ones the retrieval eval pinned; change them only with a sweep.
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    data_dir: Path = REPO_ROOT / "data"
    retrieval_k: int = 5
    retrieval_per_doc_max: int = 2
    retrieval_fusion: str = "rrf"

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def settings() -> Settings:
    return Settings()
