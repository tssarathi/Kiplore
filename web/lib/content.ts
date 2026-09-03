// the library on disk, server side only: node:fs cannot be bundled for a client
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";

export type Story = {
  id: string;
  title: string;
  blurb: string;
  script: string[];
};

export type Collection = {
  id: string;
  title: string;
  count: number;
};

export type Voice = {
  id: string;
  name: string;
  elevenLabsId: string;
  look: "elder" | "woman" | "man";
};

// a sibling of web/, so the agent and the client read the same story files
const LIBRARY_DIR = path.join(process.cwd(), "..", "library");
// ids come from the URL and go into a path, so they are held to safe characters
const NAME = /^[A-Za-z0-9_-]+$/;

export async function getVoices(): Promise<Voice[]> {
  const raw = await readFile(path.join(LIBRARY_DIR, "voices.json"), "utf8");
  return JSON.parse(raw) as Voice[];
}

/** One story, or null if the id is unusable or nothing is there. */
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

/** A directory name as a title: "hans-andersen" becomes "Hans Andersen". */
// collections carry no metadata file, and deriving the title keeps it that way
export function titleOf(id: string): string {
  return id
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Every collection holding at least one story. */
// the directory test keeps voices.json out, the count keeps empty ones out
export async function getCollections(): Promise<Collection[]> {
  const entries = await readdir(LIBRARY_DIR, { withFileTypes: true });
  const collections = await Promise.all(
    entries
      .filter((entry) => entry.isDirectory() && NAME.test(entry.name))
      .map(async (entry) => ({
        id: entry.name,
        title: titleOf(entry.name),
        count: (await getStories(entry.name)).length,
      })),
  );
  return collections
    .filter((collection) => collection.count > 0)
    .sort((a, b) => a.title.localeCompare(b.title));
}

/** Every story in a collection, or an empty list if there is no such collection. */
export async function getStories(collection: string): Promise<Story[]> {
  if (!NAME.test(collection)) return [];
  let names: string[];
  try {
    names = await readdir(path.join(LIBRARY_DIR, collection));
  } catch {
    return [];
  }
  const stories = await Promise.all(
    names
      .filter((name) => name.endsWith(".json"))
      .map((name) => getStory(collection, name.slice(0, -5))),
  );
  return stories
    .filter((story): story is Story => story !== null)
    .sort((a, b) => a.title.localeCompare(b.title));
}
