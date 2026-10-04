import type { Diagnosis, VisionMeta } from '../types'

export function softmax(x: ArrayLike<number>, T = 1): number[] {
  let m = -Infinity
  for (let i = 0; i < x.length; i++) m = Math.max(m, x[i] / T)
  const e = Array.from({ length: x.length }, (_, i) => Math.exp(x[i] / T - m))
  const s = e.reduce((a, b) => a + b, 0)
  return e.map((v) => v / s)
}

/**
 * Turn the two network heads into a user-facing decision. Mirrors the evaluation logic of notebook 01:
 *  1. temperature-scaled crop probabilities
 *  2. "not a plant" if P(not_plant) is high
 *  3. "unsure / retake" if the best crop probability is below the calibrated gate
 *  4. otherwise pick the disease **only among classes of the predicted crop**
 */
export function diagnose(cropLogits: ArrayLike<number>, labLogits: ArrayLike<number>, M: VisionMeta): Diagnosis {
  const pc = softmax(cropLogits, M.temperature)
  const np = M.not_plant_crop_index
  if (pc[np] >= M.thresholds.not_plant_p) return { kind: 'not_plant', p: pc[np] }

  let ci = -1
  pc.forEach((p, i) => { if (i !== np && (ci < 0 || p > pc[ci])) ci = i })
  if (pc[ci] < M.thresholds.min_confidence) return { kind: 'unsure', cropConf: pc[ci] }
  // a plant we recognise but have no disease data for (e.g. banana): say so instead of guessing a disease of another crop
  if (M.unsupported_crops?.includes(M.crops[ci])) return { kind: 'unsupported', crop: M.crops[ci], cropConf: pc[ci] }

  const idx: number[] = []
  M.labels.forEach((_, i) => { if (M.label_to_crop[i] === ci && i !== M.not_plant_label_index) idx.push(i) })
  const pl = softmax(idx.map((i) => labLogits[i]))
  const order = pl.map((p, k) => ({ label: M.labels[idx[k]], p })).sort((a, b) => b.p - a.p)
  return {
    kind: 'ok', crop: M.crops[ci], label: order[0].label, cropConf: pc[ci], condConf: order[0].p,
    alternatives: order.slice(1, 3).filter((a) => a.p >= 0.1),
  }
}

export type Sureness = 'high' | 'mid' | 'low'
export const sureness = (p: number): Sureness => (p >= 0.8 ? 'high' : p >= 0.5 ? 'mid' : 'low')
export const isHealthy = (label: string) => label.endsWith('___healthy')
