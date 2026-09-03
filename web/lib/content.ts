import { readFile } from "node:fs/promises";
import path from "node:path";

export type Story = {
  id: string;
  title: string;
  blurb: string;
  script: string[];
};

export type Voice = {
  id: string;
  name: string;
  elevenLabsId: string;
};

const LIBRARY_DIR = path.join(process.cwd(), "..", "library");
const NAME = /^[A-Za-z0-9_-]+$/;

export async function getVoices(): Promise<Voice[]> {
  const raw = await readFile(path.join(LIBRARY_DIR, "voices.json"), "utf8");
  return JSON.parse(raw) as Voice[];
}

export async function getStory(
  collection: string,
  storyId: string,
): Promise<Story | null> {
  if (!NAME.test(collection) || !NAME.test(storyId)) return null;
  try {
    const raw = await readFile(
      path.join(LIBRARY_DIR, collection, `${storyId}.json`),
      "utf8",
    );
    return JSON.parse(raw) as Story;
  } catch {
    return null;
  }
}
