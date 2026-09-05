type IconProps = { className?: string };

const line = {
  fill: "none" as const,
  stroke: "currentColor",
  strokeWidth: 2,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function PlayIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path d="M7 4.5v15l12-7.5z" fill="currentColor" />
    </svg>
  );
}

export function PauseIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect x="6.5" y="5" width="4" height="14" rx="1.5" fill="currentColor" />
      <rect x="13.5" y="5" width="4" height="14" rx="1.5" fill="currentColor" />
    </svg>
  );
}

export function BackIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" {...line}>
      <path d="M3 5v6h6" />
      <path d="M3.5 11a8.5 8.5 0 1 1 2 7" />
    </svg>
  );
}

export function ForwardIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" {...line}>
      <path d="M21 5v6h-6" />
      <path d="M20.5 11a8.5 8.5 0 1 0-2 7" />
    </svg>
  );
}

export function ChevronLeftIcon({ className }: IconProps) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true" {...line}>
      <path d="M15 5l-7 7 7 7" />
    </svg>
  );
}
