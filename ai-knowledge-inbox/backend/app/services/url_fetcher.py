"""Server-side URL fetching.

Fetching a user-supplied URL from the server is a request-forgery primitive:
without a guard, "http://169.254.169.254/latest/meta-data/" turns this
endpoint into a cloud-credential reader. So every hop is checked against
resolved IP addresses, redirects are followed manually rather than by httpx,
and the body is streamed with a hard byte cap instead of being read whole.

Known limitation: the address is validated at resolution time, so a DNS
rebind between the check and the connection is not covered. Closing that
needs a transport that dials the already-validated IP with an explicit Host
header; it is the right next step if this ever becomes multi-tenant.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

from app.config import Settings
from app.errors import ContentTooLargeError, FetchError, UnsupportedContentError, ValidationError
from app.logging_config import get_logger
from app.services.html_text import html_to_text
from app.services.text import condense, normalize_whitespace

logger = get_logger(__name__)

TEXTUAL_CONTENT_TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown")
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")


@dataclass(slots=True)
class FetchedDocument:
    url: str
    title: str
    text: str
    content_type: str
    bytes_read: int


def _is_blocked_address(raw_address: str) -> bool:
    address = ipaddress.ip_address(raw_address)
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
        or address.is_unspecified
    )


async def _resolve(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    try:
        records = await loop.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise FetchError(f"could not resolve host {host!r}", details={"host": host}) from exc
    return [record[4][0] for record in records]


async def assert_fetchable(url: str, *, allow_private: bool) -> None:
    """Reject non-HTTP schemes and hosts that resolve inside the network."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValidationError("only http and https URLs can be fetched", details={"url": url})
    if not parsed.hostname:
        raise ValidationError("url is missing a hostname", details={"url": url})
    if allow_private:
        return

    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    for address in await _resolve(parsed.hostname, port):
        if _is_blocked_address(address):
            logger.warning(
                "blocked fetch of private address",
                extra={"url": url, "host": parsed.hostname, "resolved": address},
            )
            raise ValidationError(
                "that URL resolves to a private or reserved address and will not be fetched",
                details={"url": url, "resolved_address": address},
            )


async def _read_capped(response: httpx.Response, limit: int, url: str) -> bytes:
    chunks: list[bytes] = []
    total = 0
    async for piece in response.aiter_bytes():
        total += len(piece)
        if total > limit:
            raise ContentTooLargeError(
                f"page exceeds the {limit} byte limit",
                details={"url": url, "limit_bytes": limit},
            )
        chunks.append(piece)
    return b"".join(chunks)


async def fetch_document(url: str, settings: Settings) -> FetchedDocument:
    """Fetch a URL and return its extracted text, following redirects by hand."""
    current = url
    async with httpx.AsyncClient(
        timeout=settings.fetch_timeout_seconds,
        follow_redirects=False,
        headers={"User-Agent": settings.user_agent, "Accept": "text/html,text/plain;q=0.9,*/*;q=0.1"},
    ) as client:
        for hop in range(settings.fetch_max_redirects + 1):
            await assert_fetchable(current, allow_private=settings.allow_private_network_fetch)
            try:
                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        location = response.headers.get("location")
                        if not location:
                            raise FetchError("redirect response had no Location header", details={"url": current})
                        current = str(httpx.URL(current).join(location))
                        logger.info("following redirect", extra={"hop": hop + 1, "to": current})
                        continue

                    if response.status_code >= 400:
                        raise FetchError(
                            f"upstream returned HTTP {response.status_code}",
                            details={"url": current, "status_code": response.status_code},
                        )

                    content_type = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
                    if content_type and not content_type.startswith(TEXTUAL_CONTENT_TYPES):
                        raise UnsupportedContentError(
                            f"{content_type or 'unknown content type'} cannot be indexed; "
                            "only HTML and plain text are supported",
                            details={"url": current, "content_type": content_type},
                        )

                    body = await _read_capped(response, settings.max_fetch_bytes, current)
                    encoding = response.encoding or "utf-8"
            except httpx.TimeoutException as exc:
                raise FetchError(
                    f"timed out after {settings.fetch_timeout_seconds}s",
                    details={"url": current},
                ) from exc
            except httpx.HTTPError as exc:
                raise FetchError(f"could not fetch the URL: {exc}", details={"url": current}) from exc

            decoded = body.decode(encoding, errors="replace")
            if content_type.startswith(HTML_CONTENT_TYPES) or (not content_type and "<html" in decoded[:2000].lower()):
                title, text = html_to_text(decoded)
            else:
                title, text = "", normalize_whitespace(decoded)

            if not text.strip():
                raise UnsupportedContentError(
                    "no readable text was found at that URL",
                    details={"url": current, "content_type": content_type},
                )

            logger.info(
                "fetched url",
                extra={
                    "url": current,
                    "content_type": content_type,
                    "bytes": len(body),
                    "extracted_chars": len(text),
                },
            )
            return FetchedDocument(
                url=current,
                title=title or condense(text, 80),
                text=text,
                content_type=content_type or "text/html",
                bytes_read=len(body),
            )

    raise FetchError(
        f"gave up after {settings.fetch_max_redirects} redirects",
        details={"url": url, "max_redirects": settings.fetch_max_redirects},
    )
