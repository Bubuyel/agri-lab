import type { ReactNode } from 'react'

/** Minimal stroke icon set (24×24, 1.8 stroke, round caps) in the spirit of SF Symbols. */
const P: Record<string, ReactNode> = {
  home: <><path d="M4 11.2 12 4l8 7.2" /><path d="M6 10v9.2a.8.8 0 0 0 .8.8H10v-5h4v5h3.2a.8.8 0 0 0 .8-.8V10" /></>,
  scan: <><path d="M4 8V6.5A2.5 2.5 0 0 1 6.5 4H8M16 4h1.5A2.5 2.5 0 0 1 20 6.5V8M20 16v1.5a2.5 2.5 0 0 1-2.5 2.5H16M8 20H6.5A2.5 2.5 0 0 1 4 17.5V16" /><path d="M16 8.2c-4.6.2-7 2.6-7.2 7.2 4.6-.2 7-2.6 7.2-7.2Z" /><path d="M8.8 15.4 12 12" /></>,
  camera: <><path d="M4.5 8.5A1.5 1.5 0 0 1 6 7h1.6l1-1.5A1.5 1.5 0 0 1 9.9 5h4.2a1.5 1.5 0 0 1 1.3.6l1 1.4H18a1.5 1.5 0 0 1 1.5 1.5V17a1.5 1.5 0 0 1-1.5 1.5H6A1.5 1.5 0 0 1 4.5 17Z" /><circle cx="12" cy="12.4" r="3.2" /></>,
  photo: <><rect x="4" y="5" width="16" height="14" rx="3" /><circle cx="9" cy="10" r="1.6" /><path d="m5 17 4.5-4.2a1.5 1.5 0 0 1 2 0L15 16l1.6-1.4a1.5 1.5 0 0 1 2 0L20 16" /></>,
  chart: <><path d="M4 19V5" /><path d="M4 19h16" /><path d="m7.5 14 3.3-3.8 3 2.6L19 7.5" /><path d="M15.6 7.5H19V11" /></>,
  rain: <><path d="M7 15.5A4.2 4.2 0 0 1 7.4 7.1a5.2 5.2 0 0 1 10 1.6A3.5 3.5 0 0 1 17 15.5" /><path d="m8.5 18.2-.9 2M12.5 18.2l-.9 2M16.5 18.2l-.9 2" /></>,
  layers: <><path d="m12 4 8.5 4.6L12 13.2 3.5 8.6Z" /><path d="m3.5 12.4 8.5 4.6 8.5-4.6" /><path d="m3.5 16 8.5 4.6 8.5-4.6" /></>,
  sprout: <><path d="M12 20v-7" /><path d="M12 13c0-3.6-2.4-5.8-6-5.8 0 3.8 2.3 5.8 6 5.8Z" /><path d="M12 11.6c0-3.2 2-5.6 6-5.6 0 3.6-2.2 5.6-6 5.6Z" /><path d="M8.5 20h7" /></>,
  settings: <><path d="M5 7h9M18 7h1M5 17h1M10 17h9" /><circle cx="16" cy="7" r="2.2" /><circle cx="8" cy="17" r="2.2" /></>,
  back: <path d="m14.5 5.5-6.5 6.5 6.5 6.5" />,
  chevron: <path d="m9.5 5.5 6.5 6.5-6.5 6.5" />,
  check: <path d="m5.5 12.5 4.2 4.2L18.5 8" />,
  alert: <><path d="M12 4.2 3.2 19.2a.8.8 0 0 0 .7 1.2h16.2a.8.8 0 0 0 .7-1.2Z" /><path d="M12 10v4.2M12 17.2v.1" /></>,
  help: <><circle cx="12" cy="12" r="8.5" /><path d="M9.6 9.6a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2.9-1.2 1.8M12 16.8v.1" /></>,
  install: <><path d="M12 4v11" /><path d="m7.5 11 4.5 4.5 4.5-4.5" /><path d="M5 19h14" /></>,
  share: <><path d="M12 15V4" /><path d="m8 7.5 4-4 4 4" /><path d="M7 11H6.5A1.5 1.5 0 0 0 5 12.5v6A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5v-6a1.5 1.5 0 0 0-1.5-1.5H17" /></>,
  addSquare: <><rect x="4.5" y="4.5" width="15" height="15" rx="3.5" /><path d="M12 8.5v7M8.5 12h7" /></>,
  dots: <><circle cx="12" cy="5.5" r="1.3" /><circle cx="12" cy="12" r="1.3" /><circle cx="12" cy="18.5" r="1.3" /></>,
  menu: <path d="M5 7h14M5 12h14M5 17h14" />,
  globe: <><circle cx="12" cy="12" r="8.5" /><path d="M3.5 12h17M12 3.5c2.4 2.4 3.6 5.2 3.6 8.5s-1.2 6.1-3.6 8.5c-2.4-2.4-3.6-5.2-3.6-8.5s1.2-6.1 3.6-8.5Z" /></>,
  sun: <><circle cx="12" cy="12" r="3.8" /><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.4 1.4M16.6 16.6 18 18M18 6l-1.4 1.4M7.4 16.6 6 18" /></>,
  moon: <path d="M19.5 14.6A7.8 7.8 0 0 1 9.4 4.5a7.8 7.8 0 1 0 10.1 10.1Z" />,
  pin: <><path d="M12 20.5s6-5.2 6-10.1A6 6 0 0 0 6 10.4c0 4.9 6 10.1 6 10.1Z" /><circle cx="12" cy="10.2" r="2.2" /></>,
  drop: <path d="M12 3.8s5.8 5.7 5.8 10a5.8 5.8 0 0 1-11.6 0c0-4.3 5.8-10 5.8-10Z" />,
  wifiOff: <><path d="M3.5 9.2a13 13 0 0 1 4-2.4M20.5 9.2a13 13 0 0 0-8.5-3.1M6.8 12.8a8 8 0 0 1 3-1.7M17.2 12.8a8 8 0 0 0-3.8-2M9.7 16.2a4 4 0 0 1 4.6 0" /><path d="M12 19.5v.1" /><path d="M4 4l16 16" /></>,
  sparkles: <><path d="M10 4l1.6 4.4L16 10l-4.4 1.6L10 16l-1.6-4.4L4 10l4.4-1.6Z" /><path d="M17.5 14.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z" /></>,
  flask: <><path d="M9.5 4h5M10.5 4v5.2L5.4 18a1.6 1.6 0 0 0 1.4 2.4h10.4a1.6 1.6 0 0 0 1.4-2.4l-5.1-8.8V4" /><path d="M8 14.5h8" /></>,
  up: <path d="M5 15 12 8l7 7" />,
  down: <path d="M5 9l7 7 7-7" />,
  star: <path d="m12 4.2 2.4 5 5.4.7-4 3.7 1 5.4L12 16.4l-4.8 2.6 1-5.4-4-3.7 5.4-.7Z" />,
  info: <><circle cx="12" cy="12" r="8.5" /><path d="M12 11v5M12 7.9v.1" /></>,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  leaf: <><path d="M19 5c-8.5.2-13 4-13.2 12.2C14.4 17 18.8 13.4 19 5Z" /><path d="M5.2 20.5C7 15.4 10 12 14 9.6" /></>,
  bolt: <path d="M13 3.5 6 13h5l-1 7.5L18 11h-5Z" />,
  sound: <><path d="M5 10v4h3l4 3.5v-11L8 10Z" /><path d="M15.5 9.5a3.5 3.5 0 0 1 0 5M18 7a7 7 0 0 1 0 10" /></>,
  trash: <><path d="M5 7h14M10 7V5h4v2M7 7l.8 12h8.4L17 7" /></>,
}

export type IconName = keyof typeof P

export function Icon({ name, size = 22, className = '', strokeWidth = 1.8 }: { name: IconName; size?: number; className?: string; strokeWidth?: number }) {
  return (
    <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round" className={`icon ${name === 'back' || name === 'chevron' ? 'mirror' : ''} ${className}`} aria-hidden="true">
      {P[name]}
    </svg>
  )
}
