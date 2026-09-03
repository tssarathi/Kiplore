"""Renders on disk, named by everything that shaped them."""

import hashlib
import json
import logging
import os

from narrator import qc
from narrator.alignment import Timings
from narrator.config import (
    CHUNK_GAP_SECONDS,
    ELEVEN_MODEL,
    OUTPUT_FORMAT,
    PIPELINE_VERSION,
    RENDER_DIR,
    SEED,
    VOICE_SETTINGS,
)

logger = logging.getLogger("narrator")


def render_id(story: dict, voice_id: str) -> str:
    identity = {
        "script": story["script"],
        "voice_id": voice_id,
        "model": ELEVEN_MODEL,
        "output_format": OUTPUT_FORMAT,
        "voice_settings": VOICE_SETTINGS,
        "seed": SEED,
        "chunk_gap": CHUNK_GAP_SECONDS,
        "pipeline_version": PIPELINE_VERSION,
    }
    canonical = json.dumps(identity, sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def load(rid: str) -> tuple[bytes, Timings] | None:
    try:
        meta = json.loads((RENDER_DIR / f"{rid}.json").read_bytes())
        pcm = (RENDER_DIR / f"{rid}.pcm").read_bytes()
        if len(pcm) != meta["bytes"]:
            raise ValueError("render audio does not match its timings")
        return pcm, Timings(meta["segments"], meta["chunk_timings"])
    except (OSError, ValueError, KeyError, TypeError) as error:
        if not isinstance(error, FileNotFoundError):
            logger.warning(f"cached render unusable render={rid} reason={error}")
        return None


def _write(name: str, data: bytes) -> None:
    temporary = RENDER_DIR / f"{name}.part"
    temporary.write_bytes(data)
    os.replace(temporary, RENDER_DIR / name)


def save(rid: str, pcm: bytes, timings: Timings, spoken: str) -> str | None:
    reason = qc.inspect(pcm, spoken, timings.segments)
    if reason is not None:
        return reason
    RENDER_DIR.mkdir(parents=True, exist_ok=True)
    _write(f"{rid}.pcm", pcm)
    _write(
        f"{rid}.json",
        json.dumps(
            {
                "bytes": len(pcm),
                "segments": timings.segments,
                "chunk_timings": timings.chunk_timings,
            }
        ).encode(),
    )
    return None
