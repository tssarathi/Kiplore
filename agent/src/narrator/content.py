import json

from narrator.config import LIBRARY_DIR


def load_story(collection: str, story_id: str) -> dict:
    return json.loads((LIBRARY_DIR / collection / f"{story_id}.json").read_text())


def load_voice(voice_id: str) -> dict:
    voices = json.loads((LIBRARY_DIR / "voices.json").read_text())
    return {voice["id"]: voice for voice in voices}[voice_id]
