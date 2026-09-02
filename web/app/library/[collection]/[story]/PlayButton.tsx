"use client";

import { Room, RoomEvent } from "livekit-client";
import { useState } from "react";

export default function PlayButton({
  collection,
  storyId,
}: {
  collection: string;
  storyId: string;
}) {
  const [status, setStatus] = useState("Ready");

  async function play() {
    setStatus("Connecting");

    const response = await fetch("/api/session", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ collection, storyId }),
    });
    if (!response.ok) {
      setStatus("Could not start the session");
      return;
    }
    const { token, url } = await response.json();

    const room = new Room();
    room.on(RoomEvent.ParticipantConnected, (participant) =>
      setStatus(`Narrator joined: ${participant.identity}`),
    );

    await room.connect(url, token);
    setStatus("Connected, waiting for the narrator");
  }

  return (
    <div>
      <button onClick={play}>Play</button>
      <p>{status}</p>
    </div>
  );
}
