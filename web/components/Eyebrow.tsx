export default function Eyebrow({ children }: { children: React.ReactNode }) {
  return (
    <p className="label flex items-center gap-2 text-sm text-quiet">
      <span aria-hidden="true" className="text-ink">
        ■
      </span>
      {children}
    </p>
  );
}
