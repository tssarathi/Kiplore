"""Turning story text into the narrator's voice."""

import os
from collections.abc import AsyncIterator

import aiohttp

from narrator.config import (
    ELEVEN_MODEL,
    OUTPUT_FORMAT,
    SEED,
    VOICE_ID,
    VOICE_SETTINGS,
)


async def stream_text(text: str) -> AsyncIterator[bytes]:
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            params={"output_format": OUTPUT_FORMAT},
            headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"]},
            json={
                "text": text,
                "model_id": ELEVEN_MODEL,
                "voice_settings": VOICE_SETTINGS,
                "seed": SEED,
            },
        ) as response:
            if response.status != 200:
                detail = (await response.content.read(200)).decode(errors="replace")
                raise RuntimeError(f"synthesis failed, HTTP {response.status}: {detail}")
            async for chunk in response.content.iter_any():
                yield chunk
