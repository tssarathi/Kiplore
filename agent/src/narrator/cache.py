"""Renders in R2, named by everything that shaped them."""

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
    return f"renders/{collection}/{story_id}/{voice_id}/{render}"


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


def _load(at: str) -> tuple[bytes, Timings] | None:
    client = _client()
    raw = _get(client, f"{at}/{TIMINGS}")
    if raw is None:
        return None
    meta = json.loads(raw)
    audio = _get(client, f"{at}/{meta['audio']}")
    if audio is None:
        raise ValueError(f"{meta['audio']} is missing")
    if len(audio) != meta["bytes"]:
        raise ValueError("render audio does not match its timings")
    return audio, Timings(meta["segments"], meta["chunk_timings"])


async def load(at: str) -> tuple[bytes, Timings] | None:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_load, at), CACHE_RESOLVE_SECONDS
        )
    except TimeoutError:
        logger.warning(f"render lookup timed out at={at}")
        return None
    except (*REMOTE_ERRORS, ValueError, KeyError, TypeError) as error:
        logger.warning(f"cached render unusable at={at} reason={error}")
        return None


def _save(at: str, pcm: bytes, timings: Timings, spoken: str) -> str | None:
    reason = qc.inspect(pcm, spoken, timings.segments)
    if reason is not None:
        return reason
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
    try:
        return await asyncio.to_thread(_save, at, pcm, timings, spoken)
    except REMOTE_ERRORS as error:
        return f"upload failed: {error}"
