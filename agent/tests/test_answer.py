"""An answer is not just text: brackets in it are instructions to the synthesiser."""

from narrator.answer import shape
from narrator.config import ANSWER_FALLBACK


def test_a_stray_audio_tag_is_not_spoken_or_acted_on():
    assert shape("[whispers] He was only pretending.") == "He was only pretending."


def test_an_answer_that_is_nothing_but_a_tag_still_says_something():
    assert shape("[warmly]") == ANSWER_FALLBACK
