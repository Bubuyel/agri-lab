import type { CSSProperties, ReactNode } from 'react'
import { useI18n } from '../i18n'
import { Icon, type IconName } from './Icon'

/** Sticky translucent navigation bar for pushed screens. */
export function NavBar({ title, onBack }: { title: string; onBack: () => void }) {
  const { t } = useI18n()
  return (
    <header className="navbar">
      <button className="round-btn" onClick={onBack} aria-label={t('back')}><Icon name="back" size={24} /></button>
      <h1>{title}</h1>
    </header>
  )
}

export function LargeTitle({ title, sub, right }: { title: string; sub?: string; right?: ReactNode }) {
  return (
    <div className="largetitle enter">
      <div><h1>{title}</h1>{sub && <div className="sub">{sub}</div>}</div>
      {right}
    </div>
  )
}

/** Pushed full-screen page (slides in over the tabs). */
export function PushPage({ title, onBack, children, out }: { title: string; onBack: () => void; children: ReactNode; out?: boolean }) {
  return (
    <div className={`push ${out ? 'out' : ''}`}>
      <div className="view no-tab">
        <NavBar title={title} onBack={onBack} />
        <div className="stack">{children}</div>
      </div>
    </div>
  )
}

export const stagger = (i: number): CSSProperties => ({ ['--i' as string]: i })

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="center" role="status">
      <div className="spinner" />
      {label && <p className="muted">{label}</p>}
    </div>
  )
}

export function Note({ children, tone = 'info', icon = 'info' }: { children: ReactNode; tone?: 'info' | 'warn' | 'bad'; icon?: IconName }) {
  return <div className={`note ${tone}`}><Icon name={icon} size={18} /><div>{children}</div></div>
}

export function ErrorBox({ message }: { message?: string }) {
  const { t } = useI18n()
  return <Note tone="bad" icon="alert">{message || t('error')}</Note>
}

/** `YYYY-MM` → "Aug 2026" in the user's language. */
export function useMonthLabel() {
  const { month } = useI18n()
  return (ym: string, withYear = true) => {
    const [y, m] = ym.split('-').map(Number)
    return `${month(m)}${withYear ? ' ' + y : ''}`
  }
}
