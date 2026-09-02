"""The job: one room, one listener, one story."""

import asyncio
import json
import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, JobContext
from livekit.agents.stt import SpeechEventType
from livekit.plugins import deepgram

from narrator.answer import write_answer
from narrator.audio import discard_queued, fill, play, publish_voice, speak
from narrator.player import Player
from narrator.render import stream_text
from narrator.content import load_story, load_voice

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer(num_idle_processes=1)


async def transcribe(
    track: rtc.Track, playing: asyncio.Event, questions: asyncio.Queue[str]
) -> None:
    stream = deepgram.STT().stream()

    async def read_transcripts() -> None:
        async for event in stream:
            if not event.alternatives or not event.alternatives[0].text:
                continue
            text = event.alternatives[0].text
            if event.type == SpeechEventType.INTERIM_TRANSCRIPT and playing.is_set():
                playing.clear()
                logger.info("narration stopped")
            elif event.type == SpeechEventType.FINAL_TRANSCRIPT:
                logger.info(f"heard {text!r}")
                questions.put_nowait(text)

    reader = asyncio.create_task(read_transcripts())
    async for audio in rtc.AudioStream(track):
        stream.push_frame(audio.frame)
    stream.end_input()
    await reader


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    playing = asyncio.Event()
    questions: asyncio.Queue[str] = asyncio.Queue()
    listening: list[asyncio.Task] = []

    @ctx.room.on("track_subscribed")
    def on_track(track: rtc.Track, *_: object) -> None:
        listening.append(asyncio.create_task(transcribe(track, playing, questions)))

    await ctx.connect()
    source = await publish_voice(ctx)

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    paragraph = story["script"][0]
    eleven_id = voice["elevenLabsId"]

    player = Player()
    producer = asyncio.create_task(fill(player, stream_text(paragraph, eleven_id)))

    while True:
        playing.set()
        await play(source, player, playing)
        if playing.is_set():
            break
        logger.info(f"rewound {discard_queued(source, player):.2f}s of queued audio")

        question = await questions.get()
        answer = await write_answer(story["title"], paragraph, question)
        logger.info(f"answering {answer!r}")
        await speak(source, stream_text(answer, eleven_id))

    await producer
    logger.info("paragraph finished")


if __name__ == "__main__":
    agents.cli.run_app(server)
