# The chat backend image that Cloud Run runs. Built from the repository root.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencies first, so a code change doesn't reinstall them.
COPY pyproject.toml uv.lock .python-version ./
COPY backend/pyproject.toml backend/pyproject.toml
COPY pipeline/pyproject.toml pipeline/pyproject.toml
RUN uv sync --frozen --no-dev --package chat-backend --no-install-workspace

COPY backend backend
COPY corpus corpus
RUN uv sync --frozen --no-dev --package chat-backend

RUN useradd --create-home app
USER app

ENV PORT=8080
CMD ["sh", "-c", "exec /app/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
