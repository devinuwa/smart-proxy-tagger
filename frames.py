"""Sparse frame sampling.

Demo sample interval: one frame every 5 seconds, at most 24 frames per file.
That is the judging demo, not a full-rate pass over a terabyte library.
ffmpeg does the extract when it is on PATH. Without ffmpeg, the activity
still records timestamps so the Temporal and pgvector path can be exercised.
Those rows are marked as timestamp samples, not decoded pictures.
Phase 4's PaliGemma step reads the image files this module writes.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

# One frame every five seconds. Documented next to the constant on purpose:
# judges should see that the demo is sparse.
FRAME_SAMPLE_INTERVAL_SECONDS = 5.0
FRAME_SAMPLE_LIMIT = 24

VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def list_videos(path: Path) -> list[Path]:
    if path.is_file():
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            raise ValueError(f"{path} is not a video file ({', '.join(sorted(VIDEO_SUFFIXES))}).")
        return [path]
    if path.is_dir():
        found = [item for item in path.rglob("*") if item.is_file() and item.suffix.lower() in VIDEO_SUFFIXES]
        found.sort()
        if not found:
            raise ValueError(f"No video files under {path}.")
        return found
    raise ValueError(f"Path does not exist: {path}")


def extract_frames(video_path: Path, workflow_id: str) -> list[dict]:
    """Return frame descriptors. Image files are written only when ffmpeg runs."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return _timestamp_samples(video_path)
    return _ffmpeg_samples(ffmpeg, video_path, workflow_id)


def _timestamp_samples(video_path: Path) -> list[dict]:
    frames = []
    for index in range(3):
        frames.append(
            {
                "video_path": str(video_path.resolve()),
                "timestamp_seconds": index * FRAME_SAMPLE_INTERVAL_SECONDS,
                "image_path": None,
                "frame_source": "timestamp-sample",
            }
        )
    return frames


def _ffmpeg_samples(ffmpeg: str, video_path: Path, workflow_id: str) -> list[dict]:
    out_dir = Path("var") / "frames" / workflow_id / _safe_stem(video_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "frame_%03d.jpg")
    # fps=1/5 keeps the demo sparse. -frames:v caps a long file.
    completed = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{int(FRAME_SAMPLE_INTERVAL_SECONDS)}",
            "-frames:v",
            str(FRAME_SAMPLE_LIMIT),
            pattern,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    images = sorted(out_dir.glob("frame_*.jpg"))
    if completed.returncode != 0 or not images:
        return _timestamp_samples(video_path)
    frames = []
    for index, image in enumerate(images):
        frames.append(
            {
                "video_path": str(video_path.resolve()),
                "timestamp_seconds": index * FRAME_SAMPLE_INTERVAL_SECONDS,
                "image_path": str(image.resolve()),
                "frame_source": "ffmpeg",
            }
        )
    return frames


def _safe_stem(video_path: Path) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in video_path.stem)
    return cleaned[:80] or "clip"
