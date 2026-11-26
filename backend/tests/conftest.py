import os

# Settings are read once at import; set what the tests rely on first.
os.environ.setdefault("CHAT_API_KEY", "test-key")
os.environ.setdefault("RATE_LIMIT", "3")
os.environ.setdefault("OPENAI_API_KEY", "unused")
