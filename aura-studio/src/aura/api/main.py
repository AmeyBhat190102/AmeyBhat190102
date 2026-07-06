"""HTTP surface: submit a project (text brief + files), poll status, fetch
the delivered gallery. Jobs run as background tasks; swap in a queue
(SQS/Celery) behind the same endpoints when volume demands it."""

from __future__ import annotations

import asyncio
import uuid
from typing import Literal

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from aura.config import Settings, build_providers
from aura.graph.pipeline import run_studio
from aura.schemas import DeliverablePackage, InputAsset
from aura.storage import ArtifactStore

app = FastAPI(title="AURA Studio", version="0.1.0")

settings = Settings()
providers = build_providers(settings)
store = ArtifactStore(settings.artifact_dir)


class Job(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"] = "queued"
    error: str | None = None
    package: DeliverablePackage | None = None


JOBS: dict[str, Job] = {}


async def _execute(job_id: str, request_text: str, assets: list[InputAsset]) -> None:
    JOBS[job_id].status = "running"
    try:
        package = await run_studio(providers, settings, store,
                                   request_text=request_text, assets=assets)
        JOBS[job_id].package = package
        JOBS[job_id].status = "done"
    except Exception as e:  # surfaced via the job, not a dropped task
        JOBS[job_id].status = "failed"
        JOBS[job_id].error = str(e)


@app.post("/projects", response_model=Job)
async def create_project(
    background: BackgroundTasks,
    brief: str = Form(..., description="The design request, in the client's words"),
    files: list[UploadFile] = File(default=[]),
    file_descriptions: str = Form("", description="One line per file, same order"),
) -> Job:
    job_id = uuid.uuid4().hex[:12]
    descriptions = [d.strip() for d in file_descriptions.splitlines()]
    assets = []
    for i, f in enumerate(files):
        data = await f.read()
        path = store.save(job_id, f"input-{i}-{f.filename}", data)
        assets.append(InputAsset(
            kind="photo", path=path,
            media_type=f.content_type or "image/png",
            description=descriptions[i] if i < len(descriptions) else (f.filename or ""),
        ))
    JOBS[job_id] = Job(job_id=job_id)
    background.add_task(asyncio.ensure_future, _execute(job_id, brief, assets))
    return JOBS[job_id]


@app.get("/projects/{job_id}", response_model=Job)
async def get_project(job_id: str) -> Job:
    if job_id not in JOBS:
        raise HTTPException(404, "unknown job")
    return JOBS[job_id]


@app.get("/projects/{job_id}/files")
async def get_file(job_id: str, path: str) -> FileResponse:
    job = JOBS.get(job_id)
    if not job or not job.package:
        raise HTTPException(404, "no deliverables yet")
    allowed = {p for c in job.package.selected
               for p in [*c.preview_paths, c.print_pdf_path] if p}
    if path not in allowed:
        raise HTTPException(403, "not a deliverable of this project")
    return FileResponse(path)
