# Kiplore

Bedtime stories that stop when a child asks why.

A narrator reads a folk tale aloud. The child can interrupt out loud at any moment — the
narration ducks, the question is answered in the same voice, and the story picks up where
it left off.

![Kiplore: browsing the library and playing a story](docs/demo.gif)

## How it works

The child's browser and a Python worker meet in a LiveKit room. The worker is the narrator.

```
web (Next.js)  ──token──▶  LiveKit room  ◀──audio+data──  agent (Python)
                                                            │
                              ElevenLabs ── narration ──────┤
                              Deepgram ──── the question ───┤
                              OpenAI ────── the answer ─────┤
                              R2 ────────── render cache ───┘
```

**Narration.** ElevenLabs streams the story as PCM with character-level timings. Those
timings become caption segments, so the line on screen is the line being spoken — not a
guess based on elapsed time.

**Interruption.** Deepgram listens continuously. Frame energy ducks the narration the
instant the child speaks; an interim transcript stops it properly. The question goes to
OpenAI with only the story *so far*, so the narrator can never spoil what has not been
read yet. The answer is spoken in the same voice, then the story resumes from the start of
the interrupted sentence.

**Caching.** A finished render is stored in R2, keyed by a hash of everything that shaped
it — script, voice, model, output format, voice settings, seed, chunk gap, pipeline
version. Change any of them and the key changes, so a stale render can never be served.
Renders are quality-checked before they are cached: speech density, longest silence, and
alignment coverage all have to pass.

**Reconnects.** If the browser drops, the room is held open briefly. On return, the client
reports the last position it heard and the story resumes from there.

## Layout

```
agent/src/narrator/    the LiveKit worker
  main.py              job entrypoint, control loop, broadcast
  render.py            ElevenLabs streaming synthesis
  alignment.py         character timings to words, sentences, captions
  listen.py            Deepgram STT, ducking, transcript publishing
  answer.py            the reply to a child's question
  cache.py  qc.py      R2 render cache and its quality gates
  audio.py  player.py  envelope.py  session.py

web/                   Next.js 16 App Router, Tailwind v4
  app/page.tsx                        collections
  app/library/[collection]/           stories in one collection
  app/library/[collection]/[story]/   the player
  app/api/session/route.ts            LiveKit token (development only)

library/               the stories themselves, as JSON
```

## The library

Each story is one JSON file: `id`, `title`, `blurb`, and a `script` of seven chunks.
Collections are just directories.

```json
{
  "id": "the-tortoise-and-the-hare",
  "title": "The Tortoise and the Hare",
  "blurb": "The fastest animal in the wood takes a nap. That is his mistake.",
  "script": ["[warmly] Long, long ago… ", "..."]
}
```

The bracketed tags are [ElevenLabs v3 audio tags](https://elevenlabs.io/docs/best-practices/prompting/eleven-v3).
They direct delivery and are stripped before anything reaches the screen. Three things
worth knowing before editing a script:

- **v3 is the only model that supports tags.** Switching to Flash or Multilingual makes
  them get read aloud or ignored.
- **The limit is 5,000 characters per request**, and a story is sent as one request.
- **`[short pause]` and `[long pause]` are real; SSML `<break>` is not.** Ellipses carry
  most of the pacing, and capitals carry emphasis.

Twelve stories ship here, all public domain: Aesop, the Brothers Grimm, Hans Andersen, and
Kipling's *Just So Stories*.

## Running it

Needs Python 3.13+, Node 20+, and accounts for LiveKit, ElevenLabs, Deepgram, OpenAI and
Cloudflare R2.

`agent/.env`:

```
LIVEKIT_URL=            LIVEKIT_API_KEY=       LIVEKIT_API_SECRET=
ELEVENLABS_API_KEY=     DEEPGRAM_API_KEY=      OPENAI_API_KEY=
R2_ACCOUNT_ID=          R2_ACCESS_KEY_ID=      R2_SECRET_ACCESS_KEY=      R2_BUCKET=
```

`web/.env.local` needs the three `LIVEKIT_` values only.

Two terminals:

```bash
cd agent && uv run python -m narrator.main dev
cd web   && npm install && npm run dev
```

Then open <http://localhost:3000>. The first play of a story synthesises it, which takes a
few seconds and costs ElevenLabs credits; after that it comes from the cache.

## Scope

A single-user demo. There is no auth, no accounts, and nothing is persisted between
sessions. The token route refuses to run outside development and would need real
authentication before this was exposed to anyone.
