"""Every instruction the model gets lives in this folder, versioned.

Change a prompt by editing its file, bumping PROMPT_VERSION and adding a line to
CHANGELOG.md, so a trace or an eval run can always say which prompt it used.
"""

from pathlib import Path

PROMPT_VERSION = "v2"

_DIR = Path(__file__).parent


def _read(name: str) -> str:
    return (_DIR / name).read_text(encoding="utf-8").strip()


def format_passages(passages: list) -> str:
    """[n] Title > heading, then the verbatim text. n is what the model cites."""
    if not passages:
        return _read("passages_none.md")
    return "\n\n".join(f"[{n}] {c.heading}\n{c.text}" for n, c in enumerate(passages, start=1))


def system_prompt(name: str, summary: str, passages: list) -> str:
    return _read("system.md").format(name=name, summary=summary, passages=format_passages(passages))
