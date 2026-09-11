"""The HTTP contract: status codes, response shapes, error bodies."""

from __future__ import annotations

import pytest

from tests.conftest import ingest_note, wait_for_status

NOTES = {
    "Retrieval notes": (
        "Hybrid retrieval blends a dense vector score with BM25 keyword scoring. "
        "The dense half catches paraphrases, and the keyword half catches exact identifiers "
        "such as error codes and product names that embeddings tend to blur together."
    ),
    "Deploy runbook": (
        "Deploys run from the main branch only. Roll back by re-running the previous image tag; "
        "there is no database migration step in the rollback path, so schema changes must be "
        "backwards compatible for one release."
    ),
}


@pytest.fixture
def stocked_client(client):
    for title, body in NOTES.items():
        ingest_note(client, body, title=title)
    return client


# --- ingest ----------------------------------------------------------------


def test_ingesting_a_note_returns_202_and_becomes_ready(client):
    response = client.post("/ingest", json={"type": "note", "content": NOTES["Deploy runbook"]})
    assert response.status_code == 202

    created = response.json()
    assert created["status"] == "pending"
    assert created["source_type"] == "note"
    assert created["title"] == "Deploys run from the main branch only."

    item = wait_for_status(client, created["id"])
    assert item["chunk_count"] >= 1
    assert item["char_count"] == len(NOTES["Deploy runbook"])
    assert item["error_message"] is None


def test_explicit_title_is_kept(client):
    item = ingest_note(client, "Body text for the note.", title="My title")
    assert item["title"] == "My title"


def test_ingesting_a_url_fetches_and_indexes_it(client, fixture_site):
    response = client.post("/ingest", json={"type": "url", "url": f"{fixture_site}/article"})
    assert response.status_code == 202

    item = wait_for_status(client, response.json()["id"])
    assert item["title"] == "Vector Index Tradeoffs"
    assert item["source_url"].endswith("/article")
    assert "efSearch" in item["raw_content"]


def test_a_failed_url_is_recorded_on_the_item_not_lost(client, fixture_site):
    response = client.post("/ingest", json={"type": "url", "url": f"{fixture_site}/boom"})
    assert response.status_code == 202

    item = wait_for_status(client, response.json()["id"], expected="failed")
    assert "500" in item["error_message"]
    assert item["chunk_count"] == 0


@pytest.mark.parametrize(
    ("payload", "expected_field"),
    [
        ({"type": "note"}, "content"),
        ({"type": "note", "content": "   "}, "content"),
        ({"type": "url"}, "url"),
        ({"type": "url", "url": "ftp://example.com"}, "url"),
        ({"type": "webpage", "url": "https://example.com"}, "type"),
        ({"type": "note", "content": "ok", "unexpected": 1}, "unexpected"),
    ],
)
def test_invalid_ingest_payloads_return_422_naming_the_field(client, payload, expected_field):
    response = client.post("/ingest", json=payload)
    assert response.status_code == 422

    body = response.json()["error"]
    assert body["code"] == "validation_error"
    # The offending field is named either by its location or, for a bad
    # discriminator value, in the message pydantic produces for it.
    assert any(
        expected_field in field["field"] or expected_field in field["message"]
        for field in body["details"]["fields"]
    )


def test_validation_errors_are_scoped_to_the_matching_variant(client):
    """A bad note must not report errors about the URL variant it never was."""
    fields = client.post("/ingest", json={"type": "note", "content": ""}).json()["error"]["details"]["fields"]
    assert [field["field"] for field in fields] == ["note.content"]


def test_note_over_the_size_limit_is_refused(client):
    response = client.post("/ingest", json={"type": "note", "content": "x" * 200_001})
    assert response.status_code == 422


# --- items -----------------------------------------------------------------


def test_items_are_listed_newest_first_with_totals(stocked_client):
    body = stocked_client.get("/items").json()
    assert body["total"] == 2
    assert [item["title"] for item in body["items"]] == ["Deploy runbook", "Retrieval notes"]
    assert body["limit"] == 50 and body["offset"] == 0


def test_item_list_paginates(stocked_client):
    first = stocked_client.get("/items", params={"limit": 1, "offset": 0}).json()
    second = stocked_client.get("/items", params={"limit": 1, "offset": 1}).json()
    assert len(first["items"]) == len(second["items"]) == 1
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert first["total"] == second["total"] == 2


def test_item_list_filters_by_status_and_type(stocked_client):
    assert stocked_client.get("/items", params={"status": "ready"}).json()["total"] == 2
    assert stocked_client.get("/items", params={"status": "failed"}).json()["total"] == 0
    assert stocked_client.get("/items", params={"source_type": "url"}).json()["total"] == 0


