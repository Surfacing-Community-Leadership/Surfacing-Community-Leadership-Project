// The brand signature: a heart with three motion ticks — the neighborly
// answer to HUMAN MADE's heart mark. Red because the heart (and a neighbor
// asking for a hand) is the one thing on this whole app allowed to be loud.
export function HeartMark({ size = 28, color = "var(--accent)", title }) {
  return (
    <svg
      className="heart-mark"
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      role={title ? "img" : "presentation"}
      aria-label={title}
      aria-hidden={title ? undefined : true}
    >
      {/* motion ticks — the heart is on its way somewhere */}
      <g stroke={color} strokeWidth="2.4" strokeLinecap="round">
        <line x1="25" y1="4.5" x2="30" y2="2" />
        <line x1="26" y1="9" x2="31.5" y2="7.5" />
        <line x1="24" y1="1" x2="27" y2="-1" />
      </g>
      <path
        d="M15.6 27.4C8.9 22.7 3.4 18.6 3.4 12.9c0-3.6 2.8-6.3 6.2-6.3 2.2 0 4.3 1.1 5.5 3 1.2-1.9 3.3-3 5.5-3 3.4 0 6.2 2.7 6.2 6.3 0 5.7-5.5 9.8-12.2 14.5-.3.2-.7.2-1 0z"
        fill={color}
      />
    </svg>
  );
}

// The full brand lockup: heart + "Ours" wordmark. Used in the two nav bars.
export function BrandLock({ heartSize = 26 }) {
  return (
    <>
      <HeartMark size={heartSize} title="Ours" />
      <span className="wordmark">Ours</span>
    </>
  );
}
