import json

from narrator.config import LIBRARY_DIR


def load_story(collection: str, story_id: str) -> dict:
    path = (LIBRARY_DIR / collection / f"{story_id}.json").resolve()
    if not path.is_relative_to(LIBRARY_DIR.resolve()):
        raise ValueError(f"story is outside the library: {collection}/{story_id}")
    return json.loads(path.read_text())


def load_voice(voice_id: str) -> dict:
    voices = json.loads((LIBRARY_DIR / "voices.json").read_text())
    return {voice["id"]: voice for voice in voices}[voice_id]
