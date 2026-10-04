import { useCallback, useEffect, useState } from 'react'

/**
 * Where is the app running and how can it be installed *there*?
 * Install flows differ a lot: Chrome/Edge on Android expose a real install prompt; iOS has no prompt at all
 * (Safari: Share → Add to Home Screen; Chrome/Firefox/Edge on iOS have their own share button); Samsung Internet and Firefox use menus.
 */
export type Platform =
  | 'ios-safari' | 'ios-chrome' | 'ios-other'
  | 'android-chrome' | 'android-samsung' | 'android-firefox' | 'android-other'
  | 'desktop-chromium' | 'desktop-safari' | 'desktop-firefox' | 'other'

export function detectPlatform(ua = navigator.userAgent, maxTouch = navigator.maxTouchPoints): Platform {
  const iOS = /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && maxTouch > 1) // iPadOS reports as Mac
  if (iOS) {
    if (/CriOS/.test(ua)) return 'ios-chrome'
    if (/FxiOS|EdgiOS|OPiOS|DuckDuckGo|GSA\//.test(ua)) return 'ios-other'
    return 'ios-safari'
  }
  if (/Android/.test(ua)) {
    if (/SamsungBrowser/.test(ua)) return 'android-samsung'
    if (/Firefox|Fennec/.test(ua)) return 'android-firefox'
    if (/Chrome|EdgA|OPR/.test(ua)) return 'android-chrome'
    return 'android-other'
  }
  if (/Firefox/.test(ua)) return 'desktop-firefox'
  if (/Chrome|Edg\//.test(ua)) return 'desktop-chromium'
  if (/Safari/.test(ua)) return 'desktop-safari'
  return 'other'
}

const FLAG = 'agriai.installed'
const flagged = () => { try { return localStorage.getItem(FLAG) === '1' } catch { return false } }
const setFlag = () => { try { localStorage.setItem(FLAG, '1') } catch { /* ignore */ } }
const standalone = () => window.matchMedia?.('(display-mode: standalone)').matches || (navigator as unknown as { standalone?: boolean }).standalone === true
/** Installed = running as an installed app, or we saw it get installed (the button must never reappear in the browser tab afterwards). */
export const isStandalone = () => { if (standalone()) { setFlag(); return true } return flagged() }

interface BIPEvent extends Event { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> }
let deferred: BIPEvent | null = null
const listeners = new Set<() => void>()
if (typeof window !== 'undefined') {
  window.addEventListener('beforeinstallprompt', (e) => { e.preventDefault(); deferred = e as BIPEvent; listeners.forEach((l) => l()) })
  window.addEventListener('appinstalled', () => { deferred = null; setFlag(); listeners.forEach((l) => l()) })
  // Chrome on Android can tell us whether this web app is already installed (matches manifest.related_applications)
  ;(navigator as unknown as { getInstalledRelatedApps?: () => Promise<unknown[]> }).getInstalledRelatedApps?.()
    .then((apps) => { if (apps.length) { setFlag(); listeners.forEach((l) => l()) } }).catch(() => {})
}

export function useInstall() {
  const [, force] = useState(0)
  useEffect(() => {
    const l = () => force((n) => n + 1)
    listeners.add(l)
    return () => { listeners.delete(l) }
  }, [])
  const platform = detectPlatform()
  const installed = isStandalone()
  const promptInstall = useCallback(async () => {
    if (!deferred) return false
    await deferred.prompt()
    const { outcome } = await deferred.userChoice
    deferred = null
    force((n) => n + 1)
    return outcome === 'accepted'
  }, [])
  return { platform, installed, canPrompt: !!deferred, promptInstall }
}
