import { useCallback, useEffect, useState } from 'react'
import { asset } from '../../data/loaders'
import { voiceIndex } from './speech'

/**
 * Voice packs are ~2 MB of MP3 clips per language. They are NOT in the install bundle; they are downloaded once (automatically on Wi-Fi/online when a
 * language is chosen, or with the Download button) and kept by the service worker's `agriai-audio` cache → listen works offline afterwards.
 */
const CACHE = 'agriai-audio'

export type PackState = 'none' | 'ready' | 'loading' | 'unavailable'

async function cachedCount(lang: string): Promise<{ have: number; total: number }> {
  const idx = await voiceIndex(lang)
  if (!idx) return { have: 0, total: 0 }
  const files = [...new Set(Object.values(idx))]
  if (!('caches' in window)) return { have: 0, total: files.length }
  const c = await caches.open(CACHE)
  let have = 0
  for (const f of files) if (await c.match(asset(`data/audio/${lang}/${f}`))) have++
  return { have, total: files.length }
}

export async function downloadVoicePack(lang: string, onProgress?: (done: number, total: number) => void): Promise<boolean> {
  const idx = await voiceIndex(lang)
  if (!idx || !('caches' in window)) return false
  const c = await caches.open(CACHE)
  const files = [...new Set(Object.values(idx))]
  let done = 0
  const queue = [...files]
  const worker = async () => {
    for (let f = queue.shift(); f; f = queue.shift()) {
      const url = asset(`data/audio/${lang}/${f}`)
      if (!(await c.match(url))) { try { const r = await fetch(url); if (r.ok) await c.put(url, r) } catch { /* offline: retry later */ } }
      onProgress?.(++done, files.length)
    }
  }
  await Promise.all([worker(), worker(), worker(), worker()])
  const { have, total } = await cachedCount(lang)
  return have === total
}

export function useVoicePack(lang: string) {
  const [state, setState] = useState<PackState>('none')
  const [progress, setProgress] = useState(0)
  const refresh = useCallback(async () => {
    const idx = await voiceIndex(lang)
    if (!idx) return setState('unavailable')
    const { have, total } = await cachedCount(lang)
    setState(have === total && total > 0 ? 'ready' : 'none')
  }, [lang])
  useEffect(() => { void refresh() }, [refresh])
  const download = useCallback(async () => {
    setState('loading'); setProgress(0)
    await downloadVoicePack(lang, (d, t) => setProgress(d / t))
    await refresh()
  }, [lang, refresh])
  return { state, progress, download }
}

/** Quietly fetch the pack when the user switches to a language and is online (skipped on data-saver). */
export function autoDownloadVoicePack(lang: string) {
  const conn = (navigator as unknown as { connection?: { saveData?: boolean } }).connection
  if (!navigator.onLine || conn?.saveData) return
  void downloadVoicePack(lang)
}
