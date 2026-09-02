import { notFound } from "next/navigation";
import { getStory, getVoices } from "@/lib/content";
import PlayButton from "./PlayButton";

export default async function StoryPage({
  params,
}: {
  params: Promise<{ collection: string; story: string }>;
}) {
  const { collection, story } = await params;
  const found = await getStory(collection, story);
  if (!found) notFound();

  const voices = await getVoices();

  return (
    <div>
      <h1>{found.title}</h1>
      <p>{found.blurb}</p>
      <PlayButton
        collection={collection}
        storyId={story}
        voices={voices.map(({ id, name }) => ({ id, name }))}
      />
    </div>
  );
}
