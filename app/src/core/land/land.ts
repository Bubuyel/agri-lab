/**
 * "My land": soil nutrients, fertiliser advice and crop suitability from satellite-derived maps.
 * Mirrors notebooks/src/06_land_soil_crops.py (parity-tested against Python-generated fixtures).
 */
import type { Lang } from '../types'

export interface LayerDef { key: string; offset: number; scale: number; log: boolean }
export interface GridDef { nrow: number; ncol: number; res: number; lon0: number; lat0: number }
export interface Crop {
  id: string; fam: string; T: number[]; R: number[]; pH: number[]; cycle: number; kill: number
  tex: 'light' | 'heavy' | 'any'; dem: string; perennial: boolean; legume: boolean; w: number
  names: Partial<Record<Lang | 'en', string>>
}
export interface FertRule { product: string; rate_low: [number, number]; note: string }
export interface LandModel {
  layers: LayerDef[]; grids: Record<string, GridDef>; crops: Crop[]
  nutrient_classes: Record<string, [number, number]>; fert: Record<string, FertRule>
  ph_acid: number; ph_alkaline: number; share_top: number; share_floor: number; share_power: number
  validation: { staple_recall_top6: number; places: number }
}

export interface LandGrid { name: string; def: GridDef; data: Uint8Array; layerIndex: Record<string, number> }
export interface Soil {
  tmean: number; tmin: number; rain: number; wet: number
  ph: number; n: number; p: number; k: number; oc: number; cec: number; clay: number; sand: number
}
export interface LandSample extends Soil { grid: string }

export function parseLand(buf: ArrayBuffer, model: LandModel, name: string): LandGrid {
  const def = model.grids[name]
  const data = new Uint8Array(buf)
  const layerIndex: Record<string, number> = {}
  model.layers.forEach((l, i) => { layerIndex[l.key] = i })
  if (data.length !== model.layers.length * def.nrow * def.ncol) throw new Error(`land_${name}.bin has unexpected size`)
  return { name, def, data, layerIndex }
}

const cellIndex = (g: LandGrid, lat: number, lon: number) => {
  const r = Math.floor((g.def.lat0 - lat) / g.def.res)
  const c = Math.floor((lon - g.def.lon0) / g.def.res)
  return r >= 0 && c >= 0 && r < g.def.nrow && c < g.def.ncol ? r * g.def.ncol + c : -1
}

/** Finest grid first (EAC 0.05°), then Africa 0.25°. Returns null where there is no soil data (desert, sea, dense forest). */
export function sampleLand(model: LandModel, grids: LandGrid[], lat: number, lon: number): LandSample | null {
  for (const g of grids) {
    const i = cellIndex(g, lat, lon)
    if (i < 0) continue
    const N = g.def.nrow * g.def.ncol
    const out: Record<string, number> = {}
    let ok = true
    for (const l of model.layers) {
      const q = g.data[g.layerIndex[l.key] * N + i]
      if (q === 255) { ok = false; break }
      const v = q * l.scale + l.offset
      out[l.key] = l.log ? Math.expm1(v) : v
    }
    if (ok) return { ...(out as unknown as Soil), grid: g.name }
  }
  return null
}

/* ---------------- suitability (identical maths to the notebook) ---------------- */
const clip = (x: number, a = 0, b = 1) => Math.min(b, Math.max(a, x))

export function trap(x: number, q: number[]): number {
  const [a, b, c, d] = q
  const half = (c - b) / 2 + 1e-9
  const mid = (b + c) / 2
  if (x >= b && x <= c) return clip(0.85 + 0.15 * (1 - Math.abs(x - mid) / half))
  if (x < b) return clip((0.85 * (x - a)) / (b - a))
  return clip((0.85 * (d - x)) / (d - c))
}

function textureFactor(tex: Crop['tex'], clay: number, sand: number): number {
  if (tex === 'light') return clay > 45 ? 0.7 : clay > 35 ? 0.9 : 1
  if (tex === 'heavy') return sand > 70 ? 0.7 : sand > 60 ? 0.9 : 1
  return clay > 60 || sand > 80 ? 0.75 : 1
}

const fertilityFactor = (oc: number, n: number, cec: number) =>
  0.8 + 0.2 * ((clip(oc / 20) + clip(n / 2) + clip(cec / 20)) / 3)

