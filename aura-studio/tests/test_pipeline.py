"""End-to-end pipeline tests on mock providers.

The layout engine (Playwright/Chromium) runs for real, so these tests verify
the actual deliverable path: brief -> aura -> directions -> specs -> rendered
PNG + print PDF -> critique -> curated package."""

from __future__ import annotations

import os

import pytest

os.environ["AURA_PROVIDERS"] = "mock"

from aura.config import Providers, Settings
from aura.providers.mock import MockImageGen, MockLLM, MockVideoGen
from aura.graph.pipeline import run_studio
from aura.render.html_renderer import PlaywrightRenderer
from aura.schemas import ARTIFACT_TYPES, Critique, CritiqueScore, Candidate, ConceptDirection, LayoutSpec
from aura.storage import ArtifactStore
from aura.agents.curator import select_diverse


@pytest.fixture
def providers() -> Providers:
    return Providers(llm=MockLLM(), image_gen=MockImageGen(),
                     video_gen=MockVideoGen(), renderer=PlaywrightRenderer())


@pytest.fixture
def settings() -> Settings:
    return Settings(provider_mode="mock", final_count=4)


async def test_full_pipeline_business_card(tmp_path, providers, settings):
    store = ArtifactStore(tmp_path)
    package = await run_studio(
        providers, settings, store,
        request_text="Design a visiting card for Adv. R. K. Sharma, a senior "
                     "advocate with 20 years in constitutional law. Understated, premium.")

    # Intake and aura ran
    assert package.brief.artifact_type_key == "business_card"
    assert package.aura.archetype
    # Curated gallery respects the requested count and dedupes directions
    assert 1 <= len(package.selected) <= settings.final_count
    direction_ids = [c.direction.direction_id for c in package.selected]
    assert len(direction_ids) == len(set(direction_ids))
    # Every selected design has a real preview and a print PDF
    for c in package.selected:
        assert c.preview_paths and os.path.exists(c.preview_paths[0])
        assert os.path.getsize(c.preview_paths[0]) > 1000  # real Chromium render
        assert c.print_pdf_path and os.path.exists(c.print_pdf_path)
        assert store.load(c.print_pdf_path)[:5] == b"%PDF-"
    # One rationale per selected design
    assert {r.candidate_id for r in package.rationales} == {
        c.candidate_id for c in package.selected}


async def test_pipeline_agent_order(tmp_path, providers, settings):
    store = ArtifactStore(tmp_path)
    await run_studio(providers, settings, store, request_text="visiting card for an advocate")
    calls = providers.llm.calls
    # brief -> aura -> directions -> N specs -> N critiques -> rationales
    assert calls[0] == "DesignBrief"
    assert calls[1] == "AuraProfile"
    assert calls[2] == "DirectionsBatch"
    assert calls.count("LayoutSpec") >= settings.min_directions - 1
    assert calls.count("Critique") == calls.count("LayoutSpec")


def _mk(risk: str, score: float) -> tuple[Candidate, Critique]:
    c = Candidate(
        direction=ConceptDirection(name=f"d-{risk}-{score}", thesis="t",
                                   how_it_expresses_aura="a", differentiator="x",
                                   risk_level=risk),
        spec=LayoutSpec(html="<html></html>"))
    crit = Critique(candidate_id=c.candidate_id,
                    scores=[CritiqueScore(criterion="craft", score=score, note="")],
                    overall=score, verdict="ship")
    return c, crit


def test_select_diverse_prefers_risk_spread():
    pairs = [_mk("safe", 9.0), _mk("safe", 8.9), _mk("safe", 8.8),
             _mk("balanced", 8.2), _mk("bold", 7.9)]
    candidates = [c for c, _ in pairs]
    critiques = {cr.candidate_id: cr for _, cr in pairs}
    chosen = select_diverse(candidates, critiques, k=3)
    risks = {c.direction.risk_level for c in chosen}
    assert risks == {"safe", "balanced", "bold"}  # not three near-identical safes


def test_artifact_registry_covers_all_classes():
    classes = {t.artifact_class for t in ARTIFACT_TYPES.values()}
    assert len(classes) == 3
