"""Every tunable value in one place."""

from pathlib import Path

LIBRARY_DIR = Path(__file__).resolve().parents[3] / "library"

# Best lossless format ElevenLabs serves on this tier; carries sound to 11 kHz.
SAMPLE_RATE = 22050
NUM_CHANNELS = 1

# 20 ms, the standard packet length for internet voice.
FRAME_SAMPLES = int(SAMPLE_RATE * 0.02)
