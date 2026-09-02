"""The job: one room, one listener, one story."""

import json
import logging

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer, JobContext

from narrator.audio import play, publish_voice
from narrator.render import stream_text
from narrator.content import load_story, load_voice

load_dotenv()
logger = logging.getLogger("narrator")

server = AgentServer(num_idle_processes=1)


@server.rtc_session()
async def entrypoint(ctx: JobContext) -> None:
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
