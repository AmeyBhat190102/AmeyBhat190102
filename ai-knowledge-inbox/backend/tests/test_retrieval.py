"""Embedding, lexical scoring, hybrid search and context selection."""

from __future__ import annotations

import numpy as np
import pytest

from app.models import EmbeddedChunk, ScoredChunk
from app.repositories import chunks as chunk_repo
from app.repositories import items as item_repo
from app.services.chunking import build_chunks
from app.services.embeddings import LocalHashingEmbeddings
from app.services.lexical import BM25Index, saturate
from app.services.rag import select_passages
from app.services.vector_store import VectorStore

CORPUS = {
    "HNSW notes": "HNSW builds a hierarchical navigable small world graph. Recall is tuned with the efSearch parameter, trading latency for accuracy.",
    "Chunking notes": "Chunking splits a document into overlapping passages before embedding. Sentence aligned chunks avoid cutting a thought in half.",
    "Roast recipe": "Roast the vegetables at two hundred degrees for forty minutes. Toss them with olive oil, salt and rosemary first.",
    "Postgres ops": "Run VACUUM ANALYZE after a bulk load so the planner has fresh statistics. Connection pooling with pgbouncer cuts connection cost.",
}


@pytest.fixture
def embedder() -> LocalHashingEmbeddings:
    return LocalHashingEmbeddings(1024)


@pytest.fixture
async def populated_store(database, embedder) -> VectorStore:
    for title, body in CORPUS.items():
        item = item_repo.create(database, source_type="note", title=title, source_url=None, raw_content=body)
        chunks = build_chunks(item.id, body, target_chars=400, overlap_chars=80)
        vectors = await embedder.embed_documents([chunk.text for chunk in chunks])
        chunk_repo.replace_for_item(
            database,
            item.id,
            [
                EmbeddedChunk(chunk=chunk, embedding=vector, embedding_model=embedder.model)
                for chunk, vector in zip(chunks, vectors, strict=True)
            ],
        )
        item_repo.mark_ready(database, item.id, title=title, raw_content=body, chunk_count=len(chunks))
    store = VectorStore(database)
    store.invalidate()
    return store


# --- embeddings ------------------------------------------------------------


async def test_local_embeddings_are_deterministic(embedder):
    assert embedder.embed_one("the same sentence") == embedder.embed_one("the same sentence")


async def test_local_embeddings_are_unit_length(embedder):
    vector = embedder.embed_one("vector search over saved notes")
    assert pytest.approx(1.0, abs=1e-6) == sum(value * value for value in vector)


async def test_embedding_of_blank_text_is_the_zero_vector(embedder):
    assert set(embedder.embed_one("   \n ")) == {0.0}


async def test_stemming_matches_singular_and_plural(embedder):
    singular = np.array(embedder.embed_one("embedding index"))
    plural = np.array(embedder.embed_one("embeddings indexes"))
    assert float(singular @ plural) > 0.9


# --- lexical ---------------------------------------------------------------


def test_bm25_ranks_the_document_containing_the_query_term():
    index = BM25Index(list(CORPUS.values()))
    scores = index.scores("pgbouncer pooling")
    assert int(np.argmax(scores)) == list(CORPUS).index("Postgres ops")


def test_bm25_scores_are_zero_without_shared_terms():
    index = BM25Index(list(CORPUS.values()))
    assert float(index.scores("xylophone marmalade").max()) == 0.0


def test_saturation_maps_scores_into_the_unit_interval():
    scores = saturate(np.array([0.0, 8.0, 1_000.0], dtype=np.float32))
    assert scores[0] == 0.0
    assert pytest.approx(0.5, abs=1e-6) == float(scores[1])
    assert scores[2] < 1.0


# --- hybrid search ---------------------------------------------------------


