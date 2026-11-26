"""The tools the model may call, as an explicit registry.

Only what is listed in TOOLS can run: the model names a tool, and an unknown
name gets an error back instead of a lookup in globals().
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import requests

from app.config import settings

_db = None
_db_ready = False


def _firestore():
    """Firestore client, created on first use. None when there are no credentials."""
    global _db, _db_ready
    if not _db_ready:
        _db_ready = True
        try:
            import firebase_admin
            from firebase_admin import credentials, firestore

            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.ApplicationDefault())
            _db = firestore.client()
        except Exception as e:  # expected locally without Google credentials
            print(f"Firestore unavailable: {e}", flush=True)
    return _db


def push(text: str) -> None:
    s = settings()
    if not (s.pushover_token and s.pushover_user):
        return
    try:
        requests.post(
            "https://api.pushover.net/1/messages.json",
            data={"token": s.pushover_token, "user": s.pushover_user, "message": text},
            timeout=5,
        )
    except Exception as e:
        print(f"Pushover error: {e}", flush=True)


def record_user_details(email: str, name: str = "Name not provided", notes: str = "not provided"):
    push(f"New lead: {name} ({email}). Notes: {notes}")
    db = _firestore()
    if db:
        from firebase_admin import firestore

        db.collection("portfolio_leads").document(email).set(
            {"name": name, "email": email, "notes": notes, "timestamp": firestore.SERVER_TIMESTAMP}
        )
    return {"recorded": "ok"}


def record_unknown_question(question: str):
    push(f"Unanswered question: {question}")
    db = _firestore()
    if db:
        from firebase_admin import firestore

        db.collection("portfolio_unanswered").add(
            {"question": question, "timestamp": firestore.SERVER_TIMESTAMP}
        )
    return {"recorded": "ok"}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    run: Callable[..., dict]

    def schema(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool(
            "record_user_details",
            "Record that a visitor wants to be in touch and gave an email address.",
            {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "The visitor's email address"},
                    "name": {"type": "string", "description": "The visitor's name, if given"},
                    "notes": {
                        "type": "string",
                        "description": "Context from the conversation worth recording",
                    },
                },
                "required": ["email"],
                "additionalProperties": False,
            },
            record_user_details,
        ),
        Tool(
            "record_unknown_question",
            "Record a genuine question about Sonny's career, skills, projects or availability "
            "that you couldn't answer. Don't use it for off-topic, joke or test questions.",
            {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "The unanswered question"}
                },
                "required": ["question"],
                "additionalProperties": False,
            },
            record_unknown_question,
        ),
    ]
}


def schemas() -> list[dict]:
    return [t.schema() for t in TOOLS.values()]


def run_tool_call(name: str, arguments: str) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        return {"error": "unknown tool"}
    try:
        return tool.run(**json.loads(arguments))
    except Exception as e:
        print(f"Tool error ({name}): {e}", flush=True)
        return {"error": "tool failed"}
