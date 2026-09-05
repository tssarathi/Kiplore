import asyncio
from typing import ClassVar, cast

from livekit import rtc
from livekit.agents import stt
from livekit.agents.language import LanguageCode
from livekit.agents.stt import SpeechEventType

import narrator.listen
from narrator.envelope import GainRamp
from narrator.listen import Listener


class FakeStream:
    def __init__(self, events: list[stt.SpeechEvent]) -> None:
        self._events = events

    def __aiter__(self):
        return self

    async def __anext__(self) -> stt.SpeechEvent:
        if not self._events:
            await asyncio.sleep(3600)
        return self._events.pop(0)

    def push_frame(self, _: object) -> None:
        pass

    async def aclose(self) -> None:
        pass


class FakeSTT:
    events: ClassVar[list[stt.SpeechEvent]] = []

    def __init__(self, **_: object) -> None:
        pass

    def stream(self) -> FakeStream:
        return FakeStream(list(self.events))

    async def aclose(self) -> None:
        pass


def final(text: str) -> stt.SpeechEvent:
    return stt.SpeechEvent(
        type=SpeechEventType.FINAL_TRANSCRIPT,
        alternatives=[stt.SpeechData(language=LanguageCode("en"), text=text)],
    )


def test_a_final_transcript_with_no_interim_before_it_still_stops_the_story(
    monkeypatch,
):
    async def scenario() -> None:
        FakeSTT.events = [final("Why?")]
        monkeypatch.setattr(narrator.listen.deepgram, "STTv2", FakeSTT)
        playing, paused, spoke = asyncio.Event(), asyncio.Event(), asyncio.Event()
        playing.set()
        paused.set()
        questions: asyncio.Queue[str | None] = asyncio.Queue()
        ears = Listener(
            ["Once."],
            cast(rtc.Room, object()),
            "kid",
            playing,
            paused,
            spoke,
            questions,
            GainRamp(),
        )
        try:
            question = await asyncio.wait_for(questions.get(), 2)
            assert question == "Why?"
            assert not playing.is_set(), "the story kept going over the question"
            assert spoke.is_set()
        finally:
            await ears.aclose()

    asyncio.run(scenario())
