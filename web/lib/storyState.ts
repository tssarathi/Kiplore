export type StoryState = {
  seq: number;
  position: number;
  paused: boolean;
  caption: string | null;
};

export function parseStoryState(payload: Uint8Array): StoryState | null {
  let value: unknown;
  try {
    value = JSON.parse(new TextDecoder().decode(payload));
  } catch {
    return null;
  }
  if (typeof value !== "object" || value === null) return null;
  const { seq, position, paused, caption } = value as Record<string, unknown>;
  if (!Number.isInteger(seq) || (seq as number) <= 0) return null;
  if (typeof position !== "number" || !Number.isFinite(position) || position < 0) {
    return null;
  }
  if (typeof paused !== "boolean") return null;
  if (caption !== null && typeof caption !== "string") return null;
  return { seq: seq as number, position, paused, caption };
}
