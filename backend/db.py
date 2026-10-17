"""Local TimescaleDB + pgvector access.

Tiger Data bounty: embeddings stay in TimescaleDB on localhost.
The connection host must be loopback. A remote host is refused before
any socket opens.

Connections are synchronous and run in a worker thread. Uvicorn on Windows
uses a Proactor event loop, and psycopg's async driver refuses that loop.
"""

from __future__ import annotations

import asyncio
import logging
import os
from urllib.parse import urlparse

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .embeddings import EMBEDDING_DIMENSIONS

logger = logging.getLogger(__name__)

# Cosine distance. 0 is the same direction, 1 is no shared tokens for the
# Phase 2 hash embedder. Nearest-neighbor search still returns those rows.
# Dropping them is what lets "no match" stay empty. Keyword hits are kept.
# Phase 4's MiniLM space will need this number checked again.
VECTOR_MAX_COSINE_DISTANCE = 0.85

_pool: ConnectionPool | None = None

SCHEMA = f"""
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS footage_segments (
    id bigserial PRIMARY KEY,
    video_path text NOT NULL,
    timestamp_seconds double precision NOT NULL,
    caption text NOT NULL,
    caption_tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', caption)) STORED,
    embedding vector({EMBEDDING_DIMENSIONS}) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (video_path, timestamp_seconds)
);

CREATE INDEX IF NOT EXISTS footage_segments_tsv
    ON footage_segments USING gin (caption_tsv);

CREATE INDEX IF NOT EXISTS footage_segments_embedding
    ON footage_segments USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS index_jobs (
    workflow_id text PRIMARY KEY,
    video_path text NOT NULL,
    status text NOT NULL,
    frames_seen integer NOT NULL DEFAULT 0,
    frames_captioned integer NOT NULL DEFAULT 0,
    voice_played boolean NOT NULL DEFAULT false,
    voice_error text,
    caption_model text,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""


def database_url() -> str:
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://smartproxy:smartproxy@127.0.0.1:15432/smartproxy",
    )
    host = urlparse(url).hostname
    if host not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError(
            "DATABASE_URL host must be localhost. Footage metadata stays on this machine."
        )
    return url


def _configure(conn) -> None:
    register_vector(conn)


def _init_pool() -> None:
    global _pool
    if _pool is not None:
        return
    with psycopg.connect(database_url(), autocommit=True) as conn:
        for statement in SCHEMA.split(";"):
            sql = statement.strip()
            if sql:
                conn.execute(sql)
    _pool = ConnectionPool(
        conninfo=database_url(),
        min_size=1,
        max_size=4,
        kwargs={"row_factory": dict_row},
        configure=_configure,
        open=True,
    )


def _close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def _require_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("Database pool is not open.")
    return _pool


async def init_pool() -> None:
    await asyncio.to_thread(_init_pool)


async def close_pool() -> None:
    await asyncio.to_thread(_close_pool)


async def ping() -> None:
    def _ping() -> None:
        with _require_pool().connection() as conn:
            conn.execute("SELECT 1")

    await asyncio.to_thread(_ping)


async def upsert_job(workflow_id: str, video_path: str, status: str) -> None:
    def _run() -> None:
        with _require_pool().connection() as conn:
            conn.execute(
                """
                INSERT INTO index_jobs (workflow_id, video_path, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (workflow_id)
                DO UPDATE SET status = EXCLUDED.status, updated_at = now()
                """,
                (workflow_id, video_path, status),
            )
            conn.commit()

    await asyncio.to_thread(_run)


async def update_job(
    workflow_id: str,
    *,
    status: str | None = None,
    frames_seen: int | None = None,
    frames_captioned: int | None = None,
    voice_played: bool | None = None,
    voice_error: str | None = None,
    caption_model: str | None = None,
) -> None:
    """Write dashboard progress. The UI polls this row while the activity heartbeats."""

    def _run() -> None:
        assignments = ["updated_at = now()"]
        values: list[object] = []
        for column, value in (
            ("status", status),
            ("frames_seen", frames_seen),
            ("frames_captioned", frames_captioned),
            ("voice_played", voice_played),
            ("voice_error", voice_error),
            ("caption_model", caption_model),
        ):
            if value is not None:
                assignments.append(f"{column} = %s")
                values.append(value)
        values.append(workflow_id)
        with _require_pool().connection() as conn:
            conn.execute(
                f"UPDATE index_jobs SET {', '.join(assignments)} WHERE workflow_id = %s",
                values,
            )
            conn.commit()

    await asyncio.to_thread(_run)


async def get_job(workflow_id: str) -> dict | None:
    def _run() -> dict | None:
        with _require_pool().connection() as conn:
            cur = conn.execute(
                "SELECT * FROM index_jobs WHERE workflow_id = %s",
                (workflow_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    return await asyncio.to_thread(_run)


async def upsert_segment(
    video_path: str,
    timestamp_seconds: float,
    caption: str,
    embedding: list[float],
) -> None:
    def _run() -> None:
        with _require_pool().connection() as conn:
            conn.execute(
                """
                INSERT INTO footage_segments (video_path, timestamp_seconds, caption, embedding)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (video_path, timestamp_seconds)
                DO UPDATE SET caption = EXCLUDED.caption, embedding = EXCLUDED.embedding
                """,
                (video_path, timestamp_seconds, caption, Vector(embedding)),
            )
            conn.commit()

    await asyncio.to_thread(_run)


async def search_segments(query: str, query_embedding: list[float], limit: int, video_path: str | None) -> dict:
    """Keyword list plus vector list. Filtered vector search uses an exact scan.

    pgvector HNSW picks candidates before it applies WHERE, so a filter for one
    video can return zero rows. The filtered path materializes the matching
    rows first (the fix described by ji_ai, "pgvector HNSW Filtering").
    Unfiltered search enables iterative scan when this pgvector build has it.
    """

    def _run() -> dict:
        keyword = _keyword_hits(query, limit, video_path)
        vector = _vector_hits(query_embedding, limit, video_path)
        stored = _segment_count(video_path)
        if len(vector) < limit and stored > len(vector):
            logger.warning(
                "retrieval_shortfall wanted=%s got=%s stored=%s filtered=%s",
                limit,
                len(vector),
                stored,
                bool(video_path),
            )
        vector = [
            row for row in vector if float(row["distance"]) < VECTOR_MAX_COSINE_DISTANCE
        ]
        return {"keyword": keyword, "vector": vector}

    return await asyncio.to_thread(_run)


def _segment_count(video_path: str | None) -> int:
    sql = "SELECT count(*) AS n FROM footage_segments"
    params: tuple = ()
    if video_path:
        sql += " WHERE video_path = %s"
        params = (video_path,)
    with _require_pool().connection() as conn:
        cur = conn.execute(sql, params)
        row = cur.fetchone()
        return int(row["n"])


def _keyword_hits(query: str, limit: int, video_path: str | None) -> list[dict]:
    sql = """
        SELECT id, video_path, timestamp_seconds, caption,
               ts_rank(caption_tsv, plainto_tsquery('english', %s)) AS rank
        FROM footage_segments
        WHERE caption_tsv @@ plainto_tsquery('english', %s)
    """
    params: list[object] = [query, query]
    if video_path:
        sql += " AND video_path = %s"
        params.append(video_path)
    sql += " ORDER BY rank DESC LIMIT %s"
    params.append(limit)
    with _require_pool().connection() as conn:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def _vector_hits(query_embedding: list[float], limit: int, video_path: str | None) -> list[dict]:
    if video_path:
        # Exact scan over one file. HNSW would filter after picking neighbors.
        sql = """
            WITH scoped AS MATERIALIZED (
                SELECT id, video_path, timestamp_seconds, caption, embedding
                FROM footage_segments
                WHERE video_path = %s
            )
            SELECT id, video_path, timestamp_seconds, caption,
                   embedding <=> %s AS distance
            FROM scoped
            ORDER BY distance
            LIMIT %s
        """
        params: tuple = (video_path, Vector(query_embedding), limit)
        with _require_pool().connection() as conn:
            cur = conn.execute(sql, params)
            return [dict(row) for row in cur.fetchall()]

    sql = """
        SELECT id, video_path, timestamp_seconds, caption,
               embedding <=> %s AS distance
        FROM footage_segments
        ORDER BY embedding <=> %s
        LIMIT %s
    """
    params = (Vector(query_embedding), Vector(query_embedding), limit)
    try:
        with _require_pool().connection() as conn:
            with conn.transaction():
                conn.execute("SET LOCAL hnsw.iterative_scan = relaxed_order")
                cur = conn.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]
    except psycopg.Error as exc:
        if "iterative_scan" not in str(exc):
            raise
        logger.info("hnsw.iterative_scan is unavailable; searching without it")
    with _require_pool().connection() as conn:
        cur = conn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
