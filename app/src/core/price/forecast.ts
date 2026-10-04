import type { ForecastPoint, PriceModel, PriceSeries } from '../types'

export function addMonths(ym: string, n: number): string {
  const [y, m] = ym.split('-').map(Number)
  const t = y * 12 + (m - 1) + n
  return `${Math.floor(t / 12)}-${String((t % 12) + 1).padStart(2, '0')}`
}

export function evalTrees(trees: number[][][], x: number[]): number {
  let total = 0
  for (const nodes of trees) {
    let i = 0
    while (nodes[i][0] >= 0) i = x[nodes[i][0]] <= nodes[i][1] ? nodes[i][2] : nodes[i][3]
    total += nodes[i][1]
  }
  return total
}

/**
 * log-change d_h = model_h([m1, m3, m6, m12, dev12, vol12, seasonal_h])      (pooled model from notebook 02)
 * forecast_h     = last_price · exp(d_h)
 * interval       = last_price · exp(d_h + z_q · max(vol12, 0.01))            (z calibrated on validation data)
 */
export function forecastSeries(s: PriceSeries, M: PriceModel): ForecastPoint[] {
  const out: ForecastPoint[] = []
  const vol = Math.max(s.f[5], 0.01)
  for (let h = 1; h <= M.horizons; h++) {
    const x = [...s.f, s.sd[h - 1]]
    let d: number
    if (M.type === 'gbdt') d = evalTrees(M.trees![String(h)], x)
    else {
      const { b, w } = M.ridge![String(h)]
      d = b + w.reduce((a, wi, i) => a + wi * x[i], 0)
    }
    const [q10, , q90] = M.interval_q[String(h)]
    out.push({
      h,
      ym: addMonths(s.last, h),
      mid: s.p * Math.exp(d),
      lo: s.p * Math.exp(d + q10 * vol),
      hi: s.p * Math.exp(d + q90 * vol),
    })
  }
  return out
}

export type Trend = 'up' | 'down' | 'flat'

/** Direction over the next 3 months; ±3 % counts as "stable" because it is inside the model's usual error. */
export function trendOf(s: PriceSeries, f: ForecastPoint[]): { trend: Trend; pct: number } {
  const pct = (f[Math.min(2, f.length - 1)].mid / s.p - 1) * 100
  return { trend: pct > 3 ? 'up' : pct < -3 ? 'down' : 'flat', pct }
}

/** The forecast month (1-6 ahead) with the highest expected price. */
export const bestMonth = (f: ForecastPoint[]): ForecastPoint => f.reduce((a, b) => (b.mid > a.mid ? b : a))
