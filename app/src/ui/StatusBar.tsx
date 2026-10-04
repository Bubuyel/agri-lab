import { useEffect, useState } from 'react'

/** Decorative phone status bar + notch, shown only inside the desktop phone frame (hidden on real phones via CSS). */
export function StatusBar() {
  const [now, setNow] = useState(new Date())
  useEffect(() => { const i = setInterval(() => setNow(new Date()), 15000); return () => clearInterval(i) }, [])
  return (
    <div className="statusbar" aria-hidden="true">
      <span>{now.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit', hour12: false })}</span>
      <i className="island" />
      <span className="sys">
        <svg width="18" height="12" viewBox="0 0 18 12" fill="currentColor"><rect x="0" y="8" width="3" height="4" rx="1" /><rect x="5" y="5" width="3" height="7" rx="1" /><rect x="10" y="2.5" width="3" height="9.5" rx="1" /><rect x="15" y="0" width="3" height="12" rx="1" /></svg>
        <svg width="26" height="12" viewBox="0 0 26 12" fill="none" stroke="currentColor"><rect x="0.5" y="0.5" width="22" height="11" rx="3.5" opacity=".5" /><rect x="2" y="2" width="17" height="8" rx="2" fill="currentColor" stroke="none" /><rect x="24" y="4" width="2" height="4" rx="1" fill="currentColor" stroke="none" opacity=".5" /></svg>
      </span>
    </div>
  )
}
