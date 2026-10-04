import { existsSync, readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { cropShares, fertilizerPlan, nutrientLevel, parseLand, phClass, rotationMultiplier, sampleLand, trap, type LandModel } from '../src/core/land/land'
import { dailyForecast, parseDaily } from '../src/core/rain/daily'

const data = (f: string) => new URL(`../public/data/${f}`, import.meta.url)
const buf = (f: string) => { const b = readFileSync(data(f)); return b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength) as ArrayBuffer }
const model: LandModel = JSON.parse(readFileSync(data('land_model.json'), 'utf8'))
const fixtures = JSON.parse(readFileSync(new URL('./land_fixtures.json', import.meta.url), 'utf8'))

describe('land model (matches notebook 06)', () => {
  const grids = ['eac', 'africa'].map((n) => parseLand(buf(`land_${n}.bin`), model, n))

  it('trapezoid membership: 1 at the optimum centre, 0.85 at its edge, 0 outside the absolute range', () => {
    expect(trap(22.5, [10, 18, 27, 35])).toBeCloseTo(1, 6)
    expect(trap(18, [10, 18, 27, 35])).toBeCloseTo(0.85, 6)
    expect(trap(9, [10, 18, 27, 35])).toBe(0)
    expect(trap(40, [10, 18, 27, 35])).toBe(0)
  })

  for (const f of fixtures) {
    it(`${f.place}: decoded soil + crop shares equal Python (all rotations)`, () => {
      const soil = sampleLand(model, grids, f.lat, f.lon)
      expect(soil).not.toBeNull()
      for (const k of Object.keys(f.soil)) expect((soil as unknown as Record<string, number>)[k]).toBeCloseTo(f.soil[k], 4)
      for (const prevId of ['None', 'maize', 'bean']) {
        const prev = model.crops.find((c) => c.id === prevId) ?? null
        const sh = cropShares(model, soil!, prev)
        for (const row of sh) {
          const i = model.crops.findIndex((c) => c.id === row.crop.id)
          expect(row.pct).toBeCloseTo(f.shares[prevId][i], 3)
        }
        const total = sh.reduce((a, r) => a + r.pct, 0)
        expect(total).toBeCloseTo(100, 6)
      }
    })
  }

  it('rotation: legumes after cereals are favoured, same crop again is penalised', () => {
    const maize = model.crops.find((c) => c.id === 'maize')!, bean = model.crops.find((c) => c.id === 'bean')!
    expect(rotationMultiplier(maize, bean).m).toBeGreaterThan(1)
    expect(rotationMultiplier(maize, maize).m).toBeLessThan(0.5)
    expect(rotationMultiplier(null, maize).m).toBe(1)
  })

  it('fertiliser plan only lists low nutrients the crop needs', () => {
    const maize = model.crops.find((c) => c.id === 'maize')!
    const poor = { tmean: 22, tmin: 12, rain: 900, wet: 6, ph: 4.8, n: 0.5, p: 3, k: 40, oc: 6, cec: 8, clay: 20, sand: 60 }
    const items = fertilizerPlan(model, poor, maize).map((i) => i.nutrient).sort()
    expect(items).toEqual(['k', 'n', 'oc', 'p', 'ph'])
    const rich = { ...poor, ph: 6.4, n: 2.5, p: 30, k: 300, oc: 30, cec: 25 }
    expect(fertilizerPlan(model, rich, maize)).toHaveLength(0)
    const bean = model.crops.find((c) => c.id === 'bean')!
    expect(fertilizerPlan(model, poor, bean).map((i) => i.nutrient)).not.toContain('n') // legumes fix their own nitrogen
    expect(nutrientLevel(model, 'k', 40)).toBe('low'); expect(phClass(model, 4.8)).toBe('acid')
  })
})

const hasDaily = existsSync(data('rain_daily.bin')) && existsSync(new URL('./daily_fixtures.json', import.meta.url))
describe.skipIf(!hasDaily)('daily rain chain (matches notebook 05)', () => {
  const grid = () => parseDaily(buf('rain_daily.bin'), JSON.parse(readFileSync(data('rain_daily.json'), 'utf8')))
  const fixtures = () => JSON.parse(readFileSync(new URL('./daily_fixtures.json', import.meta.url), 'utf8'))
  it('replays the Python Markov chain for every fixture', () => {
    const g = grid(), fx = fixtures()
    expect(fx.length).toBeGreaterThan(10)
    for (const f of fx) {
      const r = dailyForecast(g, f.lat, f.lon, f.month, f.y, f.t, 7)!
      f.chance.forEach((c: number, i: number) => expect(r.chance[i]).toBeCloseTo(c, 8))
      expect(r.monthChance).toBeCloseTo(f.monthChance, 8)
    }
  })
  it('rain spells persist: a wet today raises tomorrow, and the effect fades with lead time', () => {
    const g = grid()
    const wet = dailyForecast(g, -1.95, 30.06, 4, true, true, 7)!, dry = dailyForecast(g, -1.95, 30.06, 4, false, false, 7)!
    expect(wet.chance[0]).toBeGreaterThan(dry.chance[0])
    expect(wet.chance[0] - dry.chance[0]).toBeGreaterThan(wet.chance[6] - dry.chance[6])
  })
  it('returns null over the ocean', () => { expect(dailyForecast(grid(), -20, -10, 4, false, false)).toBeNull() })
})