export function suitability(c: Crop, s: Soil): number {
  const mT = trap(s.tmean, c.T), mR = trap(s.rain, c.R), mP = trap(s.ph, c.pH)
  const mF = clip((s.tmin - (c.kill - 3)) / 3)
  const season = c.cycle > 2 ? clip((s.wet + (c.perennial ? 3 : 0.5)) / c.cycle) : 1
  return Math.cbrt(clip(mT * mR * mP * mF * season)) * textureFactor(c.tex, s.clay, s.sand) * fertilityFactor(s.oc, s.n, s.cec) * c.w
}

/** Rotation: what was grown last season changes what is wise to plant now. */
export type RotationReason = 'same_crop' | 'same_family' | 'legume_after' | 'cereal_after_legume' | 'root_after_legume' | null
export function rotationMultiplier(prev: Crop | null, c: Crop): { m: number; why: RotationReason } {
  if (!prev || prev.perennial || c.perennial) return { m: 1, why: null }
  if (prev.id === c.id) return { m: 0.45, why: 'same_crop' }
  if (prev.fam === c.fam) {
    if (c.fam === 'solanaceae' || c.fam === 'brassica') return { m: 0.4, why: 'same_family' }
    if (c.fam === 'legume') return { m: 0.65, why: 'same_family' }
    if (c.fam === 'cereal') return { m: 0.8, why: 'same_family' }
    return { m: 0.55, why: 'same_family' }
  }
  if (c.fam === 'legume' && ['cereal', 'root', 'solanaceae', 'brassica', 'alliaceae', 'asteraceae'].includes(prev.fam)) return { m: 1.25, why: 'legume_after' }
  if (c.fam === 'cereal' && prev.fam === 'legume') return { m: 1.2, why: 'cereal_after_legume' }
  if (c.fam === 'root' && prev.fam === 'legume') return { m: 1.1, why: 'root_after_legume' }
  return { m: 1, why: null }
}

export interface CropShare { crop: Crop; score: number; pct: number; why: RotationReason }

/** Scores → percentages over the viable crops (high power sharpens the ranking, top-N only). */
export function cropShares(model: LandModel, s: Soil, prev: Crop | null): CropShare[] {
  const rows = model.crops.map((crop) => {
    const rot = rotationMultiplier(prev, crop)
    return { crop, score: suitability(crop, s) * rot.m, why: rot.why }
  })
  const pw = rows.map((r) => (r.score >= model.share_floor ? Math.pow(r.score, model.share_power) : 0))
  const order = [...pw.keys()].sort((a, b) => pw[b] - pw[a])
  order.slice(model.share_top).forEach((i) => { pw[i] = 0 })
  const tot = pw.reduce((a, b) => a + b, 0)
  return rows.map((r, i) => ({ ...r, pct: tot ? (100 * pw[i]) / tot : 0 })).sort((a, b) => b.pct - a.pct)
}

/* ---------------- nutrient classes & fertiliser plan ---------------- */
export type Level = 'low' | 'medium' | 'high'
export const nutrientLevel = (model: LandModel, key: 'k' | 'p' | 'n' | 'oc' | 'cec', v: number): Level => {
  const [lo, hi] = model.nutrient_classes[key]
  return v < lo ? 'low' : v <= hi ? 'medium' : 'high'
}
export type PhClass = 'acid' | 'ok' | 'alkaline'
export const phClass = (model: LandModel, ph: number): PhClass => (ph < model.ph_acid ? 'acid' : ph > model.ph_alkaline ? 'alkaline' : 'ok')

export interface FertItem { nutrient: 'n' | 'p' | 'k' | 'ph' | 'oc'; product: string; rate: [number, number]; note: string }
/** What to buy for the chosen crop: only nutrients that are LOW in the soil AND that the crop needs. */
export function fertilizerPlan(model: LandModel, s: Soil, crop: Crop): FertItem[] {
  const out: FertItem[] = []
  const need = (ch: string) => crop.dem.includes(ch)
  const add = (nutrient: FertItem['nutrient'], rule: FertRule) => out.push({ nutrient, product: rule.product, rate: rule.rate_low, note: rule.note })
  if (need('N') && !crop.legume && nutrientLevel(model, 'n', s.n) === 'low') add('n', model.fert.n)
  if (need('P') && nutrientLevel(model, 'p', s.p) === 'low') add('p', model.fert.p)
  if (need('K') && nutrientLevel(model, 'k', s.k) === 'low') add('k', model.fert.k)
  if (phClass(model, s.ph) === 'acid' && crop.pH[1] >= 5.2) add('ph', model.fert.ph_low)
  if (nutrientLevel(model, 'oc', s.oc) === 'low') add('oc', model.fert.oc)
  return out
}
