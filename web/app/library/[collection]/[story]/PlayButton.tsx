"use client";

import { RoomContext } from "@livekit/components-react";
import { Room, RoomEvent } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import {
  BackIcon,
  ForwardIcon,
  PauseIcon,
  PlayIcon,
} from "@/components/icons";
import VoiceAvatar, { type Look } from "@/components/VoiceAvatar";
import Narrator from "./Narrator";
import {
  MAX_RESUME_ATTEMPTS,
  RESUME_RETRY_BASE_MS,
  formatTime,
  parseServerMessage,
} from "@/lib/storyState";

type ResumeReport = { seq: number; position: number; paused: boolean };

/**
 * The player: connects to the room, holds the LiveKit session, and drives transport.
 *
 * State here is of two kinds and they are kept apart. Anything React draws is useState.
 * Anything a room event handler reads at the moment it fires is a ref, because the
 * handlers are registered once and would otherwise close over the values from the
 * render that created them.
 */
export default function PlayButton({
  collection,
  storyId,
  voices,
}: {
  collection: string;
  storyId: string;
  voices: { id: string; name: string; look: Look }[];
}) {
  const [status, setStatus] = useState("Choose a voice");
  const [caption, setCaption] = useState<string | null>(null);
  const [phase, setPhase] = useState<"picking" | "starting" | "live" | "ended">(
    "picking",
  );
  const [chosen, setChosen] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [position, setPosition] = useState(0);
  const [duration, setDuration] = useState(0);
  const [paused, setPaused] = useState(false);
  const [room] = useState(
    () =>
      new Room({
        audioCaptureDefaults: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          voiceIsolation: false,
        },
        publishDefaults: { dtx: false },
      }),
  );
  // Protocol state, read inside room event handlers rather than drawn.
  const lastSeq = useRef(0);
  const heard = useRef({ position: 0, paused: false });
  const report = useRef<ResumeReport | null>(null);
  const reportSeq = useRef(0);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Leaving the page ends the session: the agent sees the disconnect and decides
  // whether to hold the story or tear the room down.
  useEffect(
    () => () => {
      if (retry.current !== null) clearTimeout(retry.current);
      void room.disconnect();
    },
    [room],
  );

  // Transport commands go unreliably by default; another press is one click away if
  // one is lost, and a late one would be worse than a missing one.
  function send(message: object, reliable = false) {
    room.localParticipant.publishData(
      new TextEncoder().encode(JSON.stringify(message)),
      { reliable },
    );
  }

  /** Tell the agent where we had got to, until it acknowledges or the tries run out. */
  // Sent reliably, but a reconnect can still land before the agent is ready for it, so
  // it repeats with a doubling delay rather than trusting the first attempt.
  function sendReport(attempt: number) {
    if (report.current === null) return;
    if (attempt >= MAX_RESUME_ATTEMPTS) {
      report.current = null;
      return;
    }
    send({ action: "resume-at", ...report.current }, true);
    retry.current = setTimeout(
      () => sendReport(attempt + 1),
      RESUME_RETRY_BASE_MS * 2 ** attempt,
    );
  }

  async function play(voiceId: string) {
    setStatus("Connecting");
    setChosen(voiceId);
    setPhase("starting");

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ collection, storyId, voiceId }),
    });
    if (!response.ok) {
      setStatus("Could not start the session");
      setPhase("picking");
      return;
    }
    const { token, url } = await response.json();

    // The narrator's track has to be attached to an element in the page before any of
    // it can be heard.
    room.on(RoomEvent.TrackSubscribed, (track) => {
      document.body.appendChild(track.attach());
      setStatus("Narrator is speaking");
    });
    room.on(RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach((element) => element.remove());
    });
    room.on(RoomEvent.DataReceived, (payload) => {
      const message = parseServerMessage(payload);
      if (message === null) return;
      if (message.type === "resume-ack") {
        if (report.current?.seq !== message.seq) return;
        report.current = null;
        if (retry.current !== null) clearTimeout(retry.current);
        return;
      }
      // Each message is a snapshot rather than a delta, so an old one is dropped
      // outright instead of applied out of order.
      if (message.seq <= lastSeq.current) return;
      lastSeq.current = message.seq;
      heard.current = { position: message.position, paused: message.paused };
      setPosition(message.position);
      setDuration(message.duration);
      setPaused(message.paused);
      setCaption(message.caption);
    });
    // Snapshot what was last heard now, while it is still true. By the time the
    // connection is back the agent may have moved on without us.
    room.on(RoomEvent.Reconnecting, () => {
      setReconnecting(true);
      setStatus("Reconnecting");
      // Nothing heard yet, so there is no position worth reporting.
      if (lastSeq.current === 0) return;
      reportSeq.current += 1;
      report.current = { seq: reportSeq.current, ...heard.current };
    });
    room.on(RoomEvent.Reconnected, () => {
      setReconnecting(false);
      setStatus("Narrator is speaking");
      sendReport(0);
    });
    room.on(RoomEvent.Disconnected, () => {
      setPhase("ended");
      setReconnecting(false);
      setStatus("The story has ended");
    });

    await room.connect(url, token);
    setPhase("live");
    // Browsers refuse to play audio on a page that has not been interacted with. The
    // click that got here usually satisfies that, but not on every browser.
    await room
      .startAudio()
      .catch(() => setStatus("Sound is blocked in this browser"));
    await room.localParticipant.setMicrophoneEnabled(true);
  }

  // Transport is disabled whenever there is no agent on the other end to receive it.
  const busy = phase !== "live" || reconnecting;

  return (
    <RoomContext.Provider value={room}>
      {phase === "picking" || phase === "starting" ? (
        <div className="rounded-[8px] bg-card px-6 py-12 text-center">
          <p className="label text-sm text-quiet">Read to me by</p>
          <div className="mt-7 flex flex-wrap justify-center gap-4">
            {voices.map((voice) => (
              <button
                key={voice.id}
                onClick={() => play(voice.id)}
                disabled={phase === "starting"}
                className={`flex w-28 cursor-pointer flex-col items-center gap-3 rounded-[8px] px-3 py-4 transition duration-200 focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-default ${
                  chosen === voice.id
                    ? "bg-accent/10 ring-1 ring-accent"
                    : "ring-1 ring-rule hover:ring-accent disabled:opacity-40"
                }`}
              >
                <span className="size-16 overflow-hidden rounded-full">
                  <VoiceAvatar look={voice.look} />
                </span>
                <span
                  className={`label text-xs ${chosen === voice.id ? "text-accent" : "text-ink"}`}
                >
                  {voice.name}
                </span>
              </button>
            ))}
          </div>
          <p aria-live="polite" className="label mt-8 text-xs text-quiet">
            {status}
          </p>
        </div>
      ) : (
        <div className="rounded-[8px] bg-card px-6 py-10 sm:px-10">
          <Narrator caption={caption} status={status}>
            <div className="mt-10 flex items-center gap-4">
              <span className="label w-10 shrink-0 text-xs text-quiet tabular-nums">
                {formatTime(position)}
              </span>
              <div className="h-px flex-1 bg-rule">
                <div
                  className="h-px bg-accent transition-[width] duration-1000 ease-linear"
                  style={{
                    width:
                      duration > 0
                        ? `${Math.min(100, (position / duration) * 100)}%`
                        : "0%",
                  }}
                />
              </div>
              <span className="label w-10 shrink-0 text-right text-xs text-quiet tabular-nums">
                {duration > 0 ? formatTime(duration) : "--:--"}
              </span>
            </div>

            <div className="mt-8 flex items-center justify-center gap-6">
              <button
                onClick={() => send({ action: "seek", offset: -10 })}
                disabled={busy}
                aria-label="Back ten seconds"
                className="flex size-11 cursor-pointer items-center justify-center rounded-full text-quiet transition duration-200 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-default disabled:opacity-30"
              >
                <BackIcon className="size-5" />
              </button>
              <button
                onClick={() => send({ action: paused ? "resume" : "pause" })}
                disabled={busy}
                aria-label={paused ? "Play the story" : "Pause the story"}
                className="flex size-16 cursor-pointer items-center justify-center rounded-full bg-graphite text-card transition duration-200 hover:bg-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-card focus-visible:outline-none disabled:cursor-default disabled:opacity-40"
              >
                {paused ? (
                  <PlayIcon className="size-6 translate-x-px" />
                ) : (
                  <PauseIcon className="size-6" />
                )}
              </button>
              <button
                onClick={() => send({ action: "seek", offset: 10 })}
                disabled={busy}
                aria-label="Forward ten seconds"
                className="flex size-11 cursor-pointer items-center justify-center rounded-full text-quiet transition duration-200 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none disabled:cursor-default disabled:opacity-30"
              >
                <ForwardIcon className="size-5" />
              </button>
            </div>
          </Narrator>
        </div>
      )}
    </RoomContext.Provider>
  );
}
