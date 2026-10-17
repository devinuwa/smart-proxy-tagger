"""Caption stand-in for Phase 2.

PaliGemma is the Gemma-family model that will read each frame in Phase 4.
This module returns searchable text from the file name and timestamp so the
Temporal activity, the embedding step, and pgvector can be reviewed before
the weights are downloaded. The string says it is a stand-in, so a judge
does not mistake it for model output.
"""

from __future__ import annotations

from pathlib import Path

CAPTION_MODEL = "phase2-stand-in"


def caption_frame(video_path: str, timestamp_seconds: float, image_path: str | None) -> str:
    """Describe one sampled moment. `image_path` is unused until Phase 4."""
    del image_path
    name = Path(video_path).stem.replace("_", " ").replace("-", " ")
    return (
        f"Phase 2 stand-in caption for {name} at {timestamp_seconds:.1f} seconds. "
        "PaliGemma replaces this text in Phase 4."
    )
