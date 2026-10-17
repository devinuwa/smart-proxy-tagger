"""IndexFootageWorkflow — durable path from a local folder to searchable rows.

The API starts this workflow and returns. Closing the UI does not stop it.
Activities are referenced by name so this module stays free of database and
HTTP imports (Temporal replays the workflow in a sandbox).
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

TASK_QUEUE = "smart-proxy-tagger"

_SHORT = timedelta(minutes=2)
_CAPTION = timedelta(hours=6)
# Heartbeat at least this often. The activity beats once per frame, so a
# stuck caption call is retried without losing earlier frames.
_HEARTBEAT = timedelta(minutes=5)


@workflow.defn
class IndexFootageWorkflow:
    def __init__(self) -> None:
        self._progress = {
            "status": "queued",
            "frames_seen": 0,
            "frames_captioned": 0,
            "voice_played": False,
            "voice_error": None,
        }

    @workflow.query
    def progress(self) -> dict:
        return self._progress

    @workflow.run
    async def run(self, job: dict) -> dict:
        self._progress["status"] = "discovering"
        videos = await workflow.execute_activity(
            "discover_videos",
            job,
            start_to_close_timeout=_SHORT,
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        self._progress["status"] = "extracting"
        frames = await workflow.execute_activity(
            "extract_frames",
            {**job, "videos": videos},
            start_to_close_timeout=_SHORT,
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
        self._progress["frames_seen"] = len(frames)

        self._progress["status"] = "captioning"
        stored = await workflow.execute_activity(
            "caption_and_store",
            {**job, "frames": frames},
            start_to_close_timeout=_CAPTION,
            heartbeat_timeout=_HEARTBEAT,
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
        self._progress["frames_captioned"] = stored["frames_captioned"]
        self._progress["status"] = "indexed"

        # Voice is its own activity so a TTS failure retries the sentence
        # and does not re-caption the footage.
        try:
            voice = await workflow.execute_activity(
                "notify_complete",
                {**job, "frames_captioned": stored["frames_captioned"]},
                start_to_close_timeout=_SHORT,
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
        except ActivityError as exc:
            self._progress["voice_played"] = False
            self._progress["voice_error"] = str(exc.cause) if exc.cause else str(exc)
            self._progress["status"] = "indexed"
            return self._progress

        self._progress["voice_played"] = bool(voice.get("played"))
        self._progress["voice_error"] = voice.get("play_error")
        self._progress["status"] = "complete" if voice.get("played") else "indexed"
        return self._progress
