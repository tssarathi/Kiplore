from narrator.alignment import heard_text, to_segments, words_from_chars


def timed(text: str) -> tuple[list[str], list[float], list[float]]:
    return (
        list(text),
        [i / 10 for i in range(len(text))],
        [(i + 1) / 10 for i in range(len(text))],
    )


def spans(texts: list[str]) -> list[dict]:
    return [
        {"text": text, "start": i / 2, "end": (i + 1) / 2}
        for i, text in enumerate(texts)
    ]


def test_audio_tags_are_not_spoken_and_do_not_shift_the_words_after_them():
    words = words_from_chars(*timed("[warmly] Once upon a time"))

    assert [word["text"] for word in words] == ["Once", "upon", "a", "time"]
    assert words[0]["start"] == 0.9


def test_an_abbreviation_does_not_end_a_caption():
    segments = to_segments(spans(["It", "was", "5", "p.m.", "and", "dark."]))

    assert [segment["text"] for segment in segments] == ["It was 5 p.m. and dark."]


def test_a_real_sentence_end_still_does():
    segments = to_segments(spans(["He", "ran.", "She", "hid."]))

    assert [segment["text"] for segment in segments] == ["He ran.", "She hid."]


def test_the_story_so_far_stops_at_the_sentence_being_spoken():
    segments = to_segments(spans(["He", "ran.", "She", "hid.", "They", "won."]))

    heard = heard_text([], segments, [], 1.5)

    assert heard == "He ran. She hid."
    assert "won" not in heard


def test_before_any_alignment_arrives_whole_chunks_are_the_limit():
    script = ["[warmly] One two.", "Three four."]

    assert heard_text(script, [], [2.0, 4.0], 1.0) == "One two."