@pytest.mark.parametrize(
    ("question", "expected_title"),
    [
        ("how do I tune recall in HNSW?", "HNSW notes"),
        ("why should chunks overlap", "Chunking notes"),
        ("what temperature do the vegetables need", "Roast recipe"),
        ("does pgbouncer help with connection cost", "Postgres ops"),
    ],
)
async def test_search_returns_the_right_note_first(populated_store, embedder, question, expected_title):
    hits, _ = populated_store.search(
        query_vector=await embedder.embed_query(question), query_text=question, limit=3
    )
    assert hits[0].item_title == expected_title


async def test_unrelated_question_scores_below_the_relevance_floor(populated_store, embedder, settings):
    question = "quarterly revenue for the Lisbon office"
    hits, _ = populated_store.search(
        query_vector=await embedder.embed_query(question), query_text=question, limit=5
    )
    assert all(hit.score < settings.retrieval_min_score for hit in hits)


async def test_search_can_be_restricted_to_chosen_items(populated_store, embedder, database):
    recipe = next(item for item in item_repo.list_items(database, limit=10)[0] if item.title == "Roast recipe")
    hits, searched = populated_store.search(
        query_vector=await embedder.embed_query("recall tuning"),
        query_text="recall tuning",
        limit=5,
        item_ids=[recipe.id],
    )
    assert searched == recipe.chunk_count
    assert {hit.item_id for hit in hits} == {recipe.id}


async def test_empty_index_returns_no_hits(database, embedder):
    store = VectorStore(database)
    hits, searched = store.search(query_vector=await embedder.embed_query("anything"), query_text="anything", limit=5)
    assert (hits, searched) == ([], 0)


async def test_index_refreshes_after_invalidation(populated_store, embedder, database):
    before = populated_store.size
    item = item_repo.create(database, source_type="note", title="New", source_url=None, raw_content="Kafka retention policy.")
    chunks = build_chunks(item.id, "Kafka retention policy is set per topic.", target_chars=400, overlap_chars=80)
    vectors = await embedder.embed_documents([chunk.text for chunk in chunks])
    chunk_repo.replace_for_item(
        database,
        item.id,
        [EmbeddedChunk(chunk=c, embedding=v, embedding_model=embedder.model) for c, v in zip(chunks, vectors, strict=True)],
    )
    item_repo.mark_ready(database, item.id, title="New", raw_content="Kafka retention policy is set per topic.", chunk_count=len(chunks))

    assert populated_store.size == before, "a stale snapshot should be served until invalidation"
    populated_store.invalidate()
    assert populated_store.size == before + len(chunks)


async def test_dimension_mismatch_is_reported_clearly(populated_store):
    with pytest.raises(ValueError, match="re-ingest"):
        populated_store.search(query_vector=[0.1, 0.2, 0.3], query_text="mismatch", limit=3)


# --- context selection -----------------------------------------------------


def _hit(item_id: str, score: float) -> ScoredChunk:
    return ScoredChunk(
        chunk_id=f"chk_{item_id}_{score}",
        item_id=item_id,
        item_title=item_id,
        item_source_type="note",
        item_source_url=None,
        ordinal=0,
        text="text",
        dense_score=score,
        lexical_score=score,
        score=score,
    )


def test_selection_drops_hits_below_the_floor():
    selected = select_passages([_hit("a", 0.4), _hit("b", 0.05)], top_k=5, min_score=0.1, max_per_item=3)
    assert [hit.item_id for hit in selected] == ["a"]


def test_selection_caps_chunks_from_one_item():
    candidates = [_hit("a", 0.9), _hit("a", 0.8), _hit("a", 0.7), _hit("a", 0.6), _hit("b", 0.5)]
    selected = select_passages(candidates, top_k=5, min_score=0.1, max_per_item=2)
    assert [hit.item_id for hit in selected] == ["a", "a", "b"]


def test_selection_respects_top_k():
    candidates = [_hit(f"item{index}", 0.9 - index / 100) for index in range(10)]
    assert len(select_passages(candidates, top_k=3, min_score=0.1, max_per_item=3)) == 3
