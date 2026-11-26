"""Every instruction the model gets lives in this folder, versioned.

Change a prompt by editing its file, bumping PROMPT_VERSION and adding a line to
CHANGELOG.md, so a trace or an eval run can always say which prompt it used.
"""

from pathlib import Path

PROMPT_VERSION = "v1"

_DIR = Path(__file__).parent


def system_prompt(name: str, summary: str, cv: str) -> str:
    template = (_DIR / "system.md").read_text(encoding="utf-8")
    return template.format(name=name, summary=summary, cv=cv)
