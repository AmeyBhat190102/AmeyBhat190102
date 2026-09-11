"""Small text helpers shared by embedding, retrieval and answer formatting."""

from __future__ import annotations

import re

_WORD = re.compile(r"[a-z0-9]+")

# Words that appear in almost every note and question, and so carry close to
# no retrieval signal. Kept short on purpose: an aggressive list starts
# deleting meaning ("no", "not", "how").
STOPWORDS = frozenset(
    """a an and are as at be been but by for from has have how i if in into is it
    its of on or that the their there these they this to was were what when where
    which who will with you your""".split()  # noqa: SIM905 - readable as prose
)


def tokenize(text: str) -> list[str]:
    """Lowercase word tokens, stopwords and single characters removed."""
    return [token for token in _WORD.findall(text.lower()) if len(token) > 1 and token not in STOPWORDS]


_SUFFIXES = ("ingly", "edly", "ing", "ied", "ed", "ly", "s")
_SIBILANT_ENDINGS = ("s", "x", "z", "ch", "sh")
_MIN_STEM_CHARS = 4
_MIN_SHORT_STEM_CHARS = 3  # plurals of three-letter roots: boxes -> box


def stem(token: str) -> str:
    """Crude suffix stripper so 'embedding' and 'embeddings' share a feature.

    Not linguistically correct, and it does not need to be: it only has to map
    inflections of the same word to the same key more often than it collides
    with an unrelated one. Stripping repeats, because a word can carry two
    suffixes at once ('embeddings' -> 'embedding' -> 'embed').
    """
    current = token
    for _ in range(3):
        stripped = _strip_one_suffix(current)
        if stripped == current:
            break
        current = stripped
    # Drop a silent final 'e' so 'retrieve' and 'retrieved' (-> 'retriev')
    # land on the same key.
    if len(current) > _MIN_STEM_CHARS and current.endswith("e"):
        current = current[:-1]
    return current


def _strip_one_suffix(token: str) -> str:
    if token.endswith("ies") and len(token) >= _MIN_STEM_CHARS + 2:
        return token[:-3] + "y"  # queries -> query
    if token.endswith("es") and len(token) - 2 >= _MIN_SHORT_STEM_CHARS:
        # 'boxes' loses both letters, 'stores' only the 's'.
        return token[:-2] if token[:-2].endswith(_SIBILANT_ENDINGS) else token[:-1]

    stripped = next(
        (
            token[: -len(suffix)]
            for suffix in _SUFFIXES
            if token.endswith(suffix) and len(token) - len(suffix) >= _MIN_STEM_CHARS
        ),
        token,
    )
    # A doubled final consonant is an artefact of the suffix just removed:
    # 'embedd' came from 'embedding', and 'embed' is the word.
    if len(stripped) >= _MIN_STEM_CHARS and stripped[-1] == stripped[-2] and stripped[-1] not in "aeiouls":
        stripped = stripped[:-1]
    return stripped


def normalize_whitespace(text: str) -> str:
    """Collapse runs of spaces and blank lines while keeping paragraph breaks."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def condense(text: str, limit: int) -> str:
    """Single-line preview, truncated on a word boundary."""
    flat = " ".join(text.split())
    if len(flat) <= limit:
        return flat
    cut = flat[:limit]
    boundary = cut.rfind(" ")
    return (cut[:boundary] if boundary > limit // 2 else cut).rstrip() + "…"


def split_sentences(text: str) -> list[str]:
    """Rough sentence split used for snippets and note titles.

    Line breaks split too, so a heading or a bullet item is its own unit even
    without terminal punctuation.
    """
    collapsed = re.sub(r"[ \t]+", " ", text.strip())
    parts = re.split(r"(?<=[.!?])\s+|\n+", collapsed)
    return [part.strip() for part in parts if part.strip()]
