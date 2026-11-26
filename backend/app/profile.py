"""The text the bot answers from, until retrieval arrives in phase 2.

Only redacted, public material lives in corpus/: no phone number, personal email
or home address, so the bot cannot repeat them.
"""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    name: str
    summary: str
    cv: str


def load_profile(corpus_dir: Path, name: str = "Sonny Tapara") -> Profile:
    def read(relative: str) -> str:
        path = corpus_dir / relative
        if not path.exists():
            print(f"Warning: {path} not found.", flush=True)
            return ""
        return path.read_text(encoding="utf-8")

    return Profile(name=name, summary=read("profile/summary.txt"), cv=read("profile/cv.md"))
