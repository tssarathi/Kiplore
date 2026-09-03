import Link from "next/link";
import CollectionArt from "@/components/CollectionArt";
import { getCollections } from "@/lib/content";

// a server component: collections are read off disk before the markup is sent
export default async function HomePage() {
  const collections = await getCollections();

  return (
    <main className="mx-auto max-w-4xl px-6 pt-16 pb-24 sm:pt-20">
      <div className="flex flex-col items-center text-center">
        <h1 className="display text-[38px]/[0.95] tracking-[-0.03em] sm:text-7xl/[0.95]">
          Once upon
          <br />
          a time
        </h1>
        <p className="label mt-6 text-xs/[1.2] sm:text-sm/[1.2]">Tales you&rsquo;ll love</p>
      </div>

      <h2 className="label mt-14 flex items-center justify-center gap-2 text-sm text-quiet">
        <span aria-hidden="true" className="text-ink">
          ■
        </span>
        Library
      </h2>

      <ul className="mt-8 grid gap-4 sm:grid-cols-2">
        {collections.map((collection) => (
          <li key={collection.id}>
            <Link
              href={`/library/${collection.id}`}
              className="group block overflow-hidden rounded-[8px] bg-card transition duration-200 hover:ring-2 hover:ring-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
            >
              <div className="h-32 overflow-hidden">
                <CollectionArt id={collection.id} />
              </div>
              <div className="px-6 py-7">
                <h2 className="display text-2xl">{collection.title}</h2>
                <p className="label mt-2 text-xs text-quiet">
                  {collection.count}{" "}
                  {collection.count === 1 ? "Story" : "Stories"}
                </p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
