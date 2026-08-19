"""API integration tests: submit -> inline run -> package -> SSE replay ->
payment gating. Anonymous preview tier; mock providers; sqlite; no Redis."""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

os.environ["AURA_PROVIDERS"] = "mock"

from aura.api.main import create_app
from aura.config import Settings


@pytest.fixture
async def client(tmp_path):
    settings = Settings(
        provider_mode="mock",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/aura.db",
        artifact_dir=tmp_path / "artifacts",
        redis_url=None,
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport,
                                     base_url="http://studio") as c:
            yield c, app
    from aura.db.engine import dispose
    await dispose()


async def _wait_done(c, app, project_id: str, timeout: float = 120.0) -> dict:
    await asyncio.wait_for(app.state.runner.wait_inline(), timeout)
    resp = await c.get(f"/projects/{project_id}")
    return resp.json()


async def test_submit_run_and_package(client):
    c, app = client
    resp = await c.post("/projects", data={
        "brief": "visiting card for Adv. R. K. Sharma, senior advocate"})
    assert resp.status_code == 200
    project_id = resp.json()["project_id"]

    project = await _wait_done(c, app, project_id)
    assert project["status"] == "done"
    assert project["plan"] and project["package"]
    selected = project["package"]["selected"]
    assert len(selected) >= 3
    # Server paths must not leak; artifact ids must
    assert "preview_paths" not in selected[0]
    assert selected[0]["preview_artifact_ids"]

    # Task board reflects the crew
    assert {t["status"] for t in project["tasks"]} == {"succeeded"}


async def test_sse_replay(client):
    c, app = client
    resp = await c.post("/projects", data={"brief": "advocate card"})
    project_id = resp.json()["project_id"]
    await _wait_done(c, app, project_id)

    types = []
    async with c.stream("GET", f"/projects/{project_id}/events") as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("event: "):
                types.append(line.removeprefix("event: "))
            if "package_ready" in line:
                break
    assert "plan_created" in types
    assert "task_started" in types and "artifact_ready" in types


async def test_payment_gates_deliverables(client):
    c, app = client
    resp = await c.post("/projects", data={"brief": "advocate card"})
    project_id = resp.json()["project_id"]
    project = await _wait_done(c, app, project_id)

    selected = project["package"]["selected"][0]
    preview_id = selected["preview_artifact_ids"][0]
    print_id = selected["print_artifact_id"]

    # Preview streams freely
    assert (await c.get(f"/projects/{project_id}/files/{preview_id}")).status_code == 200
    # Print file requires payment
    assert (await c.get(f"/projects/{project_id}/files/{print_id}")).status_code == 402
    # Unlock requires the service token
    assert (await c.post(f"/projects/{project_id}/unlock")).status_code == 403

    import jwt as pyjwt
    token = pyjwt.encode({"sub": "svc", "editor": True},
                         app.state.settings.api_jwt_secret, algorithm="HS256")
    resp = await c.post(f"/projects/{project_id}/unlock",
                        headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert (await c.get(f"/projects/{project_id}/files/{print_id}")).status_code == 200


async def test_paid_tier_requires_account(client):
    c, _ = client
    resp = await c.post("/projects", data={"brief": "card", "tier": "standard"})
    assert resp.status_code == 401
