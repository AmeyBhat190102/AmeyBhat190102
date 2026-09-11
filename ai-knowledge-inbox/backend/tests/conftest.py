"""Shared fixtures.

Each test gets its own SQLite file and a freshly composed app, so nothing
leaks between tests through the module-level caches the app uses for the
database, the search index and the providers.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings, reset_settings_cache
from app.db import Database, reset_database
from app.services.answering import reset_answerer_cache
from app.services.embeddings import reset_embedding_provider_cache
from app.services.vector_store import reset_vector_store

INGEST_TIMEOUT_SECONDS = 15.0


@pytest.fixture
def settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("EMBEDDING_PROVIDER", "local")
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    monkeypatch.setenv("ALLOW_PRIVATE_NETWORK_FETCH", "true")
    monkeypatch.setenv("CHUNK_TARGET_CHARS", "400")
    monkeypatch.setenv("CHUNK_OVERLAP_CHARS", "80")

    reset_settings_cache()
    reset_vector_store()
    reset_embedding_provider_cache()
    reset_answerer_cache()
    yield get_settings()
    reset_settings_cache()
    reset_vector_store()
    reset_embedding_provider_cache()
    reset_answerer_cache()


@pytest.fixture
def database(settings: Settings) -> Database:
    return reset_database(settings.database_path)


@pytest.fixture
def client(database: Database) -> Iterator[TestClient]:
    # Imported here so the app is built after the environment is patched.
    from app.main import create_app

    with TestClient(create_app()) as test_client:
        yield test_client


def wait_for_status(client: TestClient, item_id: str, *, expected: str = "ready") -> dict:
    """Poll an item until ingestion settles. Returns the final item."""
    deadline = time.monotonic() + INGEST_TIMEOUT_SECONDS
    last: dict = {}
    while time.monotonic() < deadline:
        response = client.get(f"/items/{item_id}")
        response.raise_for_status()
        last = response.json()
        if last["status"] in ("ready", "failed"):
            break
        time.sleep(0.02)
    assert last.get("status") == expected, f"item settled as {last.get('status')!r}: {last.get('error_message')!r}"
    return last


def ingest_note(client: TestClient, content: str, title: str | None = None) -> dict:
    payload: dict = {"type": "note", "content": content}
    if title:
        payload["title"] = title
    response = client.post("/ingest", json=payload)
    assert response.status_code == 202, response.text
    return wait_for_status(client, response.json()["id"])


# --------------------------------------------------------------------------
# A real HTTP server for the URL ingestion tests. Mocking httpx would skip
# the redirect handling and the streaming byte cap, which are the parts most
# likely to break.
# --------------------------------------------------------------------------

ARTICLE_HTML = """<!doctype html><html><head><title>Vector Index Tradeoffs</title>
<script>var tracking = 1;</script><style>body{color:#111}</style></head>
<body><nav>Home | Archive</nav>
<main><article>
<h1>Vector index tradeoffs</h1>
<p>HNSW gives high recall with low latency but holds the whole graph in memory. The efSearch parameter trades latency for recall at query time.</p>
<p>IVF-Flat partitions vectors into cells and scans only the nearest ones. It uses far less memory than HNSW and is a better fit when the index does not fit in RAM.</p>
<p>Brute force search stays exact and needs no tuning, which is why it is the right answer below roughly one hundred thousand vectors.</p>
</article></main>
<footer>Sign up for the newsletter</footer></body></html>"""


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        routes = {
            "/article": (200, "text/html; charset=utf-8", ARTICLE_HTML.encode()),
            "/plain": (200, "text/plain; charset=utf-8", b"A plain text note about database indexes and query planning."),
            "/binary": (200, "application/pdf", b"%PDF-1.4 binary bytes"),
            "/huge": (200, "text/html; charset=utf-8", b"<html><body><p>" + b"padding " * 500_000 + b"</p></body></html>"),
            "/empty": (200, "text/html; charset=utf-8", b"<html><body><script>only()</script></body></html>"),
            "/boom": (500, "text/plain; charset=utf-8", b"upstream exploded"),
        }
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/article")
            self.end_headers()
            return
        if self.path == "/loop":
            self.send_response(302)
            self.send_header("Location", "/loop")
            self.end_headers()
            return

        status, content_type, body = routes.get(self.path, (404, "text/plain", b"not found"))
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        """Silence the default stderr access log."""


@pytest.fixture(scope="session")
def fixture_site() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
