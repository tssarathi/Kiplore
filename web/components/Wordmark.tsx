import Link from "next/link";

export default function Wordmark() {
  return (
    <header className="flex justify-center pt-4 pb-2">
      <Link
        href="/"
        aria-label="Kiplore, home"
        className="display flex h-11 items-center px-3 text-2xl leading-none transition-colors duration-200 hover:text-accent focus-visible:ring-2 focus-visible:ring-accent focus-visible:outline-none"
      >
        KIPLORE
      </Link>
    </header>
  );
}
