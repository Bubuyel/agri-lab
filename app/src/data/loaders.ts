import type { LandModel } from '../core/land/land'
import type { DailyMeta } from '../core/rain/daily'
import type { AdviceBundle, FaoFile, FxFile, MarketsFile, PriceModel, PriceSeries, RainModel, VisionMeta } from '../core/types'

/** Resolve a path inside `public/` relative to the page (works under any sub-path hosting, e.g. GitHub Pages). */
export const asset = (p: string) => new URL(p, document.baseURI).href

const memo = new Map<string, Promise<unknown>>()
function once<T>(key: string, f: () => Promise<T>): Promise<T> {
  if (!memo.has(key)) {
    const p = f()
    memo.set(key, p)
    p.catch(() => memo.delete(key))
  }
  return memo.get(key) as Promise<T>
}

const json = <T,>(p: string) =>
  once<T>(p, async () => {
    const r = await fetch(asset(p))
    if (!r.ok) throw new Error(`${p}: ${r.status}`)
    return r.json()
  })
const bin = (p: string) =>
  once<ArrayBuffer>(p, async () => {
    const r = await fetch(asset(p))
    if (!r.ok) throw new Error(`${p}: ${r.status}`)
    return r.arrayBuffer()
  })

export const loadVisionMeta = () => json<VisionMeta>('data/labels.json')
export const loadAdvice = () => json<AdviceBundle>('data/advice.json')
export const loadPriceModel = () => json<PriceModel>('data/price_model.json')
export const loadPriceSeries = () => json<PriceSeries[]>('data/price_series.json')
export const loadMarkets = () => json<MarketsFile>('data/markets.json')
export const loadFx = () => json<FxFile>('data/fx.json')
export const loadFao = () => json<FaoFile>('data/faostat_insights.json')
export const loadCountries = () => json<Record<string, string>>('data/countries.json')
export const loadRainModel = () => json<RainModel>('data/rain_model.json')
export const loadRainBin = (name: string) => bin(`data/rain_${name}.bin`)
export const loadLandModel = () => json<LandModel>('data/land_model.json')
export const loadLandBin = (name: string) => bin(`data/land_${name}.bin`)
export const loadDailyMeta = () => json<DailyMeta>('data/rain_daily.json')
export const loadDailyBin = () => bin('data/rain_daily.bin')

/** Machine-translated UI pack for a language (public/data/lang/<code>.json). Missing pack → {} (falls back to English). */
export const loadLangPack = (code: string) =>
  once<Record<string, string>>(`lang/${code}`, async () => {
    const r = await fetch(asset(`data/lang/${code}.json`))
    return r.ok ? ((await r.json()) as { ui?: Record<string, string> }).ui ?? {} : {}
  }).catch(() => ({} as Record<string, string>))
