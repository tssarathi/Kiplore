"""Sending sound into the room."""

import asyncio
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import FRAME_SAMPLES, NUM_CHANNELS, SAMPLE_RATE


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    await ctx.room.local_participant.publish_track(track)
    return source


async def play(
    source: rtc.AudioSource, chunks: AsyncIterator[bytes], playing: asyncio.Event
) -> None:
    frame_bytes = FRAME_SAMPLES * 2
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= frame_bytes:
            if not playing.is_set():
                return
            frame = rtc.AudioFrame(
                bytes(buffer[:frame_bytes]), SAMPLE_RATE, NUM_CHANNELS, FRAME_SAMPLES
            )
            del buffer[:frame_bytes]
            await source.capture_frame(frame)
