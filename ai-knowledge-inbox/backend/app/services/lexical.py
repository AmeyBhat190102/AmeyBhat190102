"""BM25 keyword scoring over the chunk corpus.

Dense retrieval alone misses exact tokens that carry all the meaning: an
error code, a product name, a person. BM25 is the standard counterweight,
it is cheap to build over a few thousand chunks, and it gives the local
embedding fallback a corpus-aware IDF signal it cannot produce on its own.
"""

from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

from app.services.text import stem, tokenize

K1 = 1.5  # term-frequency saturation
B = 0.75  # length-normalization strength


def _terms(text: str) -> list[str]:
    return [stem(token) for token in tokenize(text)]


class BM25Index:
    """Inverted index over chunk texts. Built once per corpus snapshot."""

    def __init__(self, documents: list[str]) -> None:
        self.document_count = len(documents)
        self.lengths = np.zeros(self.document_count, dtype=np.float32)
        self.postings: dict[str, list[tuple[int, int]]] = defaultdict(list)

        for index, document in enumerate(documents):
            terms = _terms(document)
            self.lengths[index] = len(terms)
            frequencies: dict[str, int] = defaultdict(int)
            for term in terms:
                frequencies[term] += 1
            for term, frequency in frequencies.items():
                self.postings[term].append((index, frequency))

        self.average_length = float(self.lengths.mean()) if self.document_count and self.lengths.sum() else 1.0
        self._idf = {
            term: math.log(1 + (self.document_count - len(posting) + 0.5) / (len(posting) + 0.5))
            for term, posting in self.postings.items()
        }

    def scores(self, query: str) -> np.ndarray:
        """Raw BM25 score per document; zero for documents sharing no term."""
        result = np.zeros(self.document_count, dtype=np.float32)
        if self.document_count == 0:
            return result

        for term in set(_terms(query)):
            posting = self.postings.get(term)
            if not posting:
                continue
            idf = self._idf[term]
            for document_index, frequency in posting:
                length_ratio = self.lengths[document_index] / (self.average_length or 1.0)
                denominator = frequency + K1 * (1 - B + B * length_ratio)
                result[document_index] += idf * (frequency * (K1 + 1)) / (denominator or 1.0)
        return result


def saturate(scores: np.ndarray, midpoint: float = 8.0) -> np.ndarray:
    """Map unbounded BM25 scores into [0, 1).

    Dividing by the batch maximum would make a score depend on the other
    results in the same request, which breaks a fixed relevance threshold.
    This transform is absolute: `midpoint` is the score that maps to 0.5.
    """
    return scores / (scores + midpoint)
