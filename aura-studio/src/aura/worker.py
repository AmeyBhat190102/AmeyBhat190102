"""The studio's job runner.

One job type: run_project(project_id, resume) — advance the project's graph
to its next interrupt or to completion. Durability is layered:
  - LangGraph checkpoints every superstep into the database, so a retried or
    restarted job resumes mid-graph (a video crash at minute 20 never redoes
    the LLM work);
  - arq (Redis) provides retries and horizontal workers in production;
  - with no Redis configured, jobs run inline in-process (dev/test mode) —
    same code path, same checkpoints.

The worker is also the event pump: it consumes the graph's custom stream,
persists every ProjectEvent (Postgres id = SSE id), publishes it on the bus,
and maintains the tasks/artifacts/interrupts projections the web app reads.
"""

from __future__ import annotations

import asyncio
import contextlib
import mimetypes
from typing import Any

from langgraph.types import Command

from aura.bus import get_bus
from aura.config import Providers, Settings, build_providers
from aura.db.engine import get_sessionmaker, init_db
from aura.db.repo import Repo
from aura.graph.dynamic import build_dynamic_graph
from aura.schemas import InputAsset
from aura.storage import ArtifactStore

_ARTIFACT_KINDS = {"preview_png": "preview_png", "print_pdf": "print_pdf",
                   "video": "video", "motif": "source", "logo": "source"}


def _serde():
    """Checkpoint serializer with our pydantic contracts explicitly allowed
    (LangGraph refuses to revive unlisted types from checkpoints)."""
    import aura.planning.schemas as planning
    import aura.roles.outputs as outputs
    import aura.schemas as schemas
    from pydantic import BaseModel
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    models = [obj for mod in (schemas, planning, outputs)
              for obj in vars(mod).values()
              if isinstance(obj, type) and issubclass(obj, BaseModel)]
    return JsonPlusSerializer(allowed_msgpack_modules=[]).with_msgpack_allowlist(models)


