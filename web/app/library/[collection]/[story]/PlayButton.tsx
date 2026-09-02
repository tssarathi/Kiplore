"use client";

import { Room, RoomEvent } from "livekit-client";
import { useState } from "react";

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

    const room = new Room();
    room.on(RoomEvent.TrackSubscribed, (track) => {
      document.body.appendChild(track.attach());
      setStatus("Narrator is speaking");
    });

    await room.connect(url, token);
    setStatus("Connected, waiting for the narrator");
  }

  return (
    <div>
      {voices.map((voice) => (
        <button key={voice.id} onClick={() => play(voice.id)}>
          {voice.name}
        </button>
      ))}
      <p>{status}</p>
    </div>
  );
}
