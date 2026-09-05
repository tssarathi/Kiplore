"use client";

import { RoomContext } from "@livekit/components-react";
import { DisconnectReason, Room, RoomEvent } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import {
  BackIcon,
  ForwardIcon,
  PauseIcon,
  PlayIcon,
} from "@/components/icons";
import VoiceAvatar, { type Look } from "@/components/VoiceAvatar";
import Narrator from "./Narrator";
import { formatTime, parseServerMessage } from "@/lib/storyState";

const MAX_RESUME_ATTEMPTS = 7;
const RESUME_RETRY_BASE_MS = 250;

type ResumeReport = { seq: number; position: number; paused: boolean };

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
  const [warning, setWarning] = useState<string | null>(null);
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

  const lastSeq = useRef(0);
  const heard = useRef({ position: 0, paused: false });
  const report = useRef<ResumeReport | null>(null);
  const reportSeq = useRef(0);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wired = useRef(false);

  function send(message: object) {
    room.localParticipant.publishData(
      new TextEncoder().encode(JSON.stringify(message)),
      { reliable: true },
    );
  }

  function sendReport(attempt: number) {

    if (retry.current !== null) clearTimeout(retry.current);
    retry.current = null;
    if (report.current === null) return;
    if (attempt >= MAX_RESUME_ATTEMPTS) {
      report.current = null;
      return;
    }
    send({ action: "resume-at", ...report.current });
    retry.current = setTimeout(
      () => sendReport(attempt + 1),
      RESUME_RETRY_BASE_MS * 2 ** attempt,
    );
  }

  useEffect(
    () => () => {
      if (retry.current !== null) clearTimeout(retry.current);
      void room.disconnect();
    },
    [room],
  );

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

    if (!wired.current) {
      wired.current = true;

      room.on(RoomEvent.TrackSubscribed, (track) => {
        document.body.appendChild(track.attach());
        setStatus((current) =>
          current === "Connecting" ? "Narrator is speaking" : current,
        );
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

        if (message.seq <= lastSeq.current) return;
        lastSeq.current = message.seq;
        heard.current = { position: message.position, paused: message.paused };
        setPosition(message.position);
        setDuration(message.duration);
        setPaused(message.paused);
        setCaption(message.caption);
      });

      room.on(RoomEvent.Reconnecting, () => {
        setReconnecting(true);
        setStatus("Reconnecting");

        reportSeq.current += 1;
        report.current = { seq: reportSeq.current, ...heard.current };
      });
      room.on(RoomEvent.Reconnected, () => {
        setReconnecting(false);
        setStatus("Narrator is speaking");
        sendReport(0);
      });
      room.on(RoomEvent.Disconnected, (reason) => {
        if (retry.current !== null) clearTimeout(retry.current);
        retry.current = null;
        report.current = null;
        setPhase("ended");
        setReconnecting(false);
        setPaused(true);
        setStatus(
          reason === DisconnectReason.ROOM_DELETED ||
            reason === DisconnectReason.CLIENT_INITIATED
            ? "The story has ended"
            : "The connection was lost",
        );
      });
    }

    try {
      const { token, url } = await response.json();
      await room.connect(url, token);
    } catch {
      setStatus("Could not start the session");
      setPhase("picking");
      return;
    }
    setPhase("live");

    await room
      .startAudio()
      .catch(() => setWarning("Sound is blocked in this browser"));
    await room.localParticipant
      .setMicrophoneEnabled(true)
      .catch(() => setWarning("The microphone is unavailable"));
  }

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
          <Narrator
            caption={caption}
            status={status}
            warning={warning}
            ended={phase === "ended"}
          >
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
                className="flex size-16 cursor-pointer items-center justify-center rounded-full bg-ink text-card transition duration-200 hover:bg-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:ring-offset-4 focus-visible:ring-offset-card focus-visible:outline-none disabled:cursor-default disabled:opacity-40"
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