@contextlib.asynccontextmanager
async def open_checkpointer(settings: Settings):
    """Postgres in production, sqlite for keyless dev — same database that
    holds the app tables, so one backup covers everything."""
    url = settings.checkpointer_url
    if url.startswith("postgresql://"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        async with AsyncPostgresSaver.from_conn_string(url, serde=_serde()) as saver:
            await saver.setup()
            yield saver
    else:
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
        path = url.removeprefix("sqlite:///")
        async with AsyncSqliteSaver.from_conn_string(path) as saver:
            saver.serde = _serde()
            yield saver


async def run_project(settings: Settings, providers: Providers, *, project_id: str,
                      resume: dict[str, Any] | None = None) -> str:
    """Advance one project. Returns the resulting project status."""
    repo = Repo(get_sessionmaker(settings.database_url))
    bus = get_bus(settings.redis_url)
    store = ArtifactStore(settings.artifact_dir)
    project = await repo.get_project(project_id)
    if project is None:
        raise ValueError(f"unknown project {project_id}")

    await repo.update_project(project_id, status="running")
    await _pump_event(repo, bus, project_id,
                      {"type": "status_changed", "payload": {"status": "running"}})

    assets = [
        InputAsset(asset_id=a.id[:12], kind="photo", path=a.storage_key,
                   media_type=a.mime, description="client upload")
        for a in await repo.list_artifacts(project_id) if a.kind == "input"
    ]

    config = {"configurable": {"thread_id": project_id}}
    graph_input: Any
    if resume is not None:
        graph_input = Command(resume=resume)
    else:
        graph_input = {
            "project_id": project_id,
            "tier": project.tier,
            "budget_cap_usd": float(project.budget_cap_usd),
            "request_text": project.request_text,
            "assets": assets,
            "task_results": {}, "candidates": {}, "critiques": {},
        }

    async with open_checkpointer(settings) as checkpointer:
        graph = build_dynamic_graph(providers, settings, store, checkpointer=checkpointer)
        try:
            async for mode, chunk in graph.astream(graph_input, config=config,
                                                   stream_mode=["custom", "updates"]):
                if mode == "custom":
                    await _pump_event(repo, bus, project_id, chunk)
                    await _project_side_effects(repo, project_id, chunk)
        except Exception as e:
            await repo.update_project(project_id, status="failed", error=str(e)[:2000])
            await _pump_event(repo, bus, project_id,
                              {"type": "error", "payload": {"message": str(e)[:500]}})
            raise

        state = await graph.aget_state(config)

    # Parked on an interrupt?
    for t in state.tasks:
        if t.interrupts:
            payload = t.interrupts[0].value
            kind = payload.get("kind", "clarify")
            status = "waiting_review" if kind == "studio_review" else "waiting_input"
            await repo.create_interrupt(project_id=project_id, kind=kind, payload=payload)
            await repo.update_project(project_id, status=status,
                                      brief=state.values.get("brief") and
                                      state.values["brief"].model_dump(mode="json"))
            await _pump_event(repo, bus, project_id,
                              {"type": "status_changed", "payload": {"status": status}})
            return status

    values = state.values
    package = values.get("package")
    if package is None:
        await repo.update_project(project_id, status="failed",
                                  error="graph finished without a package")
        return "failed"

    spent = round(sum(r.cost_usd for r in values.get("task_results", {}).values()), 4)
    await repo.update_project(
        project_id, status="done",
        brief=values["brief"].model_dump(mode="json"),
        plan=values.get("plan") and values["plan"].model_dump(mode="json"),
        package=package.model_dump(mode="json"),
        spent_usd=spent)
    for c in package.selected:
        for p in c.preview_paths:
            await repo.add_artifact(project_id=project_id, kind=_kind_for(p),
                                    storage_key=p, mime=_mime(p),
                                    candidate_id=c.candidate_id)
        if c.print_pdf_path:
            await repo.add_artifact(project_id=project_id, kind="print_pdf",
                                    storage_key=c.print_pdf_path, mime="application/pdf",
                                    candidate_id=c.candidate_id)
    await repo.record_taste(
        project_id=project_id,
        artifact_type_key=values["brief"].artifact_type_key,
        archetype=values["aura"].archetype,
        aura=values["aura"].model_dump(mode="json"),
        directions=[c.direction.model_dump(mode="json") for c in package.selected],
        critiques=[cr.model_dump(mode="json") for cr in values.get("critiques", {}).values()])
    await _pump_event(repo, bus, project_id,
                      {"type": "status_changed", "payload": {"status": "done"}})
    return "done"


async def _pump_event(repo: Repo, bus, project_id: str, event: dict) -> None:
    event_id = await repo.append_event(
        project_id=project_id, type=event.get("type", "task_progress"),
        payload=event.get("payload", {}), task_id=event.get("task_id"),
        role_key=event.get("role_key"))
    await bus.publish(project_id, {"id": event_id, **event})


async def _project_side_effects(repo: Repo, project_id: str, event: dict) -> None:
    """Maintain the tasks/artifacts projections the web app queries."""
    etype, payload = event.get("type"), event.get("payload", {})
    if etype == "plan_created":
        for t in payload.get("tasks", []):
            await repo.upsert_task(project_id=project_id, task_id=t["task_id"],
                                   role_key=t["role_key"], title=t["title"],
                                   depends_on=t.get("depends_on", []), status="pending")
    elif etype == "task_started":
        await repo.upsert_task(project_id=project_id, task_id=event.get("task_id", "?"),
                               role_key=event.get("role_key", ""),
                               title=payload.get("title", ""), status="running")
    elif etype == "task_finished":
        await repo.upsert_task(project_id=project_id, task_id=event.get("task_id", "?"),
                               status=payload.get("status", "succeeded"),
                               cost_usd=payload.get("cost_usd", 0.0),
                               error=payload.get("error"))
    elif etype == "artifact_ready" and payload.get("path"):
        await repo.add_artifact(project_id=project_id,
                                kind=_ARTIFACT_KINDS.get(payload.get("kind", ""), "source"),
                                storage_key=payload["path"], mime=_mime(payload["path"]),
                                task_id=event.get("task_id"))


def _mime(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


def _kind_for(path: str) -> str:
    return "video" if path.endswith(".mp4") else "preview_png"


# ---------------------------------------------------------------------------
# arq wiring (production) + inline runner (dev/tests)
# ---------------------------------------------------------------------------

async def _arq_run_project(ctx: dict, project_id: str,
                           resume: dict | None = None) -> str:
    return await run_project(ctx["settings"], ctx["providers"],
                             project_id=project_id, resume=resume)


async def _startup(ctx: dict) -> None:
    settings = Settings()
    await init_db(settings.database_url)
    ctx["settings"] = settings
    ctx["providers"] = build_providers(settings)


def _redis_settings():
    from arq.connections import RedisSettings
    return RedisSettings.from_dsn(Settings().redis_url or "redis://localhost:6379")


class WorkerSettings:
    """arq entrypoint: `arq aura.worker.WorkerSettings`."""

    functions = [_arq_run_project]
    on_startup = _startup
    job_timeout = 3600
    max_tries = 3
    redis_settings = _redis_settings()


class JobRunner:
    """Submit jobs from the API: arq when Redis is configured, otherwise an
    in-process task (single-process dev — identical code path + checkpoints)."""

    def __init__(self, settings: Settings, providers: Providers):
        self.settings = settings
        self.providers = providers
        self._pool = None
        self._inline: set[asyncio.Task] = set()

    async def submit(self, project_id: str, resume: dict | None = None) -> None:
        if self.settings.redis_url:
            if self._pool is None:
                from arq import create_pool
                from arq.connections import RedisSettings
                self._pool = await create_pool(
                    RedisSettings.from_dsn(self.settings.redis_url))
            await self._pool.enqueue_job(
                "_arq_run_project", project_id, resume,
                _job_id=f"project:{project_id}:{'resume' if resume else 'run'}")
        else:
            task = asyncio.create_task(
                run_project(self.settings, self.providers,
                            project_id=project_id, resume=resume))
            self._inline.add(task)
            task.add_done_callback(self._inline.discard)

    async def wait_inline(self) -> None:
        """Tests only: block until inline jobs finish."""
        while self._inline:
            await asyncio.gather(*list(self._inline), return_exceptions=True)
