"""The studio's HTTP surface.

    POST /projects                       submit a brief (+ files) -> queued project
    GET  /projects/{id}                  status, plan, tasks, package
    GET  /projects/{id}/events           SSE: replay past Last-Event-ID, then live
    POST /projects/{id}/answers          resume a clarify interrupt
    POST /projects/{id}/review           resume a studio-review interrupt (editor)
    POST /projects/{id}/pick             client chose a design (taste corpus)
    POST /projects/{id}/unlock           mark paid (called by web after payment)
    GET  /projects/{id}/files/{artifact} deliverable download (payment-gated)

The web app proxies to these same-origin; auth is a shared-secret JWT minted
by Auth.js (see api/auth.py). Everything is built by create_app() so tests
can run isolated instances against their own databases.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager

from fastapi import (
    Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile,
)
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from aura.api.auth import Caller, make_verifier
from aura.bus import get_bus
from aura.config import Settings, build_providers
from aura.db.engine import get_sessionmaker, init_db
from aura.db.repo import Repo
from aura.schemas import ClarifyResponse, ReviewResponse
from aura.storage import ArtifactStore
from aura.worker import JobRunner


class ProjectOut(BaseModel):
    project_id: str
    status: str
    tier: str
    paid: bool
    brief: dict | None = None
    plan: dict | None = None
    package: dict | None = None
    tasks: list[dict] = []
    pending_interrupt: dict | None = None
    spent_usd: float = 0.0
    error: str | None = None


class PickBody(BaseModel):
    candidate_id: str


def _sse(event_id: int, event_type: str, data: dict) -> str:
    return f"id: {event_id}\nevent: {event_type}\ndata: {json.dumps(data)}\n\n"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    providers = build_providers(settings)
    store = ArtifactStore(settings.artifact_dir)
    runner = JobRunner(settings, providers)
    verify = make_verifier(settings.api_jwt_secret)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await init_db(settings.database_url)
        yield

    app = FastAPI(title="AURA Studio", version="0.2.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.runner = runner

    def repo() -> Repo:
        return Repo(get_sessionmaker(settings.database_url))

    def _budget_for(tier: str) -> float:
        if tier == "studio":
            return settings.studio_budget_usd
        if tier == "standard":
            return settings.project_budget_usd
        return 1.0

    async def _project_out(r: Repo, project_id: str) -> ProjectOut:
        project = await r.get_project(project_id)
        if project is None:
            raise HTTPException(404, "unknown project")
        tasks = await r.list_tasks(project_id)
        pending = await r.pending_interrupt(project_id)
        artifacts = await r.list_artifacts(project_id)
        by_path = {a.storage_key: a for a in artifacts}
        package = project.package
        if package:  # map file paths -> downloadable artifact ids
            package = json.loads(json.dumps(package))
            for c in package.get("selected", []):
                c["preview_artifact_ids"] = [
                    by_path[p].id for p in c.get("preview_paths", []) if p in by_path]
                pdf = c.get("print_pdf_path")
                c["print_artifact_id"] = (by_path[pdf].id
                                          if pdf and pdf in by_path else None)
                c.pop("preview_paths", None)     # never leak server paths
                c.pop("print_pdf_path", None)
        return ProjectOut(
            project_id=project.id, status=project.status, tier=project.tier,
            paid=project.paid, brief=project.brief, plan=project.plan,
            package=package, spent_usd=float(project.spent_usd or 0),
            error=project.error,
            pending_interrupt=({"kind": pending.kind, "payload": pending.payload}
                               if pending else None),
            tasks=[{"task_id": t.task_id, "role_key": t.role_key, "title": t.title,
                    "status": t.status, "depends_on": t.depends_on,
                    "cost_usd": float(t.cost_usd or 0)} for t in tasks])

    @app.post("/projects", response_model=ProjectOut)
    async def create_project(
        brief: str = Form(...),
        tier: str = Form("preview"),
        files: list[UploadFile] = File(default=[]),
        file_descriptions: str = Form(""),
        caller: Caller = Depends(verify),
    ) -> ProjectOut:
        if tier not in ("preview", "standard", "studio"):
            raise HTTPException(422, "unknown tier")
        if tier != "preview" and caller.user_id is None:
            raise HTTPException(401, "paid tiers require an account")
        r = repo()
        project_id = uuid.uuid4().hex[:12]
        await r.create_project(project_id=project_id, request_text=brief, tier=tier,
                               budget_cap_usd=_budget_for(tier), user_id=caller.user_id)
        for i, f in enumerate(files):
            data = await f.read()
            path = store.save(project_id, f"input-{i}-{f.filename}", data)
            await r.add_artifact(project_id=project_id, kind="input", storage_key=path,
                                 mime=f.content_type or "image/png")
        await runner.submit(project_id)
        return await _project_out(r, project_id)

    @app.get("/projects/{project_id}", response_model=ProjectOut)
    async def get_project(project_id: str,
                          caller: Caller = Depends(verify)) -> ProjectOut:
        return await _project_out(repo(), project_id)

    @app.get("/projects/{project_id}/events")
    async def project_events(project_id: str, request: Request,
                             last_event_id: str | None = Header(
                                 default=None, alias="Last-Event-ID")):
        r = repo()
        if await r.get_project(project_id) is None:
            raise HTTPException(404, "unknown project")
        bus = get_bus(settings.redis_url)

        async def stream():
            after = (int(last_event_id)
                     if last_event_id and last_event_id.isdigit() else 0)
            for row in await r.events_after(project_id, after_id=after):
                yield _sse(row.id, row.type,
                           {"type": row.type, "task_id": row.task_id,
                            "role_key": row.role_key, "payload": row.payload})
                after = row.id
            agen = bus.subscribe(project_id).__aiter__()
            while not await request.is_disconnected():
                try:
                    msg = await asyncio.wait_for(agen.__anext__(), timeout=15.0)
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                except StopAsyncIteration:
                    break
                if msg.get("id", 0) > after:
                    after = msg["id"]
                    yield _sse(msg["id"], msg.get("type", "message"), msg)

        return StreamingResponse(stream(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache",
                                          "X-Accel-Buffering": "no"})

    @app.post("/projects/{project_id}/answers", response_model=ProjectOut)
    async def answer_questions(project_id: str, body: ClarifyResponse,
                               caller: Caller = Depends(verify)) -> ProjectOut:
        r = repo()
        project = await r.get_project(project_id)
        if project is None:
            raise HTTPException(404, "unknown project")
        if project.status != "waiting_input":
            raise HTTPException(409, f"project is {project.status}, "
                                     "not waiting for input")
        pending = await r.pending_interrupt(project_id)
        if pending is None or pending.kind != "clarify":
            raise HTTPException(409, "no pending clarification")
        await r.resolve_interrupt(pending.id, body.model_dump(mode="json"))
        await runner.submit(project_id, resume=body.model_dump(mode="json"))
        return await _project_out(r, project_id)

    @app.post("/projects/{project_id}/review", response_model=ProjectOut)
    async def studio_review(project_id: str, body: ReviewResponse,
                            caller: Caller = Depends(verify)) -> ProjectOut:
        if not caller.is_editor:
            raise HTTPException(403, "editor token required")
        r = repo()
        project = await r.get_project(project_id)
        if project is None:
            raise HTTPException(404, "unknown project")
        if project.status != "waiting_review":
            raise HTTPException(409, f"project is {project.status}, "
                                     "not waiting for review")
        pending = await r.pending_interrupt(project_id)
        if pending is None or pending.kind != "studio_review":
            raise HTTPException(409, "no pending review")
        await r.resolve_interrupt(pending.id, body.model_dump(mode="json"))
        await runner.submit(project_id, resume=body.model_dump(mode="json"))
        return await _project_out(r, project_id)

    @app.post("/projects/{project_id}/pick")
    async def pick_design(project_id: str, body: PickBody,
                          caller: Caller = Depends(verify)) -> dict:
        await repo().set_picked_candidate(project_id, body.candidate_id)
        return {"ok": True}

    @app.post("/projects/{project_id}/unlock")
    async def unlock(project_id: str, caller: Caller = Depends(verify)) -> dict:
        """Called by the web app's payment webhook handler (service token)."""
        if not caller.is_editor:
            raise HTTPException(403, "service token required")
        await repo().update_project(project_id, paid=True)
        return {"ok": True}

    @app.get("/projects/{project_id}/files/{artifact_id}")
    async def get_file(project_id: str, artifact_id: str,
                       caller: Caller = Depends(verify)) -> FileResponse:
        r = repo()
        project = await r.get_project(project_id)
        artifact = await r.get_artifact(artifact_id)
        if project is None or artifact is None or artifact.project_id != project_id:
            raise HTTPException(404, "not found")
        # Previews stream freely; print files, sources and videos need payment.
        if artifact.kind in ("print_pdf", "source", "video") and not project.paid:
            raise HTTPException(402, "unlock this project to download deliverables")
        return FileResponse(artifact.storage_key, media_type=artifact.mime)

    return app


app = create_app()
