"""Local caption embeddings for pgvector.

Phase 2 hashes tokens into a fixed 384-dimensional vector so search works
offline, with no model download. The dimension matches all-MiniLM-L6-v2.
Phase 4 replaces `embed_text` with that model. The two spaces are different,
so rows written by this stand-in must be re-embedded when the model arrives.
Nothing here calls a hosted embedding API.
"""

from __future__ import annotations

import hashlib
import math
import re

# Same width as sentence-transformers all-MiniLM-L6-v2, the Phase 4 model.
EMBEDDING_DIMENSIONS = 384

_TOKEN = re.compile(r"[a-z0-9]+")


def embed_text(text: str) -> list[float]:
    """Bag-of-tokens vector. Shared words pull a query and a caption together."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    tokens = _TOKEN.findall(text.lower())
    if not tokens:
        vector[0] = 1.0
        return vector
    for token in tokens:
        digest = hashlib.blake2s(token.encode("utf-8"), digest_size=8).digest()
        bucket = int.from_bytes(digest[:4], "little") % EMBEDDING_DIMENSIONS
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[bucket] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        vector[0] = 1.0
        return vector
    return [value / norm for value in vector]
