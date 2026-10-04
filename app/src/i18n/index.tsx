import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Lang } from '../core/types'
import { loadLangPack } from '../data/loaders'
import { langInfo } from './languages'
import { STRINGS } from './strings'

interface Ctx {
  lang: Lang
  dir: 'ltr' | 'rtl'
  t: (key: string, vars?: Record<string, string | number>) => string
  month: (m: number, style?: 'short' | 'long') => string
}

const I18n = createContext<Ctx>({ lang: 'en', dir: 'ltr', t: (k) => k, month: () => '' })
export const useI18n = () => useContext(I18n)

/**
 * Lookup order for a UI string: hand-written text for the language → machine-translated language pack → English.
 * (Packs are small JSON files shipped with the app, so every language also works offline.)
 */
export function I18nProvider({ lang, children }: { lang: Lang; children: ReactNode }) {
  const [pack, setPack] = useState<Record<string, string>>({})
  const info = langInfo(lang)

  useEffect(() => {
    document.documentElement.lang = info.bcp
    document.documentElement.dir = info.dir
    let alive = true
    setPack({})
    loadLangPack(lang).then((p) => { if (alive) setPack(p) })
    return () => { alive = false }
  }, [lang, info.bcp, info.dir])

  const value = useMemo<Ctx>(() => {
    const t = (key: string, vars?: Record<string, string | number>) => {
      const s = STRINGS[lang]?.[key] ?? pack[key] ?? STRINGS.en[key] ?? key
      return vars ? s.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? '')) : s
    }
    const month = (m: number, style: 'short' | 'long' = 'short') => {
      for (const loc of [info.bcp, 'en']) {
        try { return new Intl.DateTimeFormat(loc, { month: style }).format(new Date(2021, m - 1, 15)) } catch { /* try next */ }
      }
      return String(m)
    }
    return { lang, dir: info.dir, t, month }
  }, [lang, pack, info.bcp, info.dir])
  return <I18n.Provider value={value}>{children}</I18n.Provider>
}
