import { useEffect } from 'react'

export type ThemeChoice = 'auto' | 'light' | 'dark'

/** Apply the theme to <html data-theme> and keep the browser/status-bar colour in sync. */
export function useTheme(choice: ThemeChoice) {
  useEffect(() => {
    const root = document.documentElement
    const mq = window.matchMedia('(prefers-color-scheme: dark)')
    const apply = () => {
      const dark = choice === 'dark' || (choice === 'auto' && mq.matches)
      root.dataset.theme = dark ? 'dark' : 'light'
      document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#0a0a0b' : '#f5f5f7')
    }
    apply()
    mq.addEventListener?.('change', apply)
    return () => mq.removeEventListener?.('change', apply)
  }, [choice])
}
