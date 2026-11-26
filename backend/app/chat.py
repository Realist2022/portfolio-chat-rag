"""One chat turn: build the messages, call the model, run tools, return the reply.

The OpenAI client is passed in, so tests (and later the eval harness) can use a
stub without touching the network.
"""

from __future__ import annotations

import json

from app import prompts, tools
from app.config import Settings
from app.profile import Profile


class ChatEngine:
    def __init__(self, client, profile: Profile, settings: Settings):
        self.client = client
        self.profile = profile
        self.settings = settings

    def system_prompt(self) -> str:
        p = self.profile
        return prompts.system_prompt(p.name, p.summary, p.cv)

    def reply(self, message: str, history: list[dict]) -> str:
        s = self.settings
        messages = [{"role": "system", "content": self.system_prompt()}, *history]
        messages.append({"role": "user", "content": message})

        for _ in range(s.max_tool_rounds):
            response = self.client.chat.completions.create(
                model=s.chat_model,
                messages=messages,
                tools=tools.schemas(),
                max_tokens=s.max_reply_tokens,
            )
            choice = response.choices[0]
            if choice.finish_reason != "tool_calls":
                return choice.message.content or ""
            messages.append(choice.message)
            for call in choice.message.tool_calls:
                print(f"Tool called: {call.function.name}", flush=True)
                result = tools.run_tool_call(call.function.name, call.function.arguments)
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": json.dumps(result)}
                )

        # Too many tool rounds: answer without tools rather than loop.
        response = self.client.chat.completions.create(
            model=s.chat_model, messages=messages, max_tokens=s.max_reply_tokens
        )
        return response.choices[0].message.content or ""
