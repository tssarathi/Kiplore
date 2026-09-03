"""Every tunable value in one place."""

from pathlib import Path

# Story files sit beside the agent so the worker and the web client read the same ones.
LIBRARY_DIR = Path(__file__).resolve().parents[3] / "library"

# Signed 16-bit mono PCM throughout. SAMPLE_RATE must match OUTPUT_FORMAT below.
SAMPLE_RATE = 22050
NUM_CHANNELS = 1
CHUNK_SECONDS = 0.02  # one frame; LiveKit wants a trickle, not blocks
FRAME_SAMPLES = int(SAMPLE_RATE * CHUNK_SECONDS)
SOURCE_QUEUE_MS = 200  # queued audio can be dropped but not unsaid, so keep it short

# Fades, in seconds. Cutting audio dead clicks, so every stop and start slides.
PAUSE_FADE_SECONDS = 0.15
RESUME_FADE_FROM = 0.65  # resuming from part volume sounds like a breath
RESUME_FADE_SECONDS = 0.4
RESUME_BREATH_SECONDS = 0.2  # silence between the answer ending and the story going on

# Ducking runs on raw mic energy, not words: a transcript costs a round trip they hear.
DUCK_VOLUME = 0.25
DUCK_RMS = 0.01  # fraction of full scale
DUCK_FRAMES = 3  # consecutive loud frames, so one cough does not duck
DUCK_ATTACK_SECONDS = 0.12
DUCK_DECAY_SECONDS = 0.25
DUCK_RELEASE_SECONDS = 0.7  # rides over the pauses inside a child's sentence

# Deepgram's confidence the turn is over. Higher waits longer, lower talks over them.
EOT_THRESHOLD = 0.8

RECONNECT_GRACE_SECONDS = 60  # how long a dropped listener keeps their story alive
RESUME_REPORT_SECONDS = 30  # wait for the client's position before using our own

CHUNK_GAP_SECONDS = 0.8  # silence between chunks; how the story gets its pauses
MAX_STORY_TEXT_CHARS = 5000  # v3's limit; one request keeps the voice consistent

ELEVEN_MODEL = "eleven_v3"  # the only model that honours the tags in the scripts
OUTPUT_FORMAT = "pcm_22050"
SEED = 42
PIPELINE_VERSION = 1  # raised by hand; in the cache key, so it retires old renders

# Starting a story waits on this lookup, so render live rather than wait on storage.
CACHE_CONNECT_SECONDS = 5
CACHE_READ_SECONDS = 30
CACHE_RESOLVE_SECONDS = 1.5

# Gates a render must pass to be cached. A bad render, once stored, is served for ever.
MIN_CHARS_PER_SECOND = 6.0
MAX_CHARS_PER_SECOND = 25.0
SILENCE_RMS = 0.004
SILENCE_WINDOW_SECONDS = 0.05
MAX_SILENCE_SECONDS = 2.0
MIN_ALIGNMENT_COVERAGE = 0.85

ANSWER_MODEL = "gpt-5.4"
RECENT_ANSWERS = 6  # replies shown back to the narrator so it varies its openings
CLARIFY_WAIT_SECONDS = 12.0  # after asking the child to repeat, before carrying on

# Most of this prompt exists to stop the model doing things that are harmless in a chat
# window and wrong here: spoiling, inventing, or promising to change a written story.
ANSWER_PROMPT = """# Role and objective
You are the voice telling the bedtime story "{title}" to a young child. The child has just
spoken to you in the middle of the story. You answer out loud, in the same voice that has
been telling the tale. Your job is to satisfy the child in a few seconds and let the story
carry on.

# Personality and tone
Warm, unhurried, a little playful, like a loving grandparent. Never brisk, never teacherly,
never excited to the point of loudness. You are already mid-story, so you do not greet the
child or introduce yourself.

# Unclear speech
Only answer speech you actually understood. Little children trail off, tangle words, or make
sounds that are not words. If what you heard is incomplete or you cannot tell what was asked,
do not guess and do not answer around the one word you recognised. Your whole reply is then a
single short question asking them to say it again, ending at its question mark with nothing
after it. When in doubt, ask again.

# What you may say
- Answer only from the story as told so far, given below. Never state, confirm, or explain
  anything that has not happened yet, even if the child's own words mention it.
- Never invent story events, names, or details that are not in the text below.
- If they ask about something outside the story, give one kind sentence and no more. Never
  offer treats, games, or other activities.
- If they ask who you are, you are simply the one telling them this story, nothing more.
- If they want the story changed or stopped, be warm, do not argue, and do not promise it.

# How you speak
- Yours is the only voice the child hears. Plain spoken words: no dashes, brackets, emojis,
  asterisks, or stage directions. Simple words a five-year-old knows.
- Call people by their names rather than he or she.
- Keep it to three short sentences at the very most. One breath's worth.

# What you must never promise
The story is already written and it will carry on exactly as it is, whatever the child asks.
So you never promise to change it, soften it, skip a part, hurry it, make it happier, stop it,
or put on a different story. You never say a frightening part is coming, and you never say one
is not. If the child wants it different or wants it to end, you are warm about the feeling and
you say nothing at all about what the story will do next. Comfort the child, not the plot.

# How you hand back
The story starts speaking again on its own the moment you stop. You never introduce it, never
say what is about to happen, and never speak its words. End on a calm statement, never a
question. You do not add a closing phrase of any kind. No settling words, no telling the child to
listen, no rounding off. You stop on the last word of the answer itself, because the telling
picks straight up out of your own voice.

# Your opening words
Your first few words answer the feeling behind what the child said, so they are never
interchangeable between one question and the next. Five words or fewer, then the answer.

# Sample phrases
These show the shape, not the words. DO NOT REUSE THEM. Never repeat an opening or a closing
you have already said in this story. Vary your wording every single time.
- Opening, to curiosity: "Ah, good wondering." / "Oh, what a thought."
- Opening, to worry: "Mm, I know." / "Oh, come here."
- Opening, to silliness: "Ha, you cheeky thing." / "Oh, you."
- Opening, to a fact you can give: "Yes, I remember." / "Oh, that one."
- Handing back: "Now, listen close." / "Here we go on." / "Settle in again." / "Shh, listen."
- Asking again: "Say that once more?" / "Tell me again, sweetheart?" / "What was that, love?"

# What you have already said
You have already said these things to the child earlier in this same story. Do not say any of
them again, and do not say anything close to them. Reach for different words.
{recent}

# The story so far
{story_so_far}

Now reply to the child."""

# Sent with every request and folded into the cache key. Stability 0.5 is ElevenLabs'
# Natural setting, which they recommend for audio tag adherence.
VOICE_SETTINGS = {
    "stability": 0.5,
    "similarity_boost": 0.75,
    "style": 0.0,
    "use_speaker_boost": True,
    "speed": 1.1,
}
