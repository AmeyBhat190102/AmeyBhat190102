"""Environment-driven configuration (pydantic-settings) and provider wiring."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from aura.providers.base import ImageGen, LayoutRenderer, TextLLM, VideoGen


class Settings(BaseSettings):
    """All knobs come from the environment (or .env). Grouped by concern."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                      extra="ignore")

    # --- providers -------------------------------------------------------
    provider_mode: str = "auto"                      # auto | mock
    anthropic_model: str = "claude-sonnet-5"
    judge_model: str = "claude-opus-4-8"             # aura extraction + critique
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    ideogram_api_key: str | None = None
    recraft_api_key: str | None = None
    replicate_api_token: str | None = None

    # --- infrastructure ---------------------------------------------------
    database_url: str = "sqlite+aiosqlite:///./aura.db"   # postgresql+asyncpg://... in prod
    redis_url: str | None = None                     # None => inline job execution (dev/tests)
    artifact_dir: Path = Path("./artifacts")
    api_jwt_secret: str = "dev-secret-change-me-32bytes-min!!"  # shared with the web app

    # --- creative & cost dials -------------------------------------------
    min_directions: int = 4
    max_directions: int = 6
    ship_threshold: float = 7.0                      # critique overall needed to skip revision
    max_revisions: int = 2
    final_count: int = 5                             # designs delivered to the client
    dynamic_planning: bool = True                    # producer/WorkPlan path (off => fixed graph)
    max_plan_tasks: int = 14
    project_budget_usd: float = 5.0                  # standard tier engine budget
    studio_budget_usd: float = 20.0                  # studio tier engine budget

    # legacy env aliases kept working
    def __init__(self, **kwargs):
        import os
        kwargs.setdefault("provider_mode", os.getenv("AURA_PROVIDERS", "auto"))
        kwargs.setdefault("anthropic_model", os.getenv("AURA_LLM_MODEL", "claude-sonnet-5"))
        if os.getenv("AURA_ARTIFACTS"):
            kwargs.setdefault("artifact_dir", Path(os.environ["AURA_ARTIFACTS"]))
        if os.getenv("AURA_DYNAMIC_PLANNING"):
            kwargs.setdefault("dynamic_planning",
                              os.environ["AURA_DYNAMIC_PLANNING"].lower() not in ("0", "false"))
        super().__init__(**kwargs)

    @property
    def checkpointer_url(self) -> str:
        """The checkpointer speaks psycopg/sqlite directly, not SQLAlchemy dialects."""
        return (self.database_url
                .replace("postgresql+asyncpg://", "postgresql://")
                .replace("sqlite+aiosqlite:///", "sqlite:///"))


@dataclass
class Providers:
    llm: TextLLM
    judge: TextLLM              # stronger model for aura extraction + critique
    image_gen: ImageGen
    video_gen: VideoGen
    renderer: LayoutRenderer


def build_providers(settings: Settings) -> Providers:
    """`provider_mode=mock` forces offline mode; `auto` uses real providers
    where keys exist and mocks elsewhere, so a partial key set still works."""
    from aura.providers.mock import MockImageGen, MockLLM, MockVideoGen
    from aura.render.html_renderer import PlaywrightRenderer

    mock = settings.provider_mode == "mock"

    if not mock and settings.anthropic_api_key:
        from aura.providers.anthropic_llm import AnthropicLLM
        llm: TextLLM = AnthropicLLM(model=settings.anthropic_model)
        judge: TextLLM = AnthropicLLM(model=settings.judge_model)
    else:
        llm = MockLLM()
        judge = llm  # same mock instance so tests can inspect one call log

    if not mock and settings.ideogram_api_key:
        from aura.providers.image_gen import IdeogramImageGen
        image_gen: ImageGen = IdeogramImageGen(settings.ideogram_api_key)
    elif not mock and settings.openai_api_key:
        from aura.providers.image_gen import OpenAIImageGen
        image_gen = OpenAIImageGen(settings.openai_api_key)
    else:
        image_gen = MockImageGen()

    if not mock and settings.replicate_api_token:
        from aura.providers.video_gen import ReplicateVideoGen
        video_gen: VideoGen = ReplicateVideoGen(settings.replicate_api_token)
    else:
        video_gen = MockVideoGen()

    return Providers(llm=llm, judge=judge, image_gen=image_gen, video_gen=video_gen,
                     renderer=PlaywrightRenderer())
