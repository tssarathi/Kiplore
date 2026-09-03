export type Look = "elder" | "woman" | "man";

const FACE = "var(--color-card)";
const INK = "var(--color-graphite)";

export default function VoiceAvatar({ look }: { look: Look }) {
  const clip = `head-${look}`;
  return (
    <svg viewBox="0 0 64 64" className="size-full" aria-hidden="true">
      <defs>
        <clipPath id={clip}>
          <circle cx="32" cy="27" r="13" />
        </clipPath>
      </defs>

      <circle cx="32" cy="32" r="32" fill="var(--color-sage)" />
      <path d="M32 44c12 0 21 8 22 20H10c1-12 10-20 22-20z" fill={INK} />
      <rect x="28" y="38" width="8" height="8" fill={FACE} />
      <circle cx="32" cy="27" r="13" fill={FACE} />

      <g clipPath={`url(#${clip})`} fill={INK}>
        {look === "man" && <rect x="17" y="12" width="30" height="9" />}
        {look === "woman" && (
          <>
            <rect x="17" y="12" width="30" height="10" />
            <rect x="17" y="12" width="5" height="30" />
            <rect x="42" y="12" width="5" height="30" />
          </>
        )}
        {look === "elder" && (
          <>
            <rect x="17" y="12" width="30" height="5" />
            <rect x="17" y="17" width="7" height="6" />
            <rect x="40" y="17" width="7" height="6" />
          </>
        )}
      </g>

      {look === "woman" && <circle cx="32" cy="12" r="4.5" fill={INK} />}

      <circle cx="27" cy="27" r="1.7" fill={INK} />
      <circle cx="37" cy="27" r="1.7" fill={INK} />

      {look === "elder" && (
        <rect x="27" y="31.5" width="10" height="2.4" rx="1.2" fill={INK} />
      )}
      <path
        d={look === "elder" ? "M29.5 37h5" : "M28.5 34a4 4 0 0 0 7 0"}
        stroke={INK}
        strokeWidth="1.8"
        strokeLinecap="round"
        fill="none"
      />
    </svg>
  );
}
