"""HTML to readable text.

Deliberately a heuristic, not a readability engine: strip the tags that never
contain article prose, prefer <main>/<article> when the page marks it, and
keep block-level boundaries as newlines so the chunker still sees paragraphs.

A real deployment should swap this for trafilatura or readability-lxml, which
handle paywalls, comment sections and byline noise far better. This version
earns its place by having no dependencies and no surprises.
"""

from __future__ import annotations

import re
from html.parser import HTMLParser

from app.services.text import condense, normalize_whitespace

# Tags whose contents are never body text.
DROPPED_TAGS = frozenset(
    {"script", "style", "noscript", "svg", "canvas", "iframe", "template",
     "nav", "header", "footer", "aside", "form", "button", "select", "figure"}
)
# Tags that end a line of prose.
BLOCK_TAGS = frozenset(
    {"p", "div", "section", "article", "main", "br", "hr", "li", "ul", "ol",
     "tr", "td", "th", "table", "blockquote", "pre", "h1", "h2", "h3", "h4",
     "h5", "h6", "dt", "dd", "figcaption"}
)
CONTENT_TAGS = frozenset({"article", "main"})

MIN_MAIN_CONTENT_CHARS = 200


class _TextExtractor(HTMLParser):
    """Collects text, optionally only from inside <main>/<article>."""

    def __init__(self, *, only_content_tags: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self._only_content_tags = only_content_tags
        self._drop_depth = 0
        self._content_depth = 0
        self._in_title = False
        self.parts: list[str] = []
        self.title = ""
        self.heading = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in DROPPED_TAGS:
            self._drop_depth += 1
            return
        if tag in CONTENT_TAGS:
            self._content_depth += 1
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attributes = dict(attrs)
            key = (attributes.get("property") or attributes.get("name") or "").lower()
            if key in {"og:title", "twitter:title"} and attributes.get("content") and not self.title:
                self.title = attributes["content"].strip()
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in DROPPED_TAGS:
            self._drop_depth = max(0, self._drop_depth - 1)
            return
        if tag in CONTENT_TAGS:
            self._content_depth = max(0, self._content_depth - 1)
        if tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._in_title and not self.title:
            self.title = data.strip()
            return
        if self._drop_depth:
            return
        if self._only_content_tags and self._content_depth == 0:
            return
        if data.strip():
            if not self.heading:
                self.heading = data.strip()
            self.parts.append(data)

    def text(self) -> str:
        joined = "".join(self.parts)
        # Block tags emit a newline each; collapse the runs they create.
        return normalize_whitespace(re.sub(r"\n{2,}", "\n\n", joined))


def html_to_text(html: str) -> tuple[str, str]:
    """Return (title, text) extracted from an HTML document."""
    full = _TextExtractor()
    full.feed(html)
    full.close()

    focused = _TextExtractor(only_content_tags=True)
    focused.feed(html)
    focused.close()

    # Use the marked-up main content when the page provides enough of it;
    # otherwise fall back to the whole body minus the dropped tags.
    focused_text = focused.text()
    text = focused_text if len(focused_text) >= MIN_MAIN_CONTENT_CHARS else full.text()
    title = full.title or full.heading or ""
    return condense(title, 200), text
