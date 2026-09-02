import { readFile } from "node:fs/promises";
import path from "node:path";

export type Story = {
  id: string;
  title: string;
  blurb: string;
  script: string[];
};

const LIBRARY_DIR = path.join(process.cwd(), "..", "library");

export async function getStory(
  collection: string,
  storyId: string,
): Promise<Story | null> {
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
