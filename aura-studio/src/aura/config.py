"""Environment-driven configuration and provider wiring."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from aura.providers.base import ImageGen, LayoutRenderer, TextLLM, VideoGen


@dataclass
class Settings:
    provider_mode: str = field(default_factory=lambda: os.getenv("AURA_PROVIDERS", "auto"))
    anthropic_model: str = field(default_factory=lambda: os.getenv("AURA_LLM_MODEL", "claude-sonnet-5"))
    openai_api_key: str | None = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    ideogram_api_key: str | None = field(default_factory=lambda: os.getenv("IDEOGRAM_API_KEY"))
    replicate_api_key: str | None = field(default_factory=lambda: os.getenv("REPLICATE_API_TOKEN"))
    anthropic_api_key: str | None = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    artifact_dir: Path = field(default_factory=lambda: Path(os.getenv("AURA_ARTIFACTS", "./artifacts")))
    # Creative dials
    min_directions: int = 4
    max_directions: int = 6
    ship_threshold: float = 7.0        # critique overall needed to skip revision
    max_revisions: int = 2
    final_count: int = 5               # designs delivered to the client


@dataclass
class Providers:
    llm: TextLLM
    image_gen: ImageGen
    video_gen: VideoGen
    renderer: LayoutRenderer


def build_providers(settings: Settings) -> Providers:
    """`AURA_PROVIDERS=mock` forces offline mode; `auto` uses real providers
    where keys exist and mocks elsewhere, so a partial key set still works."""
    from aura.providers.mock import MockImageGen, MockLLM, MockVideoGen
    from aura.render.html_renderer import PlaywrightRenderer

    mock = settings.provider_mode == "mock"

    if not mock and settings.anthropic_api_key:
        from aura.providers.anthropic_llm import AnthropicLLM
        llm: TextLLM = AnthropicLLM(model=settings.anthropic_model)
    else:
        llm = MockLLM()

    if not mock and settings.ideogram_api_key:
        from aura.providers.image_gen import IdeogramImageGen
        image_gen: ImageGen = IdeogramImageGen(settings.ideogram_api_key)
    elif not mock and settings.openai_api_key:
        from aura.providers.image_gen import OpenAIImageGen
        image_gen = OpenAIImageGen(settings.openai_api_key)
    else:
        image_gen = MockImageGen()

    if not mock and settings.replicate_api_key:
        from aura.providers.video_gen import ReplicateVideoGen
        video_gen: VideoGen = ReplicateVideoGen(settings.replicate_api_key)
    else:
        video_gen = MockVideoGen()

    return Providers(llm=llm, image_gen=image_gen, video_gen=video_gen,
                     renderer=PlaywrightRenderer())
