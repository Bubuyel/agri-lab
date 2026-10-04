import * as Flags from 'country-flag-icons/string/3x2'

/** Inline SVG flag (bundled, so it also renders on Windows where flag emojis show as letters, and works offline). */
export function Flag({ code, size = 26 }: { code: string; size?: number }) {
  const svg = (Flags as Record<string, string>)[code]
  if (!svg) return <span className="flag" style={{ width: size, height: size * 0.67 }} />
  return <span className="flag" style={{ width: size, height: size * 0.67 }} aria-hidden="true" dangerouslySetInnerHTML={{ __html: svg }} />
}
