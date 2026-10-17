"""Temporal activities for one index job.

Discover, extract, and caption-and-store run before the ElevenLabs activity.
Caption-and-store is a single activity. It heartbeats a frame cursor so a
retry continues mid-clip. One activity per frame would fill the workflow
history on a long card (fpolster, "Long-running jobs in Temporal.io").
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError

import db
from captions import CAPTION_MODEL, caption_frame
from embeddings import embed_text
from frames import extract_frames, list_videos
from notify_voice import VoiceError, synthesize_and_play


@activity.defn(name="discover_videos")
async def discover_videos(job: dict) -> list[str]:
    """Resolve the dropzone path to video files on this machine."""
    try:
        videos = list_videos(Path(job["path"]))
    except ValueError as exc:
        raise ApplicationError(str(exc), non_retryable=True) from exc
    paths = [str(video.resolve()) for video in videos]
    await db.update_job(job["workflow_id"], status="discovered", frames_seen=0)
    return paths


@activity.defn(name="extract_frames")
async def extract_frames_activity(job: dict) -> list[dict]:
    """Sample frames sparsely. ffmpeg when present, timestamps otherwise."""
    frames: list[dict] = []
    for video_path in job["videos"]:
        frames.extend(extract_frames(Path(video_path), job["workflow_id"]))
    await db.update_job(
        job["workflow_id"],
        status="extracted",
        frames_seen=len(frames),
    )
    return frames


@activity.defn(name="caption_and_store")
async def caption_and_store(job: dict) -> dict:
    """Caption every pending frame, embed it locally, and upsert pgvector.

    Heartbeat detail is the next frame index. After a worker crash, Temporal
    reruns this activity and the loop starts at that index. Completed rows
    are already in TimescaleDB, so the retry does not redo them.
    """
    frames: list[dict] = job["frames"]
    start_index = 0
    details = activity.info().heartbeat_details
    if details:
        start_index = int(details[0])

    for index in range(start_index, len(frames)):
        frame = frames[index]
        caption = caption_frame(
            frame["video_path"],
            float(frame["timestamp_seconds"]),
            frame.get("image_path"),
        )
        embedding = embed_text(caption)
        await db.upsert_segment(
            frame["video_path"],
            float(frame["timestamp_seconds"]),
            caption,
            embedding,
        )
        done = index + 1
        activity.heartbeat(done)
        await db.update_job(
            job["workflow_id"],
            status="captioning",
            frames_seen=len(frames),
            frames_captioned=done,
            caption_model=CAPTION_MODEL,
        )

    await db.update_job(
        job["workflow_id"],
        status="indexed",
        frames_seen=len(frames),
        frames_captioned=len(frames),
        caption_model=CAPTION_MODEL,
    )
    return {"frames_captioned": len(frames), "caption_model": CAPTION_MODEL}


@activity.defn(name="notify_complete")
async def notify_complete(job: dict) -> dict:
    """Speak one completion sentence. A missing key fails this activity only."""
    count = int(job.get("frames_captioned") or 0)
    sentence = f"Your footage is indexed. {count} moments are ready to search."
    try:
        # httpx and the local player are blocking. Running them on the loop
        # stalls workflow tasks (Temporal warning TMPRL1104).
        result = await asyncio.to_thread(synthesize_and_play, sentence, job["workflow_id"])
    except VoiceError as exc:
        await db.update_job(job["workflow_id"], voice_played=False, voice_error=str(exc))
        raise ApplicationError(str(exc), non_retryable=True) from exc
    await db.update_job(
        job["workflow_id"],
        status="complete" if result["played"] else "indexed",
        voice_played=bool(result["played"]),
        voice_error=result["play_error"],
    )
    return result
