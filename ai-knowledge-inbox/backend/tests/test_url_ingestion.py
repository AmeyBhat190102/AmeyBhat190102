"""URL fetching: the request-forgery guard, transport limits, extraction.

These run against a real local HTTP server rather than a mocked transport, so
redirect handling and the streaming byte cap are actually exercised.
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.errors import ContentTooLargeError, FetchError, UnsupportedContentError, ValidationError
from app.services.html_text import html_to_text
from app.services.url_fetcher import fetch_document


@pytest.fixture
def fetch_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ALLOW_PRIVATE_NETWORK_FETCH", "true")
    monkeypatch.setenv("FETCH_TIMEOUT_SECONDS", "5")
    return Settings()


@pytest.fixture
def guarded_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("ALLOW_PRIVATE_NETWORK_FETCH", "false")
    return Settings()


# --- the guard -------------------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/admin",
        "http://169.254.169.254/latest/meta-data/",  # cloud instance metadata
        "http://10.1.2.3/internal",
        "http://192.168.0.1/router",
        "https://localhost/secrets",
    ],
)
async def test_private_addresses_are_refused(url, guarded_settings):
    with pytest.raises(ValidationError, match="private or reserved"):
        await fetch_document(url, guarded_settings)


@pytest.mark.parametrize("url", ["ftp://example.com/file", "file:///etc/passwd", "gopher://example.com"])
async def test_non_http_schemes_are_refused(url, guarded_settings):
    with pytest.raises(ValidationError, match="http"):
        await fetch_document(url, guarded_settings)


async def test_unresolvable_host_is_a_fetch_error(guarded_settings):
    with pytest.raises(FetchError, match="resolve"):
        await fetch_document("https://this-host-does-not-exist.invalid/page", guarded_settings)


# --- transport -------------------------------------------------------------


async def test_html_page_is_fetched_and_cleaned(fixture_site, fetch_settings):
    document = await fetch_document(f"{fixture_site}/article", fetch_settings)
    assert document.title == "Vector Index Tradeoffs"
    assert "efSearch" in document.text
    assert "newsletter" not in document.text  # footer dropped
    assert "tracking" not in document.text  # script dropped


async def test_plain_text_is_supported(fixture_site, fetch_settings):
    document = await fetch_document(f"{fixture_site}/plain", fetch_settings)
    assert "query planning" in document.text


async def test_redirects_are_followed(fixture_site, fetch_settings):
    document = await fetch_document(f"{fixture_site}/redirect", fetch_settings)
    assert document.url.endswith("/article")
    assert "efSearch" in document.text


async def test_redirect_loop_gives_up(fixture_site, fetch_settings, monkeypatch):
    monkeypatch.setenv("FETCH_MAX_REDIRECTS", "2")
    with pytest.raises(FetchError, match="redirects"):
        await fetch_document(f"{fixture_site}/loop", Settings())


async def test_binary_content_type_is_rejected(fixture_site, fetch_settings):
    with pytest.raises(UnsupportedContentError, match="application/pdf"):
        await fetch_document(f"{fixture_site}/binary", fetch_settings)


async def test_oversized_page_is_rejected(fixture_site, monkeypatch):
    monkeypatch.setenv("ALLOW_PRIVATE_NETWORK_FETCH", "true")
    monkeypatch.setenv("MAX_FETCH_BYTES", "20000")
    with pytest.raises(ContentTooLargeError, match="limit"):
        await fetch_document(f"{fixture_site}/huge", Settings())


async def test_upstream_error_is_surfaced_as_502(fixture_site, fetch_settings):
    with pytest.raises(FetchError) as raised:
        await fetch_document(f"{fixture_site}/boom", fetch_settings)
    assert raised.value.status_code == 502
    assert raised.value.details["status_code"] == 500


async def test_page_without_text_is_rejected(fixture_site, fetch_settings):
    with pytest.raises(UnsupportedContentError, match="no readable text"):
        await fetch_document(f"{fixture_site}/empty", fetch_settings)


# --- extraction ------------------------------------------------------------


def test_main_content_is_preferred_over_chrome():
    html = (
        "<html><head><title>T</title></head><body>"
        "<nav>Menu one Menu two</nav>"
        "<main><article><p>" + "The body of the article carries the meaning. " * 10 + "</p></article></main>"
        "<footer>Legal notice</footer></body></html>"
    )
    title, text = html_to_text(html)
    assert title == "T"
    assert "Menu one" not in text and "Legal notice" not in text


def test_entities_are_decoded_and_blocks_separated():
    title, text = html_to_text("<html><body><p>Tom &amp; Jerry</p><p>Second line</p></body></html>")
    assert "Tom & Jerry" in text
    assert "Tom & Jerry\nSecond line" in text or "Tom & Jerry\n\nSecond line" in text


def test_og_title_is_used_when_there_is_no_title_tag():
    title, _ = html_to_text('<html><head><meta property="og:title" content="From OpenGraph"></head><body><p>Body text here</p></body></html>')
    assert title == "From OpenGraph"
