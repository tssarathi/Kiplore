"""Hearing the child: energy for ducking, Flux for turns."""

import array
import asyncio
import logging
import math

from livekit import rtc
from livekit.agents import APIConnectOptions
from livekit.agents.stt import SpeechEventType
from livekit.plugins import deepgram, noise_cancellation

from narrator.alignment import keyterms
from narrator.config import (
    DUCK_ATTACK_SECONDS,
    DUCK_DECAY_SECONDS,
    DUCK_FRAMES,
    DUCK_RELEASE_SECONDS,
    DUCK_RMS,
    DUCK_VOLUME,
    EOT_THRESHOLD,
)
from narrator.envelope import GainRamp

logger = logging.getLogger("narrator")

CALL_OPTIONS = APIConnectOptions(max_retry=0, timeout=10.0)
MIC_FRAME_CAPACITY = 100


class Listener:
    def __init__(
        self,
        script: list[str],
        playing: asyncio.Event,
        spoke: asyncio.Event,
        questions: asyncio.Queue[str | None],
        ramp: GainRamp,
    ) -> None:
        self._stt = deepgram.STTv2(
            keyterm=keyterms(script), eot_threshold=EOT_THRESHOLD
        )
        self._stream = self._stt.stream(conn_options=CALL_OPTIONS)
        self._playing = playing
        self._spoke = spoke
        self._questions = questions
        self._ramp = ramp
        self._loud = 0
        self._quiet = 0.0
        self._ducked = False
        self._tasks: list[asyncio.Task[None]] = [asyncio.create_task(self._read())]

    def add_microphone(self, track: rtc.Track) -> None:
        self._tasks.append(asyncio.create_task(self._forward(track)))

    async def aclose(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        await self._stream.aclose()
        await self._stt.aclose()

    async def _forward(self, track: rtc.Track) -> None:
        stream = rtc.AudioStream(
            track,
            capacity=MIC_FRAME_CAPACITY,
            noise_cancellation=noise_cancellation.NC(),
        )
        try:
            async for event in stream:
                self._gate(event.frame)
                self._stream.push_frame(event.frame)
        finally:
            await stream.aclose()

    def _gate(self, frame: rtc.AudioFrame) -> None:
        samples = array.array("h", bytes(frame.data))
        if not samples:
            return
        rms = math.sqrt(sum(s * s for s in samples) / len(samples)) / 32768
        seconds = len(samples) / frame.sample_rate / frame.num_channels
        if rms >= DUCK_RMS:
            self._loud += 1
            self._quiet = 0.0
            if self._loud >= DUCK_FRAMES and not self._ducked:
                self._ducked = True
                self._ramp.set(DUCK_VOLUME, DUCK_ATTACK_SECONDS)
        else:
            self._loud = 0
            self._quiet += seconds
            if self._ducked and self._quiet >= DUCK_RELEASE_SECONDS:
                self._unduck()

    def _unduck(self) -> None:
        if self._ducked:
            self._ducked = False
            if self._playing.is_set():
                self._ramp.set(1.0, DUCK_DECAY_SECONDS)

    async def _read(self) -> None:
        try:
            async for event in self._stream:
                if event.type == SpeechEventType.END_OF_SPEECH:
                    self._unduck()
                    continue
                if not event.alternatives or not event.alternatives[0].text:
                    continue
                text = event.alternatives[0].text
                if event.type == SpeechEventType.INTERIM_TRANSCRIPT:
                    self._spoke.set()
                    if self._playing.is_set():
                        self._playing.clear()
                        logger.info("narration stopped")
                elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
                    logger.info(f"heard {text!r}")
                    self._questions.put_nowait(text)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("transcription failed")
            self._unduck()
            self._questions.put_nowait("")
