"""The job: one room, one listener, one story."""

import asyncio
import itertools
import json
import logging

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import AgentServer, JobContext

from narrator.alignment import chunk_start, heard_text, segment_at
from narrator.answer import write_answer
from narrator.audio import (
    discard_queued,
    fill,
    play,
    publish_voice,
    seconds_to_bytes,
    speak_reply,
)
from narrator.config import (
    RESUME_BREATH_SECONDS,
    RESUME_FADE_FROM,
    RESUME_FADE_SECONDS,
)
from narrator.content import load_story, load_voice
from narrator.envelope import GainRamp
from narrator.listen import Listener
from narrator.player import Player
from narrator.render import Narration, stream_answer
from narrator.session import Phase, Session

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer(num_idle_processes=1)


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
    spoke = asyncio.Event()
    questions: asyncio.Queue[str | None] = asyncio.Queue()
    player = Player()
    ramp = GainRamp()
    acks: set[asyncio.Task[None]] = set()

    await ctx.connect()
    source = await publish_voice(ctx)
    session = Session(source, player, playing, paused, spoke, questions, ramp)

    def publish_ack(seq: int) -> None:
        payload = json.dumps({"type": "resume-ack", "seq": seq})
        task = asyncio.create_task(
            ctx.room.local_participant.publish_data(payload, reliable=True)
        )
        acks.add(task)
        task.add_done_callback(acks.discard)

    @ctx.room.on("data_received")
    def on_control(packet: rtc.DataPacket) -> None:
        control = json.loads(packet.data)
        logger.info(f"control {control}")
        action = control["action"]
        if action == "resume-at":
            seq = session.report(
                control["seq"], control["position"], control["paused"]
            )
            if seq is not None:
                publish_ack(seq)
            return
        if session.phase is not Phase.ACTIVE:
            return
        if action == "pause":
            paused.clear()
        elif action == "resume":
            paused.set()
        elif action == "seek":
            player.seek(seconds_to_bytes(control["offset"]))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant) -> None:
        session.dropped(participant.disconnect_reason)

    @ctx.room.on("participant_connected")
    def on_participant_connected(_: rtc.RemoteParticipant) -> None:
        session.rejoined()

    listener = await ctx.wait_for_participant()
    request = json.loads(listener.metadata)
    story = load_story(request["collection"], request["storyId"])
    voice = load_voice(request["voiceId"])

    logger.info(
        f"listener={listener.identity} story={story['title']!r} voice={voice['name']}"
    )

    ears = Listener(story["script"], playing, spoke, questions, ramp)
    ctx.room.on("track_subscribed", lambda track, *_: ears.add_microphone(track))
    for publication in listener.track_publications.values():
        if publication.track is not None:
            ears.add_microphone(publication.track)

    narration = Narration(story, voice["elevenLabsId"])
    producer = asyncio.create_task(fill(player, narration.stream()))
    broadcaster = asyncio.create_task(broadcast(ctx, player, narration, paused))

    try:
        while True:
            await session.ready()
            if session.phase is Phase.LEFT:
                break
            playing.set()
            await play(source, player, playing, paused, ramp)
            if playing.is_set():
                break
            logger.info(f"rewound {discard_queued(source, player):.2f}s of queued audio")

            while question := await questions.get():
                heard = heard_text(
                    story["script"],
                    narration.segments,
                    narration.chunk_timings,
                    player.position,
                )
                answer = await write_answer(story["title"], heard, question)
                logger.info(f"answering {answer!r}")
                replied = await speak_reply(
                    source, stream_answer(answer, voice["elevenLabsId"]), spoke
                )
                if replied:
                    break
                logger.info("answer interrupted")
            if question is None:
                continue

            await asyncio.sleep(RESUME_BREATH_SECONDS)
            player.seek(
                seconds_to_bytes(
                    resume_point(narration, player.position) - player.position
                )
            )
            ramp.snap(RESUME_FADE_FROM)
            ramp.set(1.0, RESUME_FADE_SECONDS)

        if session.phase is not Phase.LEFT:
            await producer
            logger.info("story finished")
    finally:
        session.close()
        producer.cancel()
        broadcaster.cancel()
        await ears.aclose()
        await asyncio.gather(producer, broadcaster, return_exceptions=True)
        await ctx.delete_room()


if __name__ == "__main__":
    agents.cli.run_app(server)
