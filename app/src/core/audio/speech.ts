/**
 * Read text aloud for people who cannot read. Order of preference:
 *  1. a pre-generated voice clip shipped in the language's voice pack (works offline on every phone, notebook 09),
 *  2. the phone's own speech engine (offline on most Android phones for major languages),
 *  3. nothing (the button is hidden / disabled).
 */
import { asset } from '../../data/loaders'
import { langInfo } from '../../i18n/languages'

let current: HTMLAudioElement | null = null
let listeners = new Set<() => void>()
const notify = () => listeners.forEach((l) => l())
export const onSpeechChange = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn) } }

/** { sentence → file } index of a language's voice pack, if the app ships one. */
const indexCache = new Map<string, Promise<Record<string, string> | null>>()
export function voiceIndex(lang: string): Promise<Record<string, string> | null> {
  if (!indexCache.has(lang)) {
    indexCache.set(lang, fetch(asset(`data/audio/${lang}/index.json`)).then((r) => (r.ok ? r.json() : null)).catch(() => null))
  }
  return indexCache.get(lang)!
}

export function hasDeviceVoice(lang: string): boolean {
  if (typeof speechSynthesis === 'undefined') return false
  const tag = langInfo(lang).bcp.toLowerCase()
  const base = tag.split('-')[0]
  return speechSynthesis.getVoices().some((v) => { const l = v.lang.toLowerCase(); return l === tag || l.startsWith(base + '-') || l === base })
}

export function stopSpeaking() {
  if (current) { current.pause(); current = null }
  if (typeof speechSynthesis !== 'undefined') speechSynthesis.cancel()
  notify()
}
export const isSpeaking = () => !!current || (typeof speechSynthesis !== 'undefined' && speechSynthesis.speaking)

/** Speak a list of sentences in order. Returns false when no voice is available. */
export async function speak(sentences: string[], lang: string): Promise<boolean> {
  stopSpeaking()
  const idx = await voiceIndex(lang)
  const clips = idx ? sentences.map((s) => idx[s]).filter(Boolean) : []
  if (idx && clips.length === sentences.length && clips.length > 0) {
    let i = 0
    const next = () => {
      if (i >= clips.length) { current = null; notify(); return }
      const a = new Audio(asset(`data/audio/${lang}/${clips[i++]}`))
      current = a
      a.onended = next
      a.onerror = () => { current = null; notify() }
      a.play().catch(() => { current = null; notify() })
      notify()
    }
    next()
    return true
  }
  if (typeof speechSynthesis !== 'undefined' && hasDeviceVoice(lang)) {
    const tag = langInfo(lang).bcp
    const u = new SpeechSynthesisUtterance(sentences.join(' '))
    u.lang = tag
    u.rate = 0.92
    u.onend = notify; u.onerror = notify
    speechSynthesis.speak(u)
    notify()
    return true
  }
  return false
}

/** Can we speak this language at all (pack or device voice)? Used to show/hide listen buttons. */
export async function canSpeak(lang: string, sentences?: string[]): Promise<boolean> {
  const idx = await voiceIndex(lang)
  if (idx && (!sentences || sentences.every((x) => idx[x]))) return true
  return hasDeviceVoice(lang)
}
