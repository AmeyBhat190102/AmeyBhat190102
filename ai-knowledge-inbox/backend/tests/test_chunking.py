"""Chunking invariants. These are the properties the rest of the pipeline
relies on, so they are asserted rather than eyeballed."""

from __future__ import annotations

import pytest

from app.services.chunking import build_chunks, chunk_spans

PROSE = (
    "Vector databases store embeddings for similarity search. "
    "They trade exact recall for speed once the corpus grows. "
    "Dr. Chen showed that recall degrades past a certain index size.\n\n"
    "HNSW builds a navigable small world graph. It trades memory for query speed. "
    "Recall is tunable at query time, e.g. by raising efSearch. "
    "IVF partitions the vector space into cells instead, which uses less memory.\n\n"
    "Brute force search stays exact. It needs no tuning and no index build step. "
    "Below roughly one hundred thousand vectors it is usually the right answer."
)


def test_chunk_text_is_an_exact_slice_of_the_source():
    """The UI highlights citations by offset, so this must hold exactly."""
    chunks = build_chunks("itm_1", PROSE, target_chars=300, overlap_chars=60)
    assert chunks
    for chunk in chunks:
        assert PROSE[chunk.char_start : chunk.char_end] == chunk.text


def test_every_character_is_covered_by_some_chunk():
    spans = chunk_spans(PROSE, target_chars=300, overlap_chars=60)
    covered: set[int] = set()
    for span in spans:
        covered.update(range(span.start, span.end))
    uncovered = [index for index, char in enumerate(PROSE) if index not in covered and not char.isspace()]
    assert uncovered == []


def test_consecutive_chunks_overlap():
    spans = chunk_spans(PROSE, target_chars=300, overlap_chars=60)
    assert len(spans) > 1
    assert all(spans[i + 1].start < spans[i].end for i in range(len(spans) - 1))


def test_chunks_stay_near_the_target_size():
    spans = chunk_spans(PROSE, target_chars=300, overlap_chars=60)
    # Overlap means a chunk can exceed the target by up to the overlap budget.
    assert all(span.length <= 300 + 60 for span in spans)


def test_abbreviations_do_not_end_a_sentence():
    spans = chunk_spans(PROSE, target_chars=120, overlap_chars=20)
    texts = [PROSE[span.start : span.end] for span in spans]
    assert any("Dr. Chen" in text for text in texts)
    assert not any(text.strip().endswith("Dr.") for text in texts)


def test_ordinals_are_dense_and_ordered():
    chunks = build_chunks("itm_1", PROSE, target_chars=200, overlap_chars=40)
    assert [chunk.ordinal for chunk in chunks] == list(range(len(chunks)))


def test_a_sentence_longer_than_a_chunk_is_split_at_word_boundaries():
    long_sentence = " ".join(["alpha"] * 400) + "."
    spans = chunk_spans(long_sentence, target_chars=200, overlap_chars=40)
    assert len(spans) > 1
    assert all(span.length <= 200 + 40 for span in spans)
    assert "".join(long_sentence[span.start : span.end] for span in spans).replace(" ", "") \
        .startswith("alphaalpha")


def test_short_tail_is_folded_into_the_previous_chunk():
    text = "A" * 290 + ". Tiny tail."
    spans = chunk_spans(text, target_chars=300, overlap_chars=50, min_chars=100)
    assert len(spans) == 1


@pytest.mark.parametrize("text", ["", "   ", "\n\n\t "])
def test_blank_input_produces_no_chunks(text):
    assert chunk_spans(text) == []


def test_overlap_must_be_smaller_than_target():
    with pytest.raises(ValueError, match="overlap_chars"):
        chunk_spans(PROSE, target_chars=100, overlap_chars=100)
