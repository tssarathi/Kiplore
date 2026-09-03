"""Renders in R2, named by everything that shaped them.

Synthesis is the slow and costly part of starting a story, and the same script in the
same voice always sounds the same, so a render is worth keeping. Audio and timings are
stored together: recovering the timings would mean synthesising again.
"""

import asyncio
import hashlib
import json
import logging
import os

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from narrator import qc
from narrator.alignment import Timings
from narrator.config import (
    CACHE_CONNECT_SECONDS,
    CACHE_READ_SECONDS,
    CACHE_RESOLVE_SECONDS,
    CHUNK_GAP_SECONDS,
    ELEVEN_MODEL,
    OUTPUT_FORMAT,
    PIPELINE_VERSION,
    SEED,
    VOICE_SETTINGS,
)

logger = logging.getLogger("narrator")

REMOTE_ERRORS = (ClientError, BotoCoreError, OSError)
TIMINGS = "timings.json"

CLIENT_CONFIG = Config(
    connect_timeout=CACHE_CONNECT_SECONDS,
    read_timeout=CACHE_READ_SECONDS,
    retries={"mode": "standard", "total_max_attempts": 3},
)


def _client():
    account = os.environ["R2_ACCOUNT_ID"]
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
        config=CLIENT_CONFIG,
    )


def render_id(story: dict, eleven_id: str) -> str:
    """A short hash of everything that changes how a story sounds.

    Because every such input is in the hash, an edit anywhere yields a new id and the
    stale render is simply never asked for again. Nothing is ever invalidated by hand.
    """
    identity = {
        "script": story["script"],
        "voice_id": eleven_id,
        "model": ELEVEN_MODEL,
        "output_format": OUTPUT_FORMAT,
        "voice_settings": VOICE_SETTINGS,
        "seed": SEED,
        "chunk_gap": CHUNK_GAP_SECONDS,
        "pipeline_version": PIPELINE_VERSION,
    }
    canonical = json.dumps(identity, sort_keys=True).encode()
    return hashlib.sha256(canonical).hexdigest()[:16]


def prefix(collection: str, story_id: str, voice_id: str, render: str) -> str:
    """Where one render lives in the bucket."""
    return f"library/{collection}/{story_id}/{voice_id}/{render}"


def _get(client, key: str) -> bytes | None:
    try:
        return client.get_object(Bucket=os.environ["R2_BUCKET"], Key=key)["Body"].read()
    except client.exceptions.NoSuchKey:
        return None


def _put(client, key: str, body: bytes, content_type: str) -> None:
    client.put_object(
        Bucket=os.environ["R2_BUCKET"],
        Key=key,
        Body=body,
        ContentType=content_type,
    )


def _resolve(at: str) -> dict | None:
    raw = _get(_client(), f"{at}/{TIMINGS}")
    return None if raw is None else json.loads(raw)


def _fetch(at: str, meta: dict) -> tuple[bytes, Timings]:
    """Read the audio a metadata record points at, and check it is intact."""
    audio = _get(_client(), f"{at}/{meta['audio']}")
    if audio is None:
        raise ValueError(f"{meta['audio']} is missing")
    # A length mismatch means a half-written upload; better to re-render than to play
    # a story that stops early.
    if len(audio) != meta["bytes"]:
        raise ValueError("render audio does not match its timings")
    return audio, Timings(meta["segments"], meta["chunk_timings"])


async def load(at: str) -> tuple[bytes, Timings] | None:
    """A cached render, or None for anything that makes it unusable.

    Every failure is swallowed: a miss only costs a live render, so nothing here is
    worth failing a story over.
    """
    try:
        # Only the small metadata read is on the short timeout, since it is what the
        # child is waiting on. Fetching the audio may take as long as it needs.
        meta = await asyncio.wait_for(
            asyncio.to_thread(_resolve, at), CACHE_RESOLVE_SECONDS
        )
        if meta is None:
            return None
        return await asyncio.to_thread(_fetch, at, meta)
    except TimeoutError:
        logger.warning(f"render lookup timed out at={at}")
        return None
    except (*REMOTE_ERRORS, ValueError, KeyError, TypeError) as error:
        logger.warning(f"cached render unusable at={at} reason={error}")
        return None


def _save(at: str, pcm: bytes, timings: Timings, spoken: str) -> str | None:
    """Quality check a render, then upload the audio and its metadata."""
    reason = qc.inspect(pcm, spoken, timings.segments, timings.chunk_timings)
    if reason is not None:
        return reason
    # Metadata is written last and names the audio object, so a reader that finds
    # timings knows the audio behind them finished uploading.
    client = _client()
    audio = f"audio-{hashlib.sha256(pcm).hexdigest()[:12]}.pcm"
    _put(client, f"{at}/{audio}", pcm, "application/octet-stream")
    _put(
        client,
        f"{at}/{TIMINGS}",
        json.dumps(
            {
                "audio": audio,
                "bytes": len(pcm),
                "segments": timings.segments,
                "chunk_timings": timings.chunk_timings,
            }
        ).encode(),
        "application/json",
    )
    return None


async def save(at: str, pcm: bytes, timings: Timings, spoken: str) -> str | None:
    """Store a render, returning the reason it was not stored, or None on success."""
    try:
        return await asyncio.to_thread(_save, at, pcm, timings, spoken)
    except REMOTE_ERRORS as error:
        return f"upload failed: {error}"
