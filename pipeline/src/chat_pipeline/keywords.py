"""BM25 terms, shared by Qdrant's sparse vectors and the in-memory baseline.

Embeddings match meaning and are weak on exact names: "LoRA", "Cortex.io",
"SonarQube", "Hiab". BM25 matches the literal terms. Tokenising is ported from
an earlier RAG project's keyword_index.py: lowercase, stopwords out, plural "s" folded.

For Qdrant, each term is hashed to a sparse index and given BM25's term-frequency
weight; the collection's IDF modifier supplies the other half of BM25 at query
time, so the index stays correct as documents are added. Queries send weight 1
per term. This avoids downloading a tokenizer model at build or request time.
"""

from __future__ import annotations

import hashlib
import math
import re
from collections import Counter

import numpy as np

from chat_pipeline.schema import Chunk

TOKEN = re.compile(r"[a-zā-ū]+\d+(?:\.\d+)*|\d+(?:\.\d+)+|[a-zā-ū0-9]+")
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from has have he his how i if in is it its "
    "may me must my of on or our shall should she so tell that the their them there these "
    "they this to us was we what when where which who will with you your".split()
)
BM25_K1, BM25_B = 1.2, 0.75


def tokens(text: str) -> list[str]:
    terms = []
    for term in TOKEN.findall(text.lower()):
        if term in STOPWORDS or len(term) < 2:  # also drops the "s" of "Sonny's"
            continue
        if len(term) > 3 and term.endswith("s") and not term.endswith("ss"):
            term = term[:-1]
        terms.append(term)
    return terms


def keyword_text(chunk: Chunk) -> str:
    return " ".join([chunk.title, chunk.heading, " ".join(chunk.aliases), chunk.text])


def term_id(term: str) -> int:
    """A stable sparse index for a term (Python's hash() changes per process)."""
    return int.from_bytes(hashlib.blake2b(term.encode("utf-8"), digest_size=4).digest()) >> 1


def document_sparse(terms: list[str], average_length: float) -> tuple[list[int], list[float]]:
    """BM25 term-frequency weights for one document. IDF comes from Qdrant."""
    norm = BM25_K1 * (1 - BM25_B + BM25_B * len(terms) / (average_length or 1.0))
    weights: dict[int, float] = {}
    for term, count in Counter(terms).items():
        index = term_id(term)
        weights[index] = weights.get(index, 0.0) + count * (BM25_K1 + 1) / (count + norm)
    return list(weights), list(weights.values())


def query_sparse(question: str) -> tuple[list[int], list[float]]:
    ids = sorted({term_id(t) for t in tokens(question)})
    return ids, [1.0] * len(ids)


class KeywordIndex:
    """Plain BM25 over a list of chunks, for the in-memory baseline. Rows are positions."""

    def __init__(self, chunks: list[Chunk]):
        postings: dict[str, dict[int, int]] = {}
        lengths = np.zeros(len(chunks), dtype=np.float32)
        for row, chunk in enumerate(chunks):
            terms = tokens(keyword_text(chunk))
            lengths[row] = len(terms)
            for term in terms:
                postings.setdefault(term, {})
                postings[term][row] = postings[term].get(row, 0) + 1
        self.postings = {
            term: (
                np.fromiter(hits.keys(), dtype=np.int32),
                np.fromiter(hits.values(), dtype=np.float32),
            )
            for term, hits in postings.items()
        }
        self.length_ratio = lengths / (lengths.mean() or 1.0)
        self.count = len(chunks)

    def scores(self, question: str) -> np.ndarray:
        scores = np.zeros(self.count, dtype=np.float32)
        for term in set(tokens(question)):
            if term not in self.postings:
                continue
            rows, counts = self.postings[term]
            idf = math.log(1 + (self.count - len(rows) + 0.5) / (len(rows) + 0.5))
            norm = BM25_K1 * (1 - BM25_B + BM25_B * self.length_ratio[rows])
            scores[rows] += idf * counts * (BM25_K1 + 1) / (counts + norm)
        return scores
