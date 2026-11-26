"""Retrieval eval: does the right document come back for each golden question?

Each case lists what a correct retrieval contains: a doc_id, or doc_id#text to
require a section whose heading contains that text (e.g. profile-cv#Foodstuffs).
A case is a hit at k if any of its top k chunks matches any expectation.

  hit@1, hit@5  share of cases with a match at rank 1, or anywhere in the top 5
  MRR           mean of 1/rank of the first match (0 when none in the top 10)

Cases with no expectations are out of scope ("what's the weather?"). They are not
scored here; phase 2 uses them to set the similarity floor, and phase 4's gate to
check the bot declines.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from chat_pipeline.retrieval import Hit, Retriever

DEPTH = 10


@dataclass(frozen=True)
class Case:
    id: str
    question: str
    expect: list[str]


def load_cases(path: Path) -> list[Case]:
    cases = [Case(**row) for row in json.loads(path.read_text("utf-8"))]
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate case ids")
    return cases


def matches(hit: Hit, expectation: str) -> bool:
    doc_id, _, heading = expectation.partition("#")
    if hit.chunk.doc_id != doc_id:
        return False
    return heading.lower() in hit.chunk.heading.lower()


def first_rank(hits: list[Hit], expect: list[str]) -> int | None:
    for rank, hit in enumerate(hits, start=1):
        if any(matches(hit, e) for e in expect):
            return rank
    return None


def run(retriever: Retriever, cases: list[Case]) -> dict:
    rows = []
    for case in cases:
        if not case.expect:
            continue
        hits = retriever.search(case.question, k=DEPTH)
        rank = first_rank(hits, case.expect)
        rows.append({"id": case.id, "rank": rank, "top": [h.chunk.id for h in hits[:3]]})
    scored = len(rows) or 1
    return {
        "retriever": retriever.name,
        "model": retriever.model,
        "cases": len(rows),
        "hit@1": round(sum(r["rank"] == 1 for r in rows) / scored, 3),
        "hit@5": round(sum(r["rank"] is not None and r["rank"] <= 5 for r in rows) / scored, 3),
        "mrr": round(sum(1 / r["rank"] for r in rows if r["rank"]) / scored, 3),
        "per_case": rows,
    }


def report(result: dict, baseline: dict | None = None) -> str:
    lines = [f"{result['retriever']} ({result['model']}), {result['cases']} cases"]
    for row in result["per_case"]:
        rank = row["rank"]
        mark = "ok " if rank == 1 else ("~  " if rank and rank <= 5 else "MISS")
        lines.append(f"  {mark} {row['id']:<28} rank {rank or '-':<3} top: {', '.join(row['top'])}")
    summary = "  ".join(f"{m} {result[m]:.3f}" for m in ("hit@1", "hit@5", "mrr"))
    if baseline and baseline.get("model") == result["model"]:
        deltas = "  ".join(f"{m} {result[m] - baseline[m]:+.3f}" for m in ("hit@1", "hit@5", "mrr"))
        summary += f"   vs baseline: {deltas}"
    lines.append(summary)
    return "\n".join(lines)


def sweep_table(results: list[dict], baselines: dict[str, dict]) -> str:
    """One line per setting, plus each miss, so the best setting is easy to pick."""
    lines = [f"{'setting':<22} {'hit@1':>6} {'hit@5':>6} {'mrr':>6}  misses (not in top 5)"]
    for name, b in baselines.items():
        lines.append(
            f"{'baseline ' + name:<22} {b['hit@1']:>6.3f} {b['hit@5']:>6.3f} {b['mrr']:>6.3f}"
        )
    for r in results:
        misses = [row["id"] for row in r["per_case"] if not row["rank"] or row["rank"] > 5]
        lines.append(
            f"{r['retriever']:<22} {r['hit@1']:>6.3f} {r['hit@5']:>6.3f} {r['mrr']:>6.3f}  "
            + (", ".join(misses) or "-")
        )
    return "\n".join(lines)
