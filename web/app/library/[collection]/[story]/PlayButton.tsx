"use client";

import { Room, RoomEvent } from "livekit-client";
import { useEffect, useRef, useState } from "react";
import { parseStoryState } from "@/lib/storyState";

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
  const room = useRef<Room | null>(null);
  const lastSeq = useRef(0);

  useEffect(() => () => void room.current?.disconnect(), []);

  async function play(voiceId: string) {
    setStatus("Connecting");

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ collection, storyId, voiceId }),
    });
    if (!response.ok) {
      setStatus("Could not start the session");
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
      const state = parseStoryState(payload);
      if (state === null || state.seq <= lastSeq.current) return;
      lastSeq.current = state.seq;
      setCaption(state.caption);
    });

    await joined.connect(url, token);
    await joined
      .startAudio()
      .catch(() => setStatus("Sound is blocked in this browser"));
    await joined.localParticipant.setMicrophoneEnabled(true);
  }

  function control(action: string, offset = 0) {
    const message = JSON.stringify({ action, offset });
    room.current?.localParticipant.publishData(new TextEncoder().encode(message));
  }

  return (
    <div>
      {voices.map((voice) => (
        <button key={voice.id} onClick={() => play(voice.id)}>
          {voice.name}
        </button>
      ))}
      <p>{status}</p>
      <p>{caption}</p>
      <button onClick={() => control("pause")}>Pause</button>
      <button onClick={() => control("resume")}>Resume</button>
      <button onClick={() => control("seek", -10)}>Back 10s</button>
      <button onClick={() => control("seek", 10)}>Forward 10s</button>
    </div>
  );
}
