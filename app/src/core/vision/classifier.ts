import * as ort from 'onnxruntime-web/wasm'
import type { Diagnosis, VisionMeta } from '../types'
import { asset } from '../../data/loaders'
import { diagnose, softmax } from './decide'

/** Draw the centre square of `src` into an `n`×`n` canvas, halving step-wise (better anti-aliasing than one big resize). */
export function squareCanvas(src: CanvasImageSource & { width?: number; height?: number }, n: number): HTMLCanvasElement {
  const v = src as HTMLVideoElement
  const w = v.videoWidth || (src as HTMLImageElement).naturalWidth || (src as ImageBitmap).width || 0
  const h = v.videoHeight || (src as HTMLImageElement).naturalHeight || (src as ImageBitmap).height || 0
  const s = Math.min(w, h)
  let cur = document.createElement('canvas')
  const first = Math.min(s, n * 4)
  cur.width = cur.height = first
  const g0 = cur.getContext('2d')!
  g0.imageSmoothingQuality = 'high'
  g0.drawImage(src, (w - s) / 2, (h - s) / 2, s, s, 0, 0, first, first)
  while (cur.width > n) {
    const next = document.createElement('canvas')
    next.width = next.height = Math.max(n, Math.floor(cur.width / 2))
    const g = next.getContext('2d')!
    g.imageSmoothingQuality = 'high'
    g.drawImage(cur, 0, 0, next.width, next.height)
    cur = next
  }
  return cur
}

/** RGBA canvas → NCHW float32 normalised exactly like training (ImageNet mean/std). */
export function canvasToTensor(c: HTMLCanvasElement, mean: number[], std: number[]): Float32Array {
  const n = c.width
  const { data } = c.getContext('2d')!.getImageData(0, 0, n, n)
  const out = new Float32Array(3 * n * n)
  for (let i = 0; i < n * n; i++) {
    for (let k = 0; k < 3; k++) out[k * n * n + i] = (data[i * 4 + k] / 255 - mean[k]) / std[k]
  }
  return out
}

let sessionP: Promise<ort.InferenceSession> | null = null

function loadSession(meta: VisionMeta) {
  if (!sessionP) {
    ort.env.wasm.wasmPaths = new URL('ort/', document.baseURI).href
    ort.env.wasm.numThreads = 1 // multi-thread needs cross-origin isolation, which static hosts rarely give
    ort.env.wasm.proxy = false
    sessionP = ort.InferenceSession.create(asset(`models/${meta.model_file}`), { executionProviders: ['wasm'], graphOptimizationLevel: 'all' })
    sessionP.catch(() => { sessionP = null })
  }
  return sessionP
}

/** Start loading the model early (e.g. when the scan screen opens) so the first photo is not slow. */
export const warmUp = (meta: VisionMeta) => { loadSession(meta).catch(() => {}) }

export async function classify(file: Blob, meta: VisionMeta): Promise<{ diagnosis: Diagnosis; ms: number }> {
  const bmp = await createImageBitmap(file, { imageOrientation: 'from-image' } as ImageBitmapOptions)
  const sq = squareCanvas(bmp, meta.input_size)
  bmp.close?.()
  const sess = await loadSession(meta)
  const t0 = performance.now()
  const x = new ort.Tensor('float32', canvasToTensor(sq, meta.mean, meta.std), [1, 3, meta.input_size, meta.input_size])
  const out = await sess.run({ image: x })
  const ms = performance.now() - t0
  return { diagnosis: diagnose(out.crop_logits.data as Float32Array, out.lab_logits.data as Float32Array, meta), ms }
}

export interface Glance { plant: boolean; pPlant: number; brightness: number; sharpness: number }

/** Cheap live check of one camera frame (tens of ms, fully on the phone): is there a plant, is it bright and sharp enough? */
export async function glance(frame: CanvasImageSource, meta: VisionMeta): Promise<Glance> {
  const n = meta.input_size
  const sq = squareCanvas(frame as CanvasImageSource & { width?: number; height?: number }, n)
  const { data } = sq.getContext('2d')!.getImageData(0, 0, n, n)
  const g = new Float32Array(n * n)
  let sum = 0
  for (let i = 0; i < n * n; i++) { g[i] = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2]; sum += g[i] }
  // sharpness = variance of the Laplacian (low = blurry)
  let m = 0, m2 = 0, c = 0
  for (let y = 1; y < n - 1; y++) for (let x = 1; x < n - 1; x++) {
    const i = y * n + x
    const l = 4 * g[i] - g[i - 1] - g[i + 1] - g[i - n] - g[i + n]
    m += l; m2 += l * l; c++
  }
  const sharpness = m2 / c - (m / c) ** 2
  const sess = await loadSession(meta)
  const x = new ort.Tensor('float32', canvasToTensor(sq, meta.mean, meta.std), [1, 3, n, n])
  const out = await sess.run({ image: x })
  const pc = softmax(out.crop_logits.data as Float32Array, meta.temperature)
  const pNot = pc[meta.not_plant_crop_index]
  return { plant: pNot < meta.thresholds.not_plant_p, pPlant: 1 - pNot, brightness: sum / (n * n), sharpness }
}
