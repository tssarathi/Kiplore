"""Every tunable value in one place."""

from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[3] / "library"

SAMPLE_RATE = 22050
NUM_CHANNELS = 1
FRAME_SAMPLES = int(SAMPLE_RATE * 0.02)

VOICE_ID = "YrAYvOVjAFiqVwBgB4qI"
ELEVEN_MODEL = "eleven_v3"
OUTPUT_FORMAT = "pcm_22050"
SEED = 42

VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 1.1,
}
