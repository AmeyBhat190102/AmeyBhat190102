"""Structure-aware chunking.

Strategy: pack whole sentences (grouped by paragraph) into ~900-character
chunks with ~150 characters of sentence-aligned overlap.

Why not fixed-size windows: notes and articles are prose, and a fixed window
routinely cuts a sentence in half. Half a sentence embeds into a vector that
means something slightly different from either neighbour, which is exactly
the kind of quiet retrieval failure that is hard to debug later.

Why overlap: a claim and the sentence that qualifies it often straddle a
boundary. Overlap makes the join retrievable from either side; the cost is
~15% more vectors, which is cheap at this scale.

Invariant: a chunk's text is always `source[char_start:char_end]`, so the UI
can highlight a citation in the original and offsets survive re-indexing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models import Chunk
from app.repositories.chunks import new_chunk_id

# A sentence boundary candidate: terminal punctuation (plus an optional closing
# quote or bracket) followed by whitespace. Candidates preceded by a known
# abbreviation are rejected in `_sentence_spans`, so "Dr. Chen" stays intact.
_BOUNDARY_CANDIDATE = re.compile(r"[.!?][\"')\]]?(\s+)")
_TRAILING_WORD = re.compile(r"([A-Za-z]+)\.?[\"')\]]?$")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
# A bare line break also ends a unit of thought: note headings and bullet
# list items rarely carry terminal punctuation.
_LINE_BREAK = re.compile(r"\n+")

_ABBREVIATIONS = frozenset(
    {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "st", "vs", "etc", "eg",
        "ie", "fig", "no", "inc", "ltd", "co", "approx", "al", "cf", "resp",
    }
)


@dataclass(slots=True)
class TextSpan:
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start


def _paragraph_spans(text: str) -> list[TextSpan]:
    spans: list[TextSpan] = []
    cursor = 0
    for match in _PARAGRAPH_BREAK.finditer(text):
        if match.start() > cursor:
            spans.append(TextSpan(cursor, match.start()))
        cursor = match.end()
    if cursor < len(text):
        spans.append(TextSpan(cursor, len(text)))
    return [span for span in spans if text[span.start : span.end].strip()]


def _split_oversized(text: str, span: TextSpan, limit: int) -> list[TextSpan]:
    """Break a single sentence that is longer than one chunk, at word boundaries."""
    pieces: list[TextSpan] = []
    cursor = span.start
    while span.end - cursor > limit:
        window_end = cursor + limit
        boundary = text.rfind(" ", cursor + limit // 2, window_end)
        cut = boundary if boundary != -1 else window_end
        pieces.append(TextSpan(cursor, cut))
        cursor = cut + 1 if boundary != -1 else cut
    if cursor < span.end:
        pieces.append(TextSpan(cursor, span.end))
    return pieces


def _boundaries(text: str, paragraph: TextSpan) -> list[tuple[int, int]]:
    """Candidate split points inside a paragraph, as (cut_at, resume_at)."""
    body = text[paragraph.start : paragraph.end]
    found: list[tuple[int, int]] = []

    for match in _BOUNDARY_CANDIDATE.finditer(body):
        cut = paragraph.start + match.end() - len(match.group(1))
        found.append((cut, paragraph.start + match.end()))
    for match in _LINE_BREAK.finditer(body):
        found.append((paragraph.start + match.start(), paragraph.start + match.end()))

    return sorted(set(found))


def _sentence_spans(text: str, paragraph: TextSpan) -> list[TextSpan]:
    """Split one paragraph into sentence spans, in absolute offsets."""
    spans: list[TextSpan] = []
    sentence_start = paragraph.start

    for cut, resume in _boundaries(text, paragraph):
        if cut <= sentence_start:
            continue
        preceding = text[sentence_start:cut]
        trailing_word = _TRAILING_WORD.search(preceding.rstrip())
        # Only punctuation boundaries can be abbreviations; a line break ends
        # the line regardless of what precedes it.
        if text[cut - 1] in ".!?\"')]" and trailing_word and trailing_word.group(1).lower() in _ABBREVIATIONS:
            continue
        spans.append(TextSpan(sentence_start, cut))
        sentence_start = resume

    if sentence_start < paragraph.end:
        spans.append(TextSpan(sentence_start, paragraph.end))
    return [span for span in spans if text[span.start : span.end].strip()]


def _atom_spans(text: str, target_chars: int) -> list[TextSpan]:
    """Smallest units we are willing to place in a chunk: sentences, or word
    runs when a single sentence is itself larger than a chunk."""
    atoms: list[TextSpan] = []
    for paragraph in _paragraph_spans(text):
        for sentence in _sentence_spans(text, paragraph):
            if sentence.length > target_chars:
                atoms.extend(_split_oversized(text, sentence, target_chars))
            else:
                atoms.append(sentence)
    return atoms


def chunk_spans(
    text: str,
    *,
    target_chars: int = 900,
    overlap_chars: int = 150,
    min_chars: int = 120,
) -> list[TextSpan]:
    """Group sentences into overlapping chunks and return their offsets."""
    if target_chars <= 0:
        raise ValueError("target_chars must be positive")
    if overlap_chars >= target_chars:
        raise ValueError("overlap_chars must be smaller than target_chars")
    if not text.strip():
        return []

    atoms = _atom_spans(text, target_chars)
    if not atoms:
        return []

    chunks: list[TextSpan] = []
    index = 0
    while index < len(atoms):
        start_index = index
        end_index = index
        # Always take at least one atom, otherwise an oversized atom stalls.
        while end_index < len(atoms):
            candidate_length = atoms[end_index].end - atoms[start_index].start
            if end_index > start_index and candidate_length > target_chars:
                break
            end_index += 1

        chunks.append(TextSpan(atoms[start_index].start, atoms[end_index - 1].end))

        if end_index >= len(atoms):
            break

        # Step back over trailing sentences worth up to `overlap_chars`, but
        # never so far that the next chunk repeats this one entirely.
        overlap_index = end_index
        carried = 0
        while overlap_index - 1 > start_index:
            atom = atoms[overlap_index - 1]
            if carried + atom.length > overlap_chars:
                break
            carried += atom.length
            overlap_index -= 1
        index = overlap_index if overlap_index > start_index else end_index

    # A stub tail chunk retrieves poorly on its own; fold it into its neighbour.
    if len(chunks) > 1 and chunks[-1].length < min_chars:
        chunks[-2] = TextSpan(chunks[-2].start, chunks[-1].end)
        chunks.pop()

    return chunks


def build_chunks(
    item_id: str,
    text: str,
    *,
    target_chars: int = 900,
    overlap_chars: int = 150,
    min_chars: int = 120,
) -> list[Chunk]:
    """Chunk `text` into persistable Chunk objects for one item."""
    spans = chunk_spans(
        text,
        target_chars=target_chars,
        overlap_chars=overlap_chars,
        min_chars=min_chars,
    )
    return [
        Chunk(
            id=new_chunk_id(),
            item_id=item_id,
            ordinal=ordinal,
            text=text[span.start : span.end],
            char_start=span.start,
            char_end=span.end,
        )
        for ordinal, span in enumerate(spans)
    ]
