/**
 * Agri Lab mark: a laboratory flask (science) with two leaves sprouting from its neck (agriculture) and an AI sparkle
 * in the liquid (intelligence). Minimal, monochrome strokes + a single light-green accent.
 * The flask uses `currentColor`, so it works on any background in light and dark mode.
 */
export function LogoMark({ size = 64, animate = false, className = '' }: { size?: number; animate?: boolean; className?: string }) {
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} className={`logo-mark ${animate ? 'draw' : ''} ${className}`} role="img" aria-label="Agri Lab">
      <g className="leaves">
        <path className="leaf l1" d="M47.5 33.5C39 33.5 34.2 27.4 35.2 19.6C42.4 19.6 47.4 24.8 47.5 33.5Z" />
        <path className="leaf l2" d="M52.5 33.5C51.6 22 59.6 13.6 74.5 11.4C75.6 25.6 66.8 33.6 52.5 33.5Z" />
      </g>
      <path className="flask" d="M40.5 38V52L24.5 79.5C19.5 88.5 25 92 31 92H69C75 92 80.5 88.5 75.5 79.5L59.5 52V38M35.5 38H64.5" />
      <path className="wave" d="M29.5 80.5Q39 74.5 50 79.5T70.5 80.5" />
      <path className="spark" d="M50 62L52.7 67.3L58 70L52.7 72.7L50 78L47.3 72.7L42 70L47.3 67.3Z" />
      <path className="spark s2" d="M61.5 61.5L62.5 63.6L64.6 64.6L62.5 65.6L61.5 67.7L60.5 65.6L58.4 64.6L60.5 63.6Z" />
    </svg>
  )
}

/** Rounded-square app icon version (used in the splash, install sheet and settings). */
export function AppIcon({ size = 72 }: { size?: number }) {
  return (
    <div className="app-icon" style={{ width: size, height: size, borderRadius: size * 0.235 }}>
      <LogoMark size={size * 0.72} />
    </div>
  )
}

export function Wordmark({ size = 28 }: { size?: number }) {
  return (
    <span className="wordmark" style={{ fontSize: size }}>
      Agri <b>Lab</b>
    </span>
  )
}
