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

export const MAX_RESUME_ATTEMPTS = 7;
export const RESUME_RETRY_BASE_MS = 250;

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

export function formatTime(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
