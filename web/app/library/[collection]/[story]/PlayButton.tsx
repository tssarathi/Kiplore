"use client";

import { Room, RoomEvent } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import {
  MAX_RESUME_ATTEMPTS,
  RESUME_RETRY_BASE_MS,
  parseServerMessage,
} from "@/lib/storyState";

type ResumeReport = { seq: number; position: number; paused: boolean };

export default function PlayButton({
  collection,
  storyId,
  voices,
}: {
  collection: string;
  storyId: string;
  voices: { id: string; name: string }[];
}) {
  const [status, setStatus] = useState("Choose a voice");
  const [caption, setCaption] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const room = useRef<Room | null>(null);
  const lastSeq = useRef(0);
  const heard = useRef({ position: 0, paused: false });
  const report = useRef<ResumeReport | null>(null);
  const reportSeq = useRef(0);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(
    () => () => {
      if (retry.current !== null) clearTimeout(retry.current);
      void room.current?.disconnect();
    },
    [],
  );

  function send(message: object, reliable = false) {
    room.current?.localParticipant.publishData(
      new TextEncoder().encode(JSON.stringify(message)),
      { reliable },
    );
  }

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
    setConnected(true);

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ collection, storyId, voiceId }),
    });
    if (!response.ok) {
      setStatus("Could not start the session");
      setConnected(false);
      return;
    }
    const { token, url } = await response.json();

    const joined = new Room({
      audioCaptureDefaults: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        voiceIsolation: false,
      },
      publishDefaults: { dtx: false },
    });
    room.current = joined;
    joined.on(RoomEvent.TrackSubscribed, (track) => {
      document.body.appendChild(track.attach());
      setStatus("Narrator is speaking");
    });
    joined.on(RoomEvent.TrackUnsubscribed, (track) => {
      track.detach().forEach((element) => element.remove());
    });
    joined.on(RoomEvent.DataReceived, (payload) => {
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
      setCaption(message.caption);
    });
    joined.on(RoomEvent.Reconnecting, () => {
      setReconnecting(true);
      setStatus("Reconnecting");
      if (lastSeq.current === 0) return;
      reportSeq.current += 1;
      report.current = { seq: reportSeq.current, ...heard.current };
    });
    joined.on(RoomEvent.Reconnected, () => {
      setReconnecting(false);
      setStatus("Narrator is speaking");
      sendReport(0);
    });
    joined.on(RoomEvent.Disconnected, () => {
      setConnected(false);
      setReconnecting(false);
      setStatus("The story has ended");
    });

    await joined.connect(url, token);
    await joined
      .startAudio()
      .catch(() => setStatus("Sound is blocked in this browser"));
    await joined.localParticipant.setMicrophoneEnabled(true);
  }

  const busy = !connected || reconnecting;

  return (
    <div>
      {voices.map((voice) => (
        <button
          key={voice.id}
          onClick={() => play(voice.id)}
          disabled={connected}
        >
          {voice.name}
        </button>
      ))}
      <p>{status}</p>
      <p>{caption}</p>
      <button onClick={() => send({ action: "pause" })} disabled={busy}>
        Pause
      </button>
      <button onClick={() => send({ action: "resume" })} disabled={busy}>
        Resume
      </button>
      <button
        onClick={() => send({ action: "seek", offset: -10 })}
        disabled={busy}
      >
        Back 10s
      </button>
      <button
        onClick={() => send({ action: "seek", offset: 10 })}
        disabled={busy}
      >
        Forward 10s
      </button>
    </div>
  );
}
