import Link from "next/link";
import { notFound } from "next/navigation";
import CollectionArt from "@/components/CollectionArt";
import Eyebrow from "@/components/Eyebrow";
import { ChevronLeftIcon } from "@/components/icons";
import { getStories, titleOf } from "@/lib/content";

export default async function CollectionPage({
  params,
}: {
  params: Promise<{ collection: string }>;
}) {
  // the id came from the URL, so an unknown collection is a 404, not a blank page
  const { collection } = await params;
  const stories = await getStories(collection);
  if (stories.length === 0) notFound();

  return (
    <main className="mx-auto max-w-4xl px-6 pt-2 pb-24">
      <Link
        href="/"
        aria-label="Back to the library"
        className="flex size-11 items-center justify-center rounded-[4px] text-ink transition duration-200 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
      >
        <ChevronLeftIcon className="size-5" />
      </Link>

      <div className="mt-8 flex flex-col items-center text-center">
        <Eyebrow>
          {stories.length} {stories.length === 1 ? "Story" : "Stories"}
        </Eyebrow>
        <h1 className="display mt-6 text-4xl/[0.95] sm:text-6xl/[0.95]">
          {titleOf(collection)}
        </h1>
      </div>

      <ul className="mt-14 grid gap-4 sm:grid-cols-2">
        {stories.map((story) => (
          <li key={story.id}>
            <Link
              href={`/library/${collection}/${story.id}`}
              className="group flex h-full flex-col overflow-hidden rounded-[8px] bg-card transition duration-200 hover:ring-2 hover:ring-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <div className="h-28 overflow-hidden">
                <CollectionArt id={story.id} />
              </div>
              <div className="flex flex-1 flex-col px-6 py-7">
                <h2 className="display text-2xl">{story.title}</h2>
                <p className="mono mt-3 flex-1 text-sm leading-relaxed text-quiet">
                  {story.blurb}
                </p>
                <span className="label mt-6 flex items-center gap-2 text-xs text-ink transition group-hover:text-accent">
                  <span aria-hidden="true">■</span> Listen
                </span>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
