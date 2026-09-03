import Link from "next/link";
import { notFound } from "next/navigation";
import Eyebrow from "@/components/Eyebrow";
import { ChevronLeftIcon } from "@/components/icons";
import { getStory, getVoices, titleOf } from "@/lib/content";
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
    <main className="mx-auto max-w-2xl px-6 pt-6 pb-24">
      <Link
        href={`/library/${collection}`}
        aria-label={`Back to ${titleOf(collection)}`}
        className="flex size-11 items-center justify-center rounded-[4px] text-ink transition duration-200 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
      >
        <ChevronLeftIcon className="size-5" />
      </Link>

      <div className="mt-12 flex flex-col items-center text-center">
        <Eyebrow>Tonight&rsquo;s Story</Eyebrow>
        <h1 className="display mt-6 text-4xl/[0.95] sm:text-5xl/[0.95]">{found.title}</h1>
        <p className="mono mt-5 max-w-md text-sm leading-relaxed text-quiet">
          {found.blurb}
        </p>
      </div>

      <div className="mt-12">
        <PlayButton
          collection={collection}
          storyId={story}
          voices={voices.map(({ id, name, look }) => ({ id, name, look }))}
        />
      </div>
    </main>
  );
}
