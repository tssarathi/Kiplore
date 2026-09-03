<h1 align="center">Kiplore</h1>

<p align="center">
  A voice application that reads folk tales aloud to a child and answers their questions
  in the middle of the story.
</p>

<p align="center">
  <a href="#features"><strong>Features</strong></a> ·
  <a href="#how-it-works"><strong>How it works</strong></a> ·
  <a href="#getting-started"><strong>Getting started</strong></a> ·
  <a href="#story-format"><strong>Story format</strong></a> ·
  <a href="#project-layout"><strong>Project layout</strong></a>
</p>

<p align="center">
  <img alt="Next.js 16" src="https://img.shields.io/badge/Next.js-16-000000?logo=nextdotjs&logoColor=white">
  <img alt="React 19" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black">
  <img alt="Python 3.13" src="https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white">
  <img alt="LiveKit Agents 1.7" src="https://img.shields.io/badge/LiveKit%20Agents-1.7-1FD5F9?logo=livekit&logoColor=white">
</p>

<p align="center">
  <img alt="Browsing the library, choosing a voice, and playing a story with live captions and transport controls" src="docs/demo.gif" width="100%">
</p>

## Features

- **Interrupt with your voice.** The child can speak at any point. Frame energy ducks the
  narration immediately, and the first interim transcript stops playback properly.
- **Answers that cannot spoil the story.** The model is given only the text narrated so
  far, so it is unable to reveal events the child has not yet reached.
- **Captions derived from the audio.** Character level timings returned by the synthesiser
  are grouped into sentences, so the line on screen is the line being spoken rather than an
  estimate based on elapsed time.
- **Transport controls.** Pause, resume and ten second seeks, applied by the agent and
  reflected back to every client.
- **Resume after a dropped connection.** The room is held open for 60 seconds. On return,
  the client reports the last position it heard and playback continues from there.
- **Deterministic render cache.** Completed narrations are cached in object storage under a
  hash of every input that shaped them, so a stale render cannot be served.
- **Quality gates before caching.** Speech density, silence length and alignment coverage
  are all checked before a render is allowed into the cache.

## How it works

The browser and a Python worker meet in a LiveKit room. The worker is the narrator: it
publishes an audio track, streams synthesised speech into it, listens to the child's
microphone, and answers when spoken to.

```
web (Next.js)  ──token──▶  LiveKit room  ◀──audio + data──  agent (Python)
                                                              │
                                ElevenLabs ── narration ──────┤
                                Deepgram ──── transcription ──┤
                                OpenAI ────── answers ────────┤
                                Cloudflare R2 ─ render cache ─┘
```

### Narration and captions

ElevenLabs streams each story as PCM audio together with character level timings. Those
timings are grouped into words and then into sentence segments, which the agent broadcasts
to the client roughly once per second alongside the playback position.

### Interruption and answering

Deepgram transcribes the microphone continuously. Two signals are used, at different
latencies: frame energy ducks the narration volume as soon as speech is detected, and the
first interim transcript stops playback.

The question is then sent to OpenAI together with the story text heard so far. If the
speech was not understood, the narrator asks the child to repeat it instead of guessing.
The reply is synthesised in the same voice, after which playback resumes from the start of
the interrupted sentence.

### Render cache

A completed render is stored in Cloudflare R2 under a key derived from a SHA-256 hash of
the script, voice, model, output format, voice settings, seed, chunk gap and pipeline
version. Changing any of these produces a different key.

Renders are quality checked before being cached. A render is rejected if its speech density
falls outside 6 to 25 characters per second, if it contains a silence longer than two
seconds, or if the character alignment covers less than 85 percent of the audio. A rejected
render is still played to the listener, but it is not stored.

## Getting started

### Prerequisites

- Python 3.13 or later, with [uv](https://docs.astral.sh/uv/)
- Node.js 20 or later
- Accounts for LiveKit, ElevenLabs, Deepgram, OpenAI and Cloudflare R2

### Configuration

| Variable | Required by | Purpose |
| --- | --- | --- |
| `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` | agent, web | Room connection and access token signing |
| `ELEVENLABS_API_KEY` | agent | Speech synthesis |
| `DEEPGRAM_API_KEY` | agent | Transcription |
| `OPENAI_API_KEY` | agent | Answer generation |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET` | agent | Render cache |

Place all of the above in `agent/.env`, and the three `LIVEKIT_` values in `web/.env.local`.

### Running locally

Start the agent worker and the web application in separate terminals.

```bash
cd agent
uv run python -m narrator.main dev
```

```bash
cd web
npm install
npm run dev
```

The application is then available at http://localhost:3000.

The first playback of a story synthesises it, which takes a few seconds and consumes
ElevenLabs credits. Later playbacks of the same story and voice are served from the cache.

## Story format

Each story is a single JSON file containing an identifier, title, blurb and a script of
seven chunks. Collections are directories under `library/`.

```json
{
  "id": "the-tortoise-and-the-hare",
  "title": "The Tortoise and the Hare",
  "blurb": "The fastest animal in the wood takes a nap. That is his mistake.",
  "script": ["[warmly] Long, long ago…", "..."]
}
```

Bracketed tags are [ElevenLabs v3 audio tags](https://elevenlabs.io/docs/best-practices/prompting/eleven-v3).
They direct vocal delivery and are removed before any text reaches the screen. Three
constraints apply when editing a script.

| Constraint | Detail |
| --- | --- |
| Model | Eleven v3 is the only model that supports audio tags. Flash and Multilingual will speak them aloud or ignore them. |
| Length | 5,000 characters per request, and each story is sent as a single request. |
| Pauses | `[pause]`, `[short pause]` and `[long pause]` are supported. SSML break tags are not. Ellipses control pacing and capitalisation controls emphasis. |

Twelve stories are included, all in the public domain: Aesop's fables, tales from the
Brothers Grimm and Hans Andersen, and Kipling's *Just So Stories*.

## Project layout

```
agent/src/narrator/
  main.py          job entrypoint, control loop, state broadcast
  render.py        ElevenLabs streaming synthesis
  alignment.py     character timings to words, sentences and captions
  listen.py        Deepgram transcription, ducking, transcript publishing
  answer.py        answer generation
  cache.py         R2 render cache
  qc.py            quality gates applied before caching
  audio.py         track publishing and playback
  player.py        playback position and seeking
  envelope.py      volume ramping
  session.py       reconnect and resume state
  config.py        all tunable values

web/
  app/page.tsx                       collection index
  app/library/[collection]/          stories within a collection
  app/library/[collection]/[story]/  the player
  app/api/session/route.ts           LiveKit access token, development only
  lib/content.ts                     library loading
  lib/storyState.ts                  message validation

library/           story content as JSON, one directory per collection
```

## Limitations

This is a single user demonstration. There is no authentication, no user accounts and no
persistence between sessions. The token endpoint returns 403 outside development and would
require proper authentication before the application could be exposed publicly.
