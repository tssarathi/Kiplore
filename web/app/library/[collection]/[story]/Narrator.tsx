"use client";

import {
  BarVisualizer,
  type TextStreamData,
  useTranscriptions,
  useVoiceAssistant,
} from "@livekit/components-react";
import { useState } from "react";

type Line = { mine: boolean; text: string };

/**
 * The narrator's presence: a voice bar, the transport controls, and the one line
 * currently on screen.
 *
 * That line is either the caption the agent is broadcasting or the newest transcript,
 * whichever changed last.
 */
export default function Narrator({
  caption,
  status,
  children,
}: {
  caption: string | null;
  status: string;
  children: React.ReactNode;
}) {
  const { state, audioTrack, agent } = useVoiceAssistant();
  const transcriptions = useTranscriptions();

  // Transcriptions are not guaranteed to arrive in order, so the newest is found by
  // timestamp rather than by taking the last of the list.
  const newest = transcriptions.reduce<TextStreamData | null>(
    (best, one) =>
      best === null || one.streamInfo.timestamp >= best.streamInfo.timestamp
        ? one
        : best,
    null,
  );
  const spoken = newest?.text ?? null;
  const mine =
    newest !== null && newest.participantInfo.identity !== agent?.identity;
  const midSentence =
    mine && newest?.streamInfo.attributes?.["lk.transcription_final"] !== "true";

  const [seen, setSeen] = useState({ caption, spoken });
  const [line, setLine] = useState<Line | null>(null);

  // Adjusted during render rather than in an effect. React re-runs the component at
  // once, before anything is painted, so the line never lags a frame behind the audio.
  if (caption !== seen.caption || spoken !== seen.spoken) {
    setSeen({ caption, spoken });
    // While the child is still mid-sentence their own words hold the line: replacing
    // them with the story caption would read as not being heard.
    if (spoken !== seen.spoken && spoken !== null) {
      setLine({ mine, text: spoken });
    } else if (caption !== null && !midSentence) {
      setLine({ mine: false, text: caption });
    }
  }

  return (
    <div>
      <BarVisualizer
        state={state}
        track={audioTrack}
        barCount={5}
        className="flex h-16 items-end justify-center gap-1.5"
      >
        <div className="w-1 bg-rule transition-colors duration-200 data-[lk-highlighted=true]:bg-accent" />
      </BarVisualizer>

      {children}

      <p
        aria-live="polite"
        className="mono mt-8 min-h-12 text-center text-sm leading-relaxed text-balance"
      >
        {line ? (
          <>
            {line.mine && (
              <span className="label mr-2 text-xs text-accent">You —</span>
            )}
            <span className={line.mine ? "text-quiet" : "text-ink"}>
              {line.text}
            </span>
          </>
        ) : (
          <span className="label text-xs text-quiet">{status}</span>
        )}
      </p>
    </div>
  );
}
