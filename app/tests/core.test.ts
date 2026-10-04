import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { diagnose, softmax } from '../src/core/vision/decide'
import { addMonths, bestMonth, forecastSeries, trendOf } from '../src/core/price/forecast'
import { convert } from '../src/core/price/markets'
import { haversine } from '../src/core/geo'
import { parseGrid, rainOutlook } from '../src/core/rain/outlook'
import type { RainModel, VisionMeta } from '../src/core/types'

const fx = JSON.parse(readFileSync(new URL('./fixtures.json', import.meta.url), 'utf8'))
const data = (f: string) => new URL(`../public/data/${f}`, import.meta.url)

/* ---------------- vision decision logic ---------------- */
const meta: VisionMeta = {
  input_size: 160, mean: [0, 0, 0], std: [1, 1, 1], model_file: 'x.onnx',
  crops: ['coffee', 'maize', 'not_plant'],
  labels: ['coffee___healthy', 'coffee___rust', 'maize___healthy', 'maize___common_rust', 'not_plant'],
  label_to_crop: [0, 0, 1, 1, 2], not_plant_crop_index: 2, not_plant_label_index: 4,
  temperature: 1, thresholds: { not_plant_p: 0.5, min_confidence: 0.6 },
}

describe('vision decision', () => {
  it('softmax sums to 1', () => {
    expect(softmax([1, 2, 3]).reduce((a, b) => a + b)).toBeCloseTo(1, 10)
  })
  it('rejects a non-plant', () => {
    expect(diagnose([0, 0, 5], [0, 0, 0, 0, 5], meta).kind).toBe('not_plant')
  })
  it('asks to retake when the crop is uncertain', () => {
    expect(diagnose([1, 1.1, 0], [1, 0, 1, 0, 0], meta).kind).toBe('unsure')
  })
  it('restricts the disease to the predicted crop', () => {
    // crop head says maize; label head (wrongly) prefers coffee___rust — must still answer a maize class
    const d = diagnose([0, 6, -3], [0, 9, 1, 2, -3], meta)
    expect(d.kind).toBe('ok')
    if (d.kind === 'ok') {
      expect(d.crop).toBe('maize')
      expect(d.label.startsWith('maize___')).toBe(true)
      expect(d.label).toBe('maize___common_rust')
    }
  })
})

/* ---------------- price forecast parity with the notebook ---------------- */
describe('price forecast (matches notebook 02)', () => {
  const model = JSON.parse(readFileSync(data('price_model.json'), 'utf8'))
  for (const row of fx.price) {
    it(`${row.series.c} ${row.series.com}`, () => {
      const f = forecastSeries(row.series, model)
      f.forEach((p, i) => {
        expect(p.mid).toBeCloseTo(row.forecast[i][0], 4)
        expect(p.lo).toBeCloseTo(row.forecast[i][1], 4)
        expect(p.hi).toBeCloseTo(row.forecast[i][2], 4)
        expect(p.lo).toBeLessThan(p.hi)
      })
      expect(bestMonth(f).mid).toBeGreaterThan(0)
      expect(['up', 'down', 'flat']).toContain(trendOf(row.series, f).trend)
    })
  }
  it('addMonths wraps years', () => {
    expect(addMonths('2026-11', 3)).toBe('2027-02')
    expect(addMonths('2026-08', 1)).toBe('2026-09')
  })
})

describe('currency + geo', () => {
  const fxf = { as_of: '', rates: { USD: { usd_per: 1, per_usd: 1, name: '' }, RWF: { usd_per: 0.001, per_usd: 1000, name: '' } } }
  it('converts through USD', () => {
    expect(convert(1000, 'RWF', 'USD', fxf)).toBeCloseTo(1)
    expect(convert(1, 'USD', 'RWF', fxf)).toBeCloseTo(1000)
    expect(convert(1, 'XXX', 'USD', fxf)).toBeNull()
  })
  it('haversine Kigali–Nairobi ≈ 755 km', () => {
    expect(haversine(-1.95, 30.06, -1.29, 36.82)).toBeGreaterThan(740)
    expect(haversine(-1.95, 30.06, -1.29, 36.82)).toBeLessThan(770)
  })
})

/* ---------------- rain outlook parity with the notebook ---------------- */
describe('rain outlook (matches notebook 03)', () => {
  const model: RainModel = JSON.parse(readFileSync(data('rain_model.json'), 'utf8'))
  const buf = (n: string) => {
    const b = readFileSync(data(`rain_${n}.bin`))
    return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer
  }
  const grids = ['eac', 'africa'].map((n) => parseGrid(buf(n), model.grids[n]))
  for (const p of fx.rain) {
    it(p.name, () => {
      const r = rainOutlook(model, grids, p)
      if (!p.expect) return expect(r).toBeNull()
      expect(r).not.toBeNull()
      r!.months.forEach((m, i) => {
        const e = p.expect.months[i]
        expect(m.month).toBe(e.month)
        expect(m.dry).toBe(e.dry)
        expect(m.normalBand).toEqual([e.p33, e.p67])
        if (!e.dry) e.probs.forEach((v: number, k: number) => expect(m.probs![k]).toBeCloseTo(v, 6))
      })
      expect(r!.calendar).toHaveLength(12)
    })
  }
})
