/**
 * Daily rain chance, offline: a second-order wet/dry Markov chain per grid cell and month (notebook 05).
 * state = 2·(rained yesterday) + (rained today)  →  P(rain tomorrow | state, month).
 * Without internet the phone cannot know today's weather, so the farmer tells it "did it rain today / yesterday?".
 */
export interface DailyMeta {
  nrow: number; ncol: number; res: number; lon0: number; lat0: number; nodata: number
  eval: { test_years: number[]; brier_skill_by_lead: number[]; reliability_gap_lead1: number }
}
export interface DailyGrid { meta: DailyMeta; p: Uint8Array; clim: Uint8Array; amt: Uint8Array }

export function parseDaily(buf: ArrayBuffer, meta: DailyMeta): DailyGrid {
  const N = meta.nrow * meta.ncol
  const a = new Uint8Array(buf)
  if (a.length !== (12 * 4 + 12 + 12) * N) throw new Error('rain_daily.bin has unexpected size')
  return { meta, p: a.subarray(0, 48 * N), clim: a.subarray(48 * N, 60 * N), amt: a.subarray(60 * N, 72 * N) }
}

export interface DailyResult {
  chance: number[] // P(rain) for day +1 … +days
  monthChance: number // long-run chance of a rainy day this month
  wetDays: number // expected rainy days this month
  wetMm: number // typical rainfall on a rainy day (mm)
}

export function dailyForecast(g: DailyGrid, lat: number, lon: number, month: number, yesterdayWet: boolean, todayWet: boolean, days = 7): DailyResult | null {
  const { meta } = g
  const r = Math.floor((meta.lat0 - lat) / meta.res)
  const c = Math.floor((lon - meta.lon0) / meta.res)
  if (r < 0 || c < 0 || r >= meta.nrow || c >= meta.ncol) return null
  const N = meta.nrow * meta.ncol
  const cell = r * meta.ncol + c
  const m = month - 1
  if (g.clim[m * N + cell] === meta.nodata) return null
  const P = [0, 1, 2, 3].map((s) => g.p[(m * 4 + s) * N + cell] / 255) // P(wet tomorrow | state)
  let dist = [0, 0, 0, 0]
  dist[(yesterdayWet ? 2 : 0) + (todayWet ? 1 : 0)] = 1
  const chance: number[] = []
  for (let L = 0; L < days; L++) {
    const next = [0, 0, 0, 0]
    for (let s = 0; s < 4; s++) {
      const today = s % 2
      next[today * 2 + 1] += dist[s] * P[s] // → wet tomorrow
      next[today * 2] += dist[s] * (1 - P[s]) // → dry tomorrow
    }
    dist = next
    chance.push(dist[1] + dist[3])
  }
  const monthChance = g.clim[m * N + cell] / 255
  const daysInMonth = new Date(2021, month, 0).getDate()
  return { chance, monthChance, wetDays: monthChance * daysInMonth, wetMm: g.amt[m * N + cell] / 4 }
}
