import { haversine } from '../geo'
import type { FxFile, Market, MarketsFile, PriceSeries } from '../types'

export interface NearbyMarket {
  market: Market
  km: number
  priceLocal: number
  priceUsd: number
  ym: string
}

/** Markets that recently reported `s.com` per kg/l, nearest first. */
export function nearbyMarkets(file: MarketsFile, s: PriceSeries, lat: number, lon: number, limit = 6, maxKm = 400): NearbyMarket[] {
  const ci = file.commodities.indexOf(s.com)
  if (ci < 0) return []
  const rows: NearbyMarket[] = []
  for (const m of file.markets) {
    const e = m.p.find((p) => p[0] === ci && p[1] === s.u)
    if (!e) continue
    rows.push({ market: m, km: haversine(lat, lon, m.la, m.lo), priceLocal: e[2] as number, priceUsd: e[3] as number, ym: e[4] as string })
  }
  rows.sort((a, b) => a.km - b.km)
  const near = rows.filter((r) => r.km <= maxKm).slice(0, limit)
  return near.length ? near : rows.slice(0, 3)
}

/** Convert using the exchange rates implied by WFP data (price / usdprice), refreshed with every data release. */
export function convert(amount: number, from: string, to: string, fx: FxFile): number | null {
  const a = fx.rates[from]
  const b = fx.rates[to]
  if (!a || !b) return null
  return (amount * a.usd_per) / b.usd_per
}

export function formatMoney(v: number): string {
  if (!isFinite(v)) return '–'
  const a = Math.abs(v)
  const d = a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3
  return v.toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: 0 })
}
