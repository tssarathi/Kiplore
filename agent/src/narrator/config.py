"""Every tunable value in one place."""

from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[3] / "library"

SAMPLE_RATE = 22050
NUM_CHANNELS = 1
FRAME_SAMPLES = int(SAMPLE_RATE * 0.02)

ELEVEN_MODEL = "eleven_v3"
OUTPUT_FORMAT = "pcm_22050"
SEED = 42

ANSWER_MODEL = "gpt-5.4"

ANSWER_PROMPT = """You are the storyteller reading "{title}" aloud to a small child.
The child has just interrupted you with a question.

Answer out loud, in your own voice, as one short spoken turn:
- start with an acknowledgment of at most five words
- answer in one or two short sentences
- end with one phrase that leads back into the tale

Never use more than four sentences. End on a statement, never a question.
Use only what you have already read aloud, printed below. Never confirm anything
that has not happened yet in the story, even if the child mentions it.
No stage directions, no brackets, no lists.

What you have read so far:
{story_so_far}"""

VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 1.1,
}
