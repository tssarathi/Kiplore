"use client";

import {
  BarVisualizer,
  type TextStreamData,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { useState } from "react";

type Line = { mine: boolean; text: string };

export default function Narrator({ caption }: { caption: string | null }) {
  const { state, audioTrack, agent } = useVoiceAssistant();
  const transcriptions = useTranscriptions();

  const newest = transcriptions.reduce<TextStreamData | null>(
    (best, one) =>
      best === null || one.streamInfo.timestamp >= best.streamInfo.timestamp
        ? one
        : best,
    null,
  );
  const spoken = newest?.text ?? null;
  const mine = newest?.participantInfo.identity !== agent?.identity;
  const midSentence =
    mine && newest?.streamInfo.attributes?.["lk.transcription_final"] !== "true";

  const [seen, setSeen] = useState({ caption, spoken });
  const [line, setLine] = useState<Line | null>(null);

  if (caption !== seen.caption || spoken !== seen.spoken) {
    setSeen({ caption, spoken });
    if (spoken !== seen.spoken && spoken !== null) {
      setLine({ mine, text: spoken });
    } else if (caption !== null && !midSentence) {
      setLine({ mine: false, text: caption });
    }
  }

  return (
    <div>
      <BarVisualizer state={state} track={audioTrack} barCount={7} />
      <p>
        {line?.mine ? "You: " : ""}
        {line?.text}
      </p>
    </div>
  );
}
