// the agent sends raw bytes from outside the app, so every field is checked here

export type StoryState = {
  type: "state";
  seq: number;
  position: number;
  duration: number;
  paused: boolean;
  caption: string | null;
};

export type ResumeAck = {
  type: "resume-ack";
  seq: number;
};

// seven attempts with a doubling delay span the 30s the agent waits for one
export const MAX_RESUME_ATTEMPTS = 7;
export const RESUME_RETRY_BASE_MS = 250;

/** One message from the agent, or null if it cannot be used. */
export function parseServerMessage(
  payload: Uint8Array,
): StoryState | ResumeAck | null {
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder().decode(payload));
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const { type, seq, position, duration, paused, caption } = value as Record<
    string,
    unknown
  >;
  // both message types carry seq, so it is checked before they diverge
  if (!Number.isInteger(seq) || (seq as number) <= 0) return null;
  if (type === "resume-ack") return { type, seq: seq as number };
  if (
    typeof position !== "number" ||
    !Number.isFinite(position) ||
    position < 0
  ) {
    return null;
  }
  if (
    typeof duration !== "number" ||
    !Number.isFinite(duration) ||
    duration < 0
  ) {
    return null;
  }
  if (typeof paused !== "boolean") return null;
  if (caption !== null && typeof caption !== "string") return null;
  return {
    type: "state",
    seq: seq as number,
    position,
    duration,
    paused,
    caption,
  };
}

/** Seconds as m:ss. */
export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
