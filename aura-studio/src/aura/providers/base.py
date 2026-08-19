"""Provider protocols.

Model vendors leapfrog each other every quarter; the pipeline must not care.
Agents depend on these four protocols only. Concrete providers (Anthropic,
OpenAI images, Ideogram, Veo/Kling via Replicate, ...) are registered in
`registry.py` and selected by config — swapping the best tool of the month
is a one-line config change.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class TextLLM(Protocol):
    """Structured-output text reasoning. All agents speak through this."""

    async def structured(self, *, system: str, prompt: str, output_model: type[T],
                         images: list[str] | None = None) -> T:
        """Run a prompt (optionally with image paths for vision) and return a
        validated instance of `output_model`. Implementations MUST retry once
        on validation failure, feeding the error back to the model."""
        ...


@runtime_checkable
class ImageGen(Protocol):
    async def generate(self, *, prompt: str, negative_prompt: str = "",
                       width: int = 1024, height: int = 1024,
                       reference_image: str | None = None) -> bytes:
        """Return PNG bytes."""
        ...


@runtime_checkable
class VideoGen(Protocol):
    async def generate(self, *, prompt: str, source_image: str | None,
                       duration_s: float, width: int, height: int) -> bytes:
        """Image-to-video (or text-to-video if source_image is None). MP4 bytes."""
        ...


@runtime_checkable
class LayoutRenderer(Protocol):
    async def render_png(self, *, html: str, width_px: int, height_px: int) -> bytes: ...

    async def render_pdf(self, *, html: str, width_mm: float, height_mm: float) -> bytes: ...
