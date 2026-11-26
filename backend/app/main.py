"""FastAPI app: /health and /api/chat.

The request and response shapes match the portfolio's current backend
({message, history} -> {reply}), so the portfolio can switch to this service by
changing one URL. Sources and streaming join in phase 2.
"""

from __future__ import annotations

import hmac
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.chat import ChatEngine
from app.config import settings
from app.profile import load_profile
from app.ratelimit import RateLimiter, client_ip

cfg = settings()

app = FastAPI(title="portfolio-chat-rag")
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

        _engine = ChatEngine(OpenAI(api_key=cfg.openai_api_key), load_profile(cfg.corpus_dir), cfg)
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


class ChatResponse(BaseModel):
    reply: str


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse, dependencies=[Depends(require_key)])
def chat(req: ChatRequest, request: Request) -> ChatResponse:
    if not limiter.allow(client_ip(request)):
        raise HTTPException(
            status_code=429,
            detail="You're sending messages quickly. Please wait a few minutes and try again.",
        )
    history = [m.model_dump() for m in req.history[-cfg.max_history_messages :]]
    try:
        return ChatResponse(reply=engine().reply(req.message, history))
    except Exception as e:
        # Log the real error; never send exception text to the caller.
        print(f"Chat error: {e}", flush=True)
        raise HTTPException(
            status_code=500,
            detail="The assistant is unavailable right now. Please try again shortly.",
        ) from None
