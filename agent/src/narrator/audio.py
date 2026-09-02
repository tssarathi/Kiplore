"""Making sound: generating it, and sending it into the room."""

import array
import math

from livekit import rtc
from livekit.agents import JobContext

from narrator.config import FRAME_SAMPLES, NUM_CHANNELS, SAMPLE_RATE


async def publish_voice(ctx: JobContext) -> rtc.AudioSource:
    source = rtc.AudioSource(SAMPLE_RATE, NUM_CHANNELS)
    track = rtc.LocalAudioTrack.create_audio_track("narrator-voice", source)
    await ctx.room.local_participant.publish_track(track)
    return source


async def play(source: rtc.AudioSource, pcm: bytes) -> None:
    frame_bytes = FRAME_SAMPLES * 2
    for start in range(0, len(pcm) - frame_bytes + 1, frame_bytes):
        frame = rtc.AudioFrame(
            pcm[start : start + frame_bytes], SAMPLE_RATE, NUM_CHANNELS, FRAME_SAMPLES
        )
        await source.capture_frame(frame)


def tone(seconds: float, hz: float = 440.0) -> bytes:
    samples = array.array("h")
    for i in range(int(SAMPLE_RATE * seconds)):
        samples.append(int(10000 * math.sin(2 * math.pi * hz * i / SAMPLE_RATE)))
    return samples.tobytes()
