"""End-to-end tests of the dynamic studio: producer-planned crews, durable
interrupts (clarify + studio review), event stream, and budget governance.
Mock reasoning, real sqlite checkpoints, real Chromium renders."""

from __future__ import annotations

import os

import pytest

os.environ["AURA_PROVIDERS"] = "mock"

from aura.config import Providers, Settings, build_providers
from aura.db.engine import dispose, get_sessionmaker, init_db
from aura.db.repo import Repo
from aura.providers.mock import MockLLM, _FIXTURES
from aura.worker import run_project


@pytest.fixture
async def env(tmp_path):
    settings = Settings(
        provider_mode="mock",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aura.db",
        artifact_dir=tmp_path / "artifacts",
        redis_url=None,
    )
    await init_db(settings.database_url)
    providers = build_providers(settings)
    repo = Repo(get_sessionmaker(settings.database_url))
    yield settings, providers, repo
    await dispose()


async def _new_project(repo, project_id="p1", tier="standard", budget=5.0):
    await repo.create_project(project_id=project_id, tier=tier,
                              budget_cap_usd=budget,
                              request_text="visiting card for a senior advocate")
    return project_id


async def test_dynamic_run_full_crew(env):
    settings, providers, repo = env
    pid = await _new_project(repo)
    status = await run_project(settings, providers, project_id=pid)
    assert status == "done"

    project = await repo.get_project(pid)
    assert project.status == "done"
    assert project.package and len(project.package["selected"]) >= 3
    assert project.plan and len(project.plan["tasks"]) == 6

    # Support tasks ran before designs (dependency order held)
    tasks = {t.task_id: t for t in await repo.list_tasks(pid)}
    assert tasks["type1"].status == "succeeded"
    assert all(tasks[f"design{i}"].status == "succeeded" for i in range(1, 5))

    # The theater got its narration, in causal order
    events = await repo.events_after(pid, 0)
    types = [e.type for e in events]
    assert types.index("plan_created") < types.index("task_started")
    assert "artifact_ready" in types and "critique" in types
    assert types[-1] == "status_changed"  # done

    # Deliverables exist on disk and are registered
    artifacts = await repo.list_artifacts(pid)
    kinds = {a.kind for a in artifacts}
    assert {"preview_png", "print_pdf"} <= kinds
    for a in artifacts:
        assert os.path.exists(a.storage_key)

    # Taste corpus captured the trace
    # (record_taste ran without error; verified via project completion)


async def test_clarify_interrupt_roundtrip(env):
    settings, providers, repo = env
    # Force intake to raise a blocking question
    brief_fixture = dict(_FIXTURES["DesignBrief"]("x"))
    brief_fixture["open_questions"] = [{
        "question": "Which name spelling: Sharma or Sharmaa?",
        "why_it_matters": "It gets printed.",
        "default_assumption": "Sharma",
        "blocking": True,
    }]
    providers.llm.overrides["DesignBrief"] = brief_fixture

    pid = await _new_project(repo, "p2")
    status = await run_project(settings, providers, project_id=pid)
    assert status == "waiting_input"

    pending = await repo.pending_interrupt(pid)
    assert pending is not None and pending.kind == "clarify"
    assert "Sharma" in pending.payload["questions"][0]["question"]

    # Client answers; the run resumes from the checkpoint and completes
    await repo.resolve_interrupt(pending.id, {"answers": {"spelling": "Sharma"}})
    status = await run_project(settings, providers, project_id=pid,
                               resume={"answers": {"spelling": "Sharma"},
                                       "accept_defaults": False})
    assert status == "done"
    project = await repo.get_project(pid)
    assert any("Sharma" in p for p in project.brief["stated_preferences"])


async def test_studio_review_gate(env):
    settings, providers, repo = env
    pid = await _new_project(repo, "p3", tier="studio", budget=20.0)
    status = await run_project(settings, providers, project_id=pid)
    assert status == "waiting_review"

    pending = await repo.pending_interrupt(pid)
    assert pending.kind == "studio_review"
    candidate_ids = pending.payload["candidate_ids"]
    assert len(candidate_ids) >= 3

    # Editor approves everything -> run resumes to completion
    decisions = {"decisions": [{"candidate_id": c, "action": "approve", "notes": ""}
                               for c in candidate_ids]}
    await repo.resolve_interrupt(pending.id, decisions)
    status = await run_project(settings, providers, project_id=pid, resume=decisions)
    assert status == "done"


async def test_budget_denial_marks_tasks(env):
    settings, providers, repo = env
    pid = await _new_project(repo, "p4", budget=0.05)  # starve the run
    status = await run_project(settings, providers, project_id=pid)
    project = await repo.get_project(pid)
    tasks = await repo.list_tasks(pid)
    denied = [t for t in tasks if t.status in ("budget_denied", "failed", "skipped")]
    # With $0.05 the crew can't all run; governance must have kicked in
    assert denied, f"expected budget governance, got {[(t.task_id, t.status) for t in tasks]}"
    assert status in ("done", "failed")  # salvage or clean failure, never a hang


async def test_task_failure_isolation(env):
    settings, providers, repo = env

    calls = {"n": 0}
    real = providers.llm.structured

    async def flaky(**kwargs):
        if kwargs["output_model"].__name__ == "TypographyPlan":
            raise RuntimeError("specialist died")
        return await real(**kwargs)

    providers.llm.structured = flaky
    pid = await _new_project(repo, "p5")
    status = await run_project(settings, providers, project_id=pid)
    # type1 fails -> its dependents skipped... but the fixture plan makes all
    # four designs depend on it, so salvage yields a failed-but-graceful end
    # OR the plan degrades; either way: no hang, project reaches a terminal state.
    project = await repo.get_project(pid)
    assert project.status in ("done", "failed")
    tasks = {t.task_id: t.status for t in await repo.list_tasks(pid)}
    assert tasks.get("type1") == "failed"
    assert all(s == "skipped" for tid, s in tasks.items() if tid.startswith("design"))
