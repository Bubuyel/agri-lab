import type { GridMeta, Place, RainModel } from '../types'

export interface Grid {
  meta: GridMeta
  a: Record<string, Uint16Array | Int8Array | Uint8Array>
}

/** Slice the single binary blob into typed arrays following `meta.layout`. */
export function parseGrid(buf: ArrayBuffer, meta: GridMeta): Grid {
  const a: Grid['a'] = {}
  let off = 0
  for (const [name, type, shape] of meta.layout) {
    const n = shape.reduce((x, y) => x * y, 1)
    if (type === 'u16') {
      a[name] = new Uint16Array(buf, off, n)
      off += n * 2
    } else if (type === 'i8') {
      a[name] = new Int8Array(buf, off, n)
      off += n
    } else {
      a[name] = new Uint8Array(buf, off, n)
      off += n
    }
  }
  return { meta, a }
}

export const cellOf = (m: GridMeta, lat: number, lon: number) => ({
  r: Math.floor((m.lat0 - lat) / m.res),
  c: Math.floor((lon - m.lon0) / m.res),
})
const inside = (m: GridMeta, r: number, c: number) => r >= 0 && c >= 0 && r < m.nrow && c < m.ncol

export type Signal = 'drier' | 'normal' | 'wetter'
export interface MonthOutlook {
  lead: number
  month: number // 1-12 calendar month
  dry: boolean // dry season: below/normal/above is meaningless
  probs: [number, number, number] | null // below / normal / above
  normalBand: [number, number] // mm: p33 – p67 for this month and place
  signal: Signal
  confidence: 'low' | 'some' | 'useful'
}
export interface RainResult {
  months: MonthOutlook[]
  calendar: number[] // 12 monthly normals (mm), Jan..Dec
  last12: number[] // observed mm, oldest → newest
  last12Months: number[] // calendar month of each `last12` entry
  lastMonth: [number, number]
  gridName: string
}

const softmax = (v: number[]) => {
  const m = Math.max(...v)
  const e = v.map((x) => Math.exp(x - m))
  const s = e.reduce((a, b) => a + b, 0)
  return e.map((x) => x / s)
}

/** Pick the finest grid that has data at the point (EAC 0.25° before Africa 0.5°). */
export function pickGrid(grids: Grid[], lat: number, lon: number): Grid | null {
  for (const g of grids) {
    const { r, c } = cellOf(g.meta, lat, lon)
    if (inside(g.meta, r, c) && g.a.state[r * g.meta.ncol + c] !== g.meta.nodata_i8) return g
  }
  return null
}

export function rainOutlook(model: RainModel, grids: Grid[], place: Pick<Place, 'lat' | 'lon'>): RainResult | null {
  const g = pickGrid(grids, place.lat, place.lon)
  if (!g) return null
  const { meta, a } = g
  const N = meta.nrow * meta.ncol
  const { r, c } = cellOf(meta, place.lat, place.lon)
  const cell = r * meta.ncol + c
  const x = [0, 1, 2].map((k) => (a.state[k * N + cell] as number) / meta.state_scale)
  const om = meta.last_month[1]

  // forecast skill flag lives on the coarse Africa grid
  const af = grids.find((q) => q.meta.name === 'africa')
  let skill = [0, 0, 0]
  if (af?.a.skill) {
    const q = cellOf(af.meta, place.lat, place.lon)
    if (inside(af.meta, q.r, q.c)) {
      const n = af.meta.nrow * af.meta.ncol
      skill = [0, 1, 2].map((h) => af.a.skill[h * n + q.r * af.meta.ncol + q.c] as number)
    }
  }

  const months: MonthOutlook[] = []
  for (let h = 1; h <= model.leads; h++) {
    const tm = ((om - 1 + h) % 12) + 1
    const p33 = a.p33[(tm - 1) * N + cell] as number
    const p67 = a.p67[(tm - 1) * N + cell] as number
    const m = model.logit[`${h}_${om}`]
    const dry = p67 < meta.dry_p67_mm || !m
    let probs: MonthOutlook['probs'] = null
    let signal: Signal = 'normal'
    if (!dry) {
      const lg = m.b.map((b, k) => b + m.w[k].reduce((s, w, j) => s + w * x[j], 0))
      probs = softmax(lg) as [number, number, number]
      if (probs[0] - probs[2] > 0.08) signal = 'drier'
      else if (probs[2] - probs[0] > 0.08) signal = 'wetter'
    }
    months.push({
      lead: h, month: tm, dry, probs, normalBand: [p33, p67], signal,
      confidence: (['low', 'some', 'useful'] as const)[skill[h - 1]] ?? 'low',
    })
  }
  const calendar = Array.from({ length: 12 }, (_, mo) => a.mean[mo * N + cell] as number)
  const last12 = Array.from({ length: 12 }, (_, k) => a.last12[k * N + cell] as number)
  const lm = meta.last_month[1]
  const last12Months = Array.from({ length: 12 }, (_, k) => ((lm - 1 - 11 + k + 120) % 12) + 1)
  return { months, calendar, last12, last12Months, lastMonth: meta.last_month, gridName: meta.name }
}
