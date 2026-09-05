import asyncio
from collections.abc import AsyncIterator

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import (
    CHUNK_SECONDS,
    PAUSE_FADE_SECONDS,
    SAMPLE_RATE,
    SOURCE_QUEUE_MS,
)
from narrator.envelope import GainRamp, scale
from narrator.player import Player

FRAME_SAMPLES = int(SAMPLE_RATE * CHUNK_SECONDS)
FRAME_BYTES = FRAME_SAMPLES * 2


def seconds_to_bytes(seconds: float) -> int:
    return round(seconds * SAMPLE_RATE) * 2


def discard_queued(source: rtc.AudioSource, player: Player) -> float:
    queued = source.queued_duration
    source.clear_queue()
    player.seek(-seconds_to_bytes(queued))
    return queued


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    source = rtc.AudioSource(SAMPLE_RATE, 1, queue_size_ms=SOURCE_QUEUE_MS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    await ctx.room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    )
    return source


def frame(pcm: bytes) -> rtc.AudioFrame:
    return rtc.AudioFrame(pcm, SAMPLE_RATE, 1, FRAME_SAMPLES)


async def once(pcm: bytes) -> AsyncIterator[bytes]:
    yield pcm


async def play(
    source: rtc.AudioSource,
    player: Player,
    playing: asyncio.Event,
    paused: asyncio.Event,
    ramp: GainRamp,
    producer: asyncio.Task[None],
) -> None:
    captured = False
    while True:
        if not (playing.is_set() and paused.is_set()) and ramp.target != 0.0:
            if captured:
                ramp.set(0.0, PAUSE_FADE_SECONDS)
            else:
                ramp.snap(0.0)
        if ramp.gain == 0.0:
            if not playing.is_set():
                return

            discard_queued(source, player)
            while not paused.is_set() and playing.is_set():
                await asyncio.sleep(CHUNK_SECONDS)
            if not playing.is_set():
                return
            ramp.resume()
        pcm = player.read(FRAME_BYTES)
        if pcm is None:
            if player.finished:
                return

            if producer.done():
                producer.result()
            ramp.step(CHUNK_SECONDS)
            await asyncio.sleep(CHUNK_SECONDS)
            continue

        await source.capture_frame(frame(scale(pcm, ramp.step(CHUNK_SECONDS))))
        captured = True


async def speak_reply(
    source: rtc.AudioSource, chunks: AsyncIterator[bytes], spoke: asyncio.Event
) -> bool:
    spoke.clear()
    speaking = asyncio.create_task(speak(source, chunks))
    interrupt = asyncio.create_task(spoke.wait())
    done, _ = await asyncio.wait(
        {speaking, interrupt}, return_when=asyncio.FIRST_COMPLETED
    )
    if speaking in done:
        interrupt.cancel()
        await speaking
        return True
    speaking.cancel()
    source.clear_queue()
    await asyncio.gather(speaking, return_exceptions=True)
    source.clear_queue()
    return False


async def speak(source: rtc.AudioSource, chunks: AsyncIterator[bytes]) -> None:
    buffer = bytearray()
    async for chunk in chunks:
        buffer += chunk
        while len(buffer) >= FRAME_BYTES:
            pcm = bytes(buffer[:FRAME_BYTES])
            del buffer[:FRAME_BYTES]
            await source.capture_frame(frame(pcm))