def test_item_detail_includes_full_content(stocked_client):
    listed = stocked_client.get("/items").json()["items"][0]
    detail = stocked_client.get(f"/items/{listed['id']}").json()
    assert detail["raw_content"] == NOTES["Deploy runbook"]
    assert detail["preview"].startswith("Deploys run from the main branch")


def test_unknown_item_returns_a_404_error_body(client):
    response = client.get("/items/itm_missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_deleting_an_item_removes_it_from_search(stocked_client):
    listed = stocked_client.get("/items").json()["items"]
    runbook = next(item for item in listed if item["title"] == "Deploy runbook")

    assert stocked_client.delete(f"/items/{runbook['id']}").status_code == 204
    assert stocked_client.get(f"/items/{runbook['id']}").status_code == 404
    assert stocked_client.delete(f"/items/{runbook['id']}").status_code == 404

    answer = stocked_client.post("/query", json={"question": "how do I roll back a deploy?"}).json()
    assert runbook["id"] not in [citation["item_id"] for citation in answer["citations"]]


def test_invalid_pagination_is_rejected(client):
    assert client.get("/items", params={"limit": 0}).status_code == 422
    assert client.get("/items", params={"limit": 1000}).status_code == 422
    assert client.get("/items", params={"offset": -1}).status_code == 422


# --- query -----------------------------------------------------------------


def test_query_answers_from_saved_content_with_citations(stocked_client):
    response = stocked_client.post("/query", json={"question": "how do I roll back a deploy?"})
    assert response.status_code == 200

    body = response.json()
    assert body["grounded"] is True
    assert body["citations"], "a grounded answer must cite something"
    assert body["chunks_searched"] >= 2
    assert body["latency_ms"] >= 0

    first = body["citations"][0]
    assert first["title"] == "Deploy runbook"
    assert first["marker"] == 1
    assert first["snippet"]
    assert 0.0 <= first["score"] <= 1.0
    assert [citation["marker"] for citation in body["citations"]] == list(range(1, len(body["citations"]) + 1))


def test_answer_only_cites_passages_it_was_given(stocked_client):
    body = stocked_client.post("/query", json={"question": "what does BM25 catch that embeddings miss?"}).json()
    markers = {citation["marker"] for citation in body["citations"]}
    cited_in_text = {int(part.split("]")[0]) for part in body["answer"].split("[")[1:] if part.split("]")[0].isdigit()}
    assert cited_in_text <= markers


def test_question_about_missing_content_is_not_answered(stocked_client):
    body = stocked_client.post("/query", json={"question": "what is the office holiday policy in Lisbon?"}).json()
    assert body["grounded"] is False
    assert body["citations"] == []
    assert "do not cover" in body["answer"]


def test_query_against_an_empty_inbox_explains_itself(client):
    body = client.post("/query", json={"question": "anything at all?"}).json()
    assert body["grounded"] is False
    assert body["chunks_searched"] == 0
    assert "Nothing has been saved" in body["answer"]


def test_query_can_be_restricted_to_one_item(stocked_client):
    listed = stocked_client.get("/items").json()["items"]
    retrieval_note = next(item for item in listed if item["title"] == "Retrieval notes")

    body = stocked_client.post(
        "/query",
        json={"question": "how do I roll back a deploy?", "item_ids": [retrieval_note["id"]]},
    ).json()
    assert all(citation["item_id"] == retrieval_note["id"] for citation in body["citations"])


def test_unknown_item_ids_are_rejected(stocked_client):
    response = stocked_client.post("/query", json={"question": "anything", "item_ids": ["itm_nope"]})
    assert response.status_code == 400

    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"]["unknown_item_ids"] == ["itm_nope"]


def test_top_k_limits_the_number_of_citations(stocked_client):
    body = stocked_client.post("/query", json={"question": "retrieval and deploys", "top_k": 1}).json()
    assert len(body["citations"]) <= 1


@pytest.mark.parametrize(
    "payload",
    [{"question": "hi"}, {"question": "   "}, {"question": "valid question", "top_k": 0}, {"question": "valid question", "top_k": 99}, {}],
)
def test_invalid_query_payloads_return_422(stocked_client, payload):
    assert stocked_client.post("/query", json=payload).status_code == 422


# --- ops -------------------------------------------------------------------


def test_health_reports_counts_and_active_providers(stocked_client):
    body = stocked_client.get("/health").json()
    assert body["status"] == "ok"
    assert body["items"] == 2
    assert body["chunks"] >= 2
    assert body["providers"]["embeddings"] == "local"
    assert body["providers"]["llm"] == "local"


def test_every_response_carries_a_request_id(client):
    assert client.get("/health").headers["X-Request-ID"].startswith("req_")


def test_an_inbound_request_id_is_preserved(client):
    response = client.get("/health", headers={"X-Request-ID": "trace-abc-123"})
    assert response.headers["X-Request-ID"] == "trace-abc-123"
