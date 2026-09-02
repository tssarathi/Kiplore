"""The job: one room, one listener, one story."""

import asyncio
import json
import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, JobContext
from livekit.agents.stt import SpeechEventType
from livekit.plugins import deepgram

from narrator.audio import play, publish_voice
from narrator.render import stream_text
from narrator.content import load_story, load_voice

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer(num_idle_processes=1)


async def transcribe(track: rtc.Track) -> None:
    stream = deepgram.STT().stream()

    async def read_transcripts() -> None:
        async for event in stream:
            if event.type == SpeechEventType.FINAL_TRANSCRIPT:
                logger.info(f"heard {event.alternatives[0].text!r}")

    reader = asyncio.create_task(read_transcripts())
    async for audio in rtc.AudioStream(track):
        stream.push_frame(audio.frame)
    stream.end_input()
    await reader


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    listening: list[asyncio.Task] = []

    @ctx.room.on("track_subscribed")
    def on_track(track: rtc.Track, *_: object) -> None:
        listening.append(asyncio.create_task(transcribe(track)))

    await ctx.connect()
    source = await publish_voice(ctx)

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    await play(source, stream_text(story["script"][0], voice["elevenLabsId"]))
    logger.info("paragraph finished")


if __name__ == "__main__":
    agents.cli.run_app(server)
