"""Turning retrieved passages into a cited answer.

Three implementations behind one `Answerer` interface:

* OpenAIAnswerer / AnthropicAnswerer - real generation; they share the prompt
  and differ only in wire format, so the shared parts live in RemoteAnswerer.
* ExtractiveAnswerer - no network. It quotes the sentences from the retrieved
  passages that best match the question. The answer is blunt rather than
  fluent, but it is always grounded, it costs nothing, and it makes the whole
  pipeline demonstrable and testable without an API key.

Citations are the point of the prompt: the model is told to mark every claim
with the [n] of the passage it came from, and to refuse rather than reach
beyond the context.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Any

from app.config import Settings, get_settings
from app.errors import ProviderError
from app.logging_config import get_logger
from app.models import ScoredChunk
from app.services.remote import post_json
from app.services.text import condense, split_sentences, stem, tokenize

logger = get_logger(__name__)

MAX_ANSWER_TOKENS = 700
ANSWER_TEMPERATURE = 0.1

SYSTEM_PROMPT = """You answer questions using only the numbered passages provided by the user.

Rules:
- Use only facts present in the passages. Never use outside knowledge.
- Cite every claim with the passage number in square brackets, like [2].
- A sentence drawing on two passages ends with [1][3].
- If the passages do not answer the question, reply exactly: The saved notes do not cover this.
- Be direct. Three sentences or fewer unless the question needs a list.
- Do not mention "passages", "context" or "documents" in the answer; just answer."""

NO_ANSWER_TEXT = "The saved notes do not cover this."


def render_context(passages: list[ScoredChunk]) -> str:
    """Number the passages so the model has something concrete to cite."""
    blocks = []
    for marker, passage in enumerate(passages, start=1):
        source = passage.item_source_url or passage.item_title
        blocks.append(f"[{marker}] (source: {source})\n{passage.text.strip()}")
    return "\n\n".join(blocks)


def build_user_prompt(question: str, passages: list[ScoredChunk]) -> str:
    return f"Passages:\n\n{render_context(passages)}\n\nQuestion: {question}"


class Answerer(ABC):
    name: str
    model: str

    @abstractmethod
    async def answer(self, question: str, passages: list[ScoredChunk]) -> str: ...


class RemoteAnswerer(Answerer):
    """Shared prompt building and logging for hosted chat models."""

    def __init__(self, *, url: str, headers: dict[str, str], model: str, timeout: float) -> None:
        self._url = url
        self._headers = headers
        self.model = model
        self._timeout = timeout

    @abstractmethod
    def build_payload(self, system: str, user: str) -> dict[str, Any]: ...

    @abstractmethod
    def extract_text(self, body: dict[str, Any]) -> str: ...

    async def answer(self, question: str, passages: list[ScoredChunk]) -> str:
        body = await post_json(
            self._url,
            headers=self._headers,
            payload=self.build_payload(SYSTEM_PROMPT, build_user_prompt(question, passages)),
            timeout=self._timeout,
            provider=self.name,
        )
        try:
            text = self.extract_text(body).strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderError(
                f"unexpected response shape from {self.name}",
                details={"provider": self.name},
            ) from exc
        if not text:
            raise ProviderError(f"{self.name} returned an empty answer", details={"provider": self.name})
        return text


class OpenAIAnswerer(RemoteAnswerer):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if not settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not set", details={"provider": "openai"})
        super().__init__(
            url=f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            model=settings.openai_chat_model,
            timeout=settings.provider_timeout_seconds,
        )

    def build_payload(self, system: str, user: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": ANSWER_TEMPERATURE,
            "max_tokens": MAX_ANSWER_TOKENS,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }

    def extract_text(self, body: dict[str, Any]) -> str:
        return body["choices"][0]["message"]["content"]


class AnthropicAnswerer(RemoteAnswerer):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        if not settings.anthropic_api_key:
            raise ProviderError("ANTHROPIC_API_KEY is not set", details={"provider": "anthropic"})
        super().__init__(
            url=f"{settings.anthropic_base_url.rstrip('/')}/v1/messages",
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            model=settings.anthropic_model,
            timeout=settings.provider_timeout_seconds,
        )

    def build_payload(self, system: str, user: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "system": system,
            "temperature": ANSWER_TEMPERATURE,
            "max_tokens": MAX_ANSWER_TOKENS,
            "messages": [{"role": "user", "content": user}],
        }

    def extract_text(self, body: dict[str, Any]) -> str:
        return "".join(block.get("text", "") for block in body["content"] if block.get("type") == "text")


class ExtractiveAnswerer(Answerer):
    """Offline fallback: quote the best-matching sentences, with markers."""

    name = "local"
    model = "extractive"
    max_sentences = 3
    snippet_chars = 320
    # Short fragments are usually headings or list labels. They match a
    # question's keywords easily but say nothing on their own.
    min_sentence_chars = 25

    async def answer(self, question: str, passages: list[ScoredChunk]) -> str:
        wanted = {stem(token) for token in tokenize(question)}
        # (overlap, tie_breaker, marker, position, sentence)
        scored: list[tuple[float, float, int, int, str]] = []

        for marker, passage in enumerate(passages, start=1):
            for position, sentence in enumerate(split_sentences(passage.text)):
                terms = {stem(token) for token in tokenize(sentence)}
                if not terms or not wanted or len(sentence) < self.min_sentence_chars:
                    continue
                overlap = len(wanted & terms) / len(wanted)
                if overlap == 0:
                    continue
                # Break ties towards better-ranked passages and earlier
                # sentences, which tend to carry the topic statement.
                tie_breaker = (len(passages) - marker + 1) / (len(passages) * 20) - position / 200
                scored.append((overlap, tie_breaker, marker, position, sentence))

        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
        chosen = scored[: self.max_sentences]
        if not chosen:
            # No sentence shares a term with the question, yet retrieval still
            # cleared its threshold; quote the best passage instead of
            # claiming there is nothing.
            return f"{condense(passages[0].text, self.snippet_chars)} [1]"

        # Restore reading order so the quoted sentences flow.
        chosen.sort(key=lambda row: (row[2], row[3]))
        return " ".join(
            f"{condense(sentence, self.snippet_chars)} [{marker}]" for _, _, marker, _, sentence in chosen
        )


def build_answerer(settings: Settings) -> Answerer:
    choice = settings.resolved_llm_provider()
    if choice == "openai":
        return OpenAIAnswerer(settings)
    if choice == "anthropic":
        return AnthropicAnswerer(settings)
    if choice == "local":
        return ExtractiveAnswerer()
    raise ProviderError(
        f"unknown LLM provider {choice!r}; expected 'openai', 'anthropic', 'local' or 'auto'",
        details={"provider": choice},
    )


@lru_cache(maxsize=1)
def get_answerer() -> Answerer:
    answerer = build_answerer(get_settings())
    logger.info("answer provider ready", extra={"provider": answerer.name, "model": answerer.model})
    return answerer


def reset_answerer_cache() -> None:
    get_answerer.cache_clear()
