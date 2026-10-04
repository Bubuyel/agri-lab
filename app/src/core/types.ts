/** Shared data contracts. These mirror the JSON/binary artifacts exported by the training notebooks. */

export type Lang = string

/* ---------- 01 · vision ---------- */
export interface VisionMeta {
  input_size: number
  mean: number[]
  std: number[]
  model_file: string
  crops: string[]
  labels: string[]
  label_to_crop: number[]
  not_plant_crop_index: number
  not_plant_label_index: number
  /** crops the model recognises but has no disease data for (banana, cassava, bean, other_plant) */
  unsupported_crops?: string[]
  temperature: number
  thresholds: { not_plant_p: number; min_confidence: number }
  metrics?: Record<string, unknown>
}

export type Diagnosis =
  | { kind: 'not_plant'; p: number }
  | { kind: 'unsure'; cropConf: number }
  | { kind: 'unsupported'; crop: string; cropConf: number }
  | {
      kind: 'ok'
      crop: string
      label: string
      cropConf: number
      condConf: number
      /** other plausible conditions for the same crop, most likely first */
      alternatives: { label: string; p: number }[]
    }

/* ---------- 04 · advice ---------- */
export interface AdviceEntry { name: string; what: string[]; treat: string[]; prevent: string[] }
export interface AdviceBundle {
  languages: Record<Lang, string>
  reviewed: Record<string, boolean>
  advice: Record<Lang, { _msg: Record<string, string[]>; _crop: Record<string, string>; labels: Record<string, AdviceEntry> }>
}

/* ---------- 02 · prices ---------- */
export interface PriceModel {
  horizons: number
  type: 'gbdt' | 'ridge'
  /** gbdt: per horizon a list of trees; node = [feature, threshold, left, right], leaf = [-1, value, 0, 0] */
  trees?: Record<string, number[][][]>
  ridge?: Record<string, { b: number; w: number[] }>
  interval_q: Record<string, number[]>
  data_end: string
}
export interface PriceSeries {
  c: string; com: string; u: 'kg' | 'l'; cur: string; last: string
  p: number; pu: number
  /** model features at the latest origin: [m1, m3, m6, m12, dev12, vol12] */
  f: number[]
  sd: number[]
  s: number[]
  h: number[]; h0: string
  mape: number | null
}
export interface ForecastPoint { h: number; ym: string; mid: number; lo: number; hi: number }

export interface MarketPrice extends Array<unknown> { 0: number; 1: string; 2: number; 3: number; 4: string }
export interface Market { id: number; n: string; c: string; a: string; la: number; lo: number; cur: string; p: MarketPrice[] }
export interface MarketsFile { commodities: string[]; markets: Market[] }
export interface FxFile { as_of: string; rates: Record<string, { usd_per: number; per_usd: number; name: string }> }
export interface FaoFile {
  as_of_year: number
  production: Record<string, Record<string, { prod_kusd: number; growth5y_pct: number | null }>>
  export_destinations: Record<string, Record<string, [string, number][]>>
  item_map: Record<string, string>
}

/* ---------- 03 · rain ---------- */
export interface GridMeta {
  name: string; nrow: number; ncol: number; res: number; lon0: number; lat0: number
  last_month: [number, number]; state_scale: number
  layout: [string, 'u16' | 'i8' | 'u8', number[]][]
  nodata_u16: number; nodata_i8: number; dry_p67_mm: number
}
export interface RainModel {
  leads: number
  classes: string[]
  logit: Record<string, { b: number[]; w: number[][] }>
  grids: Record<string, GridMeta>
  eval: { rpss_by_lead: Record<string, number>; reliability_gap_h1: number }
}
export interface Place { lat: number; lon: number; label: string; country?: string }
