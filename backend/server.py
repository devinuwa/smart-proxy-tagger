"""FastAPI entrypoint for Smart Proxy Tagger.

POST /api/jobs starts a Temporal workflow and returns immediately.
GET /api/jobs/{id} is what the processing dashboard polls.
GET /api/search reads pgvector. This process does not caption frames.
"""

from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from temporalio.client import Client
from temporalio.service import RPCError

from . import db
from .embeddings import embed_text
from .workflow import TASK_QUEUE, IndexFootageWorkflow

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .env stays at the repository root, beside this package.
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


class JobRequest(BaseModel):
    path: str = Field(..., description="Local video file or folder on this machine.")


class SearchHit(BaseModel):
    video_path: str
    timestamp_seconds: float
    caption: str
    signals: list[str]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_pool()
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    app.state.temporal = await Client.connect(address, namespace=namespace)
    app.state.task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", TASK_QUEUE)
    try:
        yield
    finally:
        await db.close_pool()


app = FastAPI(title="Smart Proxy Tagger", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    database = "ok"
    temporal = "ok"
    try:
        await db.ping()
    except Exception as exc:
        database = str(exc)
    try:
        await app.state.temporal.service_client.check_health()
    except Exception as exc:
        temporal = str(exc)
    return {"database": database, "temporal": temporal}


@app.post("/api/jobs", status_code=202)
async def start_job(body: JobRequest) -> dict:
    """Accept a local path and hand the work to Temporal."""
    path = Path(body.path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {body.path}")
    workflow_id = f"footage-{uuid.uuid4().hex[:12]}"
    await db.upsert_job(workflow_id, str(path.resolve()), "queued")
    try:
        await app.state.temporal.start_workflow(
            IndexFootageWorkflow.run,
            {"workflow_id": workflow_id, "path": str(path.resolve())},
            id=workflow_id,
            task_queue=app.state.task_queue,
        )
    except RPCError as exc:
        await db.update_job(workflow_id, status="failed", voice_error=str(exc))
        raise HTTPException(status_code=503, detail="Temporal is not accepting workflows.") from exc
    return {"workflow_id": workflow_id, "status": "queued"}


@app.get("/api/jobs/{workflow_id}")
async def job_status(workflow_id: str) -> dict:
    """Dashboard payload: database progress, plus the workflow query when it answers."""
    row = await db.get_job(workflow_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Unknown workflow id.")
    live = None
    try:
        handle = app.state.temporal.get_workflow_handle(workflow_id)
        live = await handle.query(IndexFootageWorkflow.progress)
    except Exception:
        logger.info("Workflow query unavailable for %s", workflow_id)
    payload = _public_job(row)
    if live:
        payload["workflow"] = live
    seen = payload["frames_seen"] or 0
    done = payload["frames_captioned"] or 0
    payload["progress"] = 0.0 if seen == 0 else round(done / seen, 4)
    return payload


@app.get("/api/search", response_model=list[SearchHit])
async def search(q: str, limit: int = 10, video_path: str | None = None) -> list[SearchHit]:
    """Fuse keyword and vector hits. Each hit names the signal that found it."""
    query = q.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query q is required.")
    limit = min(max(limit, 1), 50)
    lists = await db.search_segments(query, embed_text(query), limit, video_path)
    return _fuse_models(lists["vector"], lists["keyword"], limit)


def _fuse_models(vector_rows: list[dict], keyword_rows: list[dict], limit: int) -> list[SearchHit]:
    """Reciprocal rank fusion. Signals stay on the hit so the gallery can show them.

    Rank fusion can bury a strong vector hit under a weak keyword hit
    (faridgnank02, hybrid search write-up). Returning `signals` keeps both
    explanations visible instead of pretending the fused order is the only one.
    """
    k = 60
    scores: dict[int, float] = {}
    signals: dict[int, set[str]] = {}
    rows: dict[int, dict] = {}
    for source, group in (("vector", vector_rows), ("keyword", keyword_rows)):
        for rank, row in enumerate(group, start=1):
            row_id = int(row["id"])
            rows[row_id] = row
            scores[row_id] = scores.get(row_id, 0.0) + 1.0 / (k + rank)
            signals.setdefault(row_id, set()).add(source)
    ordered = sorted(scores, key=lambda row_id: scores[row_id], reverse=True)[:limit]
    hits = []
    for row_id in ordered:
        row = rows[row_id]
        hits.append(
            SearchHit(
                video_path=row["video_path"],
                timestamp_seconds=float(row["timestamp_seconds"]),
                caption=row["caption"],
                signals=sorted(signals[row_id]),
            )
        )
    return hits


def _public_job(row: dict) -> dict:
    updated = row.get("updated_at")
    return {
        "workflow_id": row["workflow_id"],
        "video_path": row["video_path"],
        "status": row["status"],
        "frames_seen": row["frames_seen"],
        "frames_captioned": row["frames_captioned"],
        "voice_played": row["voice_played"],
        "voice_error": row["voice_error"],
        "caption_model": row["caption_model"],
        "updated_at": updated.isoformat() if updated is not None else None,
    }
