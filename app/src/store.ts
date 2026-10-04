import { useCallback, useEffect, useState } from 'react'
import type { Lang, Place } from './core/types'
import type { ThemeChoice } from './theme'

/** "Did it rain?" answers the farmer gave on a given day (used to start the daily rain chain). */
export interface RainAnswer { d: string; y: boolean; t: boolean }

export interface Settings {
  lang: Lang | null // null until chosen on first launch
  onboarded: boolean
  theme: ThemeChoice
  place: Place | null
  currency: string | null // ISO code the user wants prices converted to (null = local currency)
  lastCrop: string | null // crop id grown last season (rotation advice)
  rain: RainAnswer | null
}

const KEY = 'agriai.settings.v2'
const DEFAULTS: Settings = { lang: null, onboarded: false, theme: 'auto', place: null, currency: null, lastCrop: null, rain: null }

function read(): Settings {
  try {
    const old = JSON.parse(localStorage.getItem('agriai.settings.v1') || 'null') as Partial<Settings> | null // migrate v1
    const cur = JSON.parse(localStorage.getItem(KEY) || 'null') as Partial<Settings> | null
    const merged = { ...DEFAULTS, ...(old ?? {}), ...(cur ?? {}) }
    if (old && !cur && old.lang) merged.onboarded = true // returning users skip the walkthrough
    return merged
  } catch {
    return DEFAULTS
  }
}

/** Tiny persisted store. localStorage can throw in private mode, so every access is guarded. */
export function useSettings() {
  const [s, setS] = useState<Settings>(read)
  useEffect(() => {
    try { localStorage.setItem(KEY, JSON.stringify(s)) } catch { /* ignore */ }
  }, [s])
  const update = useCallback((p: Partial<Settings>) => setS((o) => ({ ...o, ...p })), [])
  return [s, update] as const
}

export const todayKey = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
