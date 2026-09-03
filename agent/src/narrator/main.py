"""The job: one room, one listener, one story."""

import asyncio
import itertools
import json
import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, JobContext
from livekit.agents.stt import SpeechEventType
from livekit.plugins import deepgram

from narrator.alignment import chunk_start, heard_text, segment_at
from narrator.answer import write_answer
from narrator.audio import (
    discard_queued,
    fill,
    play,
    publish_voice,
    seconds_to_bytes,
    speak,
)
from narrator.config import RESUME_FADE_FROM, RESUME_FADE_SECONDS
from narrator.content import load_story, load_voice
from narrator.envelope import GainRamp
from narrator.player import Player
from narrator.render import Narration, stream_answer

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


async def broadcast(
    ctx: JobContext, player: Player, narration: Narration, paused: asyncio.Event
) -> None:
    for seq in itertools.count(1):
        segment = segment_at(narration.segments, player.position)
        payload = json.dumps(
            {
                "seq": seq,
                "position": round(player.position, 1),
                "paused": not paused.is_set(),
                "caption": segment["text"] if segment else None,
            }
        )
        await ctx.room.local_participant.publish_data(payload, reliable=False)
        await asyncio.sleep(1)


def resume_point(narration: Narration, position: float) -> float:
    segment = segment_at(narration.segments, position)
    if segment is not None:
        return segment["start"]
    return chunk_start(narration.chunk_timings, position)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
    playing = asyncio.Event()
    paused = asyncio.Event()
    paused.set()
    questions: asyncio.Queue[str] = asyncio.Queue()
    listening: list[asyncio.Task] = []
    player = Player()

    @ctx.room.on("track_subscribed")
    def on_track(track: rtc.Track, *_: object) -> None:
        listening.append(asyncio.create_task(transcribe(track, playing, questions)))

    @ctx.room.on("data_received")
    def on_control(packet: rtc.DataPacket) -> None:
        control = json.loads(packet.data)
        logger.info(f"control {control}")
        if control["action"] == "pause":
            paused.clear()
        elif control["action"] == "resume":
            paused.set()
        elif control["action"] == "seek":
            player.seek(seconds_to_bytes(control["offset"]))

    await ctx.connect()
    source = await publish_voice(ctx)

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    narration = Narration(story, voice["elevenLabsId"])
    ramp = GainRamp()
    producer = asyncio.create_task(fill(player, narration.stream()))
    broadcaster = asyncio.create_task(broadcast(ctx, player, narration, paused))

    try:
        while True:
            playing.set()
            await play(source, player, playing, paused, ramp)
            if playing.is_set():
                break
            logger.info(f"rewound {discard_queued(source, player):.2f}s of queued audio")

            question = await questions.get()
            heard = heard_text(
                story["script"],
                narration.segments,
                narration.chunk_timings,
                player.position,
            )
            answer = await write_answer(story["title"], heard, question)
            logger.info(f"answering {answer!r}")
            await speak(source, stream_answer(answer, voice["elevenLabsId"]))

            player.seek(seconds_to_bytes(resume_point(narration, player.position) - player.position))
            ramp.snap(RESUME_FADE_FROM)
            ramp.set(1.0, RESUME_FADE_SECONDS)

        await producer
        logger.info("story finished")
    finally:
        broadcaster.cancel()
        await ctx.delete_room()


if __name__ == "__main__":
    agents.cli.run_app(server)
