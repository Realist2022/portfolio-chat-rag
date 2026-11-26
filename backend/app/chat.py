"""One chat turn: retrieve, build the messages, call the model, run tools, cite.

`stream()` is the turn: it yields text as the model writes it, then a final
event with the sources the reply cited. `reply()` is the same turn collected
into one result, for the JSON endpoint. The OpenAI client and the retriever are
passed in, so tests (and the eval harness) can use stubs without the network.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

from app import prompts, tools
from app.config import Settings
from app.profile import Profile

CITATION = re.compile(r"\[(\d+)\]")
SHORT_QUESTION_WORDS = 6


@dataclass
class Source:
    n: int
    title: str
    heading: str
    url: str


@dataclass
class Result:
    reply: str
    sources: list[Source] = field(default_factory=list)


def search_query(message: str, history: list[dict]) -> str:
    """The text to retrieve with. A short follow-up ("and the stack?") borrows the
    previous question, which says what it is about."""
    if len(message.split()) >= SHORT_QUESTION_WORDS:
        return message
    previous = [m["content"] for m in history if m["role"] == "user"]
    return f"{previous[-1]} {message}" if previous else message


def cited_sources(text: str, passages: list) -> list[Source]:
    """The passages the reply cites, in order of first citation, one per location."""
    out: list[Source] = []
    seen: set[tuple[str, str]] = set()
    for match in CITATION.finditer(text):
        n = int(match.group(1))
        if not 1 <= n <= len(passages):
            continue  # a number the model made up
        c = passages[n - 1]
        key = (c.doc_id, c.heading)
        if key in seen:
            continue
        seen.add(key)
        out.append(Source(n=n, title=c.title, heading=c.heading, url=c.url))
    return out


class ChatEngine:
    def __init__(self, client, profile: Profile, settings: Settings, retriever=None):
        self.client = client
        self.profile = profile
        self.settings = settings
        self.retriever = retriever

    def retrieve(self, message: str, history: list[dict]) -> list:
        if self.retriever is None:
            return []
        try:
            hits = self.retriever.search(
                search_query(message, history), k=self.settings.retrieval_k
            )
        except Exception as e:  # a retrieval outage degrades to the summary, not an error
            print(f"Retrieval error: {e}", flush=True)
            return []
        return [h.chunk for h in hits]

    def system_prompt(self, passages: list) -> str:
        p = self.profile
        return prompts.system_prompt(p.name, p.summary, passages)

    def stream(self, message: str, history: list[dict]) -> Iterator[dict]:
        """Events: {"type": "delta", "text"} while the model writes, then
        {"type": "done", "reply", "sources"}."""
        s = self.settings
        passages = self.retrieve(message, history)
        messages = [{"role": "system", "content": self.system_prompt(passages)}, *history]
        messages.append({"role": "user", "content": message})
        written: list[str] = []

        # Up to max_tool_rounds rounds may call tools; the last round has none,
        # so the model must answer rather than loop.
        for round_ in range(s.max_tool_rounds + 1):
            request = {
                "model": s.chat_model,
                "messages": messages,
                "max_tokens": s.max_reply_tokens,
                "stream": True,
            }
            if round_ < s.max_tool_rounds:
                request["tools"] = tools.schemas()
            calls: dict[int, dict] = {}
            text: list[str] = []
            for chunk in self.client.chat.completions.create(**request):
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    text.append(delta.content)
                    written.append(delta.content)
                    yield {"type": "delta", "text": delta.content}
                for part in delta.tool_calls or []:
                    call = calls.setdefault(part.index, {"id": "", "name": "", "arguments": ""})
                    call["id"] = part.id or call["id"]
                    if part.function and part.function.name:
                        call["name"] += part.function.name
                    if part.function and part.function.arguments:
                        call["arguments"] += part.function.arguments
            if not calls:
                break
            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(text) or None,
                    "tool_calls": [
                        {
                            "id": c["id"],
                            "type": "function",
                            "function": {"name": c["name"], "arguments": c["arguments"]},
                        }
                        for c in calls.values()
                    ],
                }
            )
            for c in calls.values():
                print(f"Tool called: {c['name']}", flush=True)
                result = tools.run_tool_call(c["name"], c["arguments"])
                messages.append(
                    {"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)}
                )

        reply = "".join(written)
        yield {"type": "done", "reply": reply, "sources": cited_sources(reply, passages)}

    def reply(self, message: str, history: list[dict]) -> Result:
        for event in self.stream(message, history):
            if event["type"] == "done":
                return Result(reply=event["reply"], sources=event["sources"])
        raise RuntimeError("chat turn ended without a reply")
