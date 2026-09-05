const W = 240;
const H = 100;
const CELL = 3;

function seeded(id: string) {
  let hash = 2166136261;
  for (const char of id) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619);
  }
  return () => {
    hash = Math.imul(hash ^ (hash >>> 15), 2246822507);
    hash = Math.imul(hash ^ (hash >>> 13), 3266489909);
    return ((hash ^= hash >>> 16) >>> 0) / 4294967296;
  };
}

export default function CollectionArt({ id }: { id: string }) {
  
  const random = seeded(id);
  const angle = random() * Math.PI * 2;
  const dx = Math.cos(angle);
  const dy = Math.sin(angle);

  const dots: { x: number; y: number }[] = [];
  for (let x = 0; x < W; x += CELL) {
    for (let y = 0; y < H; y += CELL) {
      const along = ((x / W - 0.5) * dx + (y / H - 0.5) * dy + 0.75) / 1.5;
      const density = Math.min(1, Math.max(0, (along - 0.12) * 1.9));
      if (random() < density) dots.push({ x, y });
    }
  }

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="xMidYMid slice"
      className="h-full w-full"
      aria-hidden="true"
    >
      <rect width={W} height={H} fill="var(--color-sage)" />
      <g fill="var(--color-ink)">
        {dots.map((dot, i) => (
          <rect key={i} x={dot.x} y={dot.y} width={CELL - 1} height={CELL - 1} />
        ))}
      </g>
    </svg>
  );
}
