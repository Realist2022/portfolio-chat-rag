"""FastAPI app: /health, /api/chat and /api/chat/stream.

/api/chat keeps the portfolio's current shape ({message, history} -> {reply}),
adding the cited `sources`. /api/chat/stream takes the same request and answers
with server-sent events: `delta` events as the reply is written, then one `done`
event with the full reply and its sources (or an `error` event).
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Iterator
from dataclasses import asdict
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.chat import ChatEngine
from app.config import settings
from app.profile import load_profile
from app.ratelimit import RateLimiter, client_ip

cfg = settings()

docs = {} if cfg.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
app = FastAPI(title="portfolio-chat-rag", **docs)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cfg.origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

limiter = RateLimiter(cfg.rate_limit, cfg.rate_window_seconds)
_engine: ChatEngine | None = None


def engine() -> ChatEngine:
    """Built on first use, so importing the app needs no API key (tests, CI)."""
    global _engine
    if _engine is None:
        from openai import OpenAI

        from app.retrieval import build_retriever

        _engine = ChatEngine(
            OpenAI(api_key=cfg.openai_api_key),
            load_profile(cfg.corpus_dir),
            cfg,
            build_retriever(cfg),
        )
    return _engine


def require_key(authorization: str = Header(default="")) -> None:
    if not cfg.chat_api_key:
        return
    expected = f"Bearer {cfg.chat_api_key}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


class HistoryMessage(BaseModel):
    # Only user and assistant turns: a "system" message from a caller could
    # otherwise rewrite the bot's instructions.
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=cfg.max_message_chars)
    history: list[HistoryMessage] = []


class SourceOut(BaseModel):
    n: int  # the [n] in the reply
    title: str
    heading: str
    url: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[SourceOut] = []


UNAVAILABLE = "The assistant is unavailable right now. Please try again shortly."
SLOW_DOWN = "You're sending messages quickly. Please wait a few minutes and try again."


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def check_rate(request: Request) -> None:
    if not limiter.allow(client_ip(request)):
        raise HTTPException(status_code=429, detail=SLOW_DOWN)


def trimmed(req: ChatRequest) -> list[dict]:
    return [m.model_dump() for m in req.history[-cfg.max_history_messages :]]


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    check_rate(request)
    try:
        result = engine().reply(req.message, trimmed(req))
    except Exception as e:
        # Log the real error; never send exception text to the caller.
        print(f"Chat error: {e}", flush=True)
        raise HTTPException(status_code=500, detail=UNAVAILABLE) from None
    return ChatResponse(reply=result.reply, sources=[asdict(s) for s in result.sources])


def sse(event: dict) -> str:
    return f"data: {json.dumps(event)}\n\n"


@app.post("/api/chat/stream", dependencies=[Depends(require_key)])
def chat_stream(req: ChatRequest, request: Request) -> StreamingResponse:
    check_rate(request)
    history = trimmed(req)

    def events() -> Iterator[str]:
        try:
            for event in engine().stream(req.message, history):
                if event["type"] == "done":
                    event = {**event, "sources": [asdict(s) for s in event["sources"]]}
                yield sse(event)
        except Exception as e:
            print(f"Chat error: {e}", flush=True)
            yield sse({"type": "error", "message": UNAVAILABLE})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
