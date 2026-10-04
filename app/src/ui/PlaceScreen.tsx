import { useEffect, useMemo, useState } from 'react'
import { getPosition, haversine } from '../core/geo'
import type { Market, Place } from '../core/types'
import { loadCountries, loadMarkets } from '../data/loaders'
import { useI18n } from '../i18n'
import { Note, PushPage, Spinner } from './common'
import { Icon } from './Icon'

/** Nearest known market (to infer the country of a GPS fix, because the app ships no offline border map). */
export function nearestMarket(markets: Market[], lat: number, lon: number): Market | null {
  let best: Market | null = null
  let bd = Infinity
  for (const m of markets) {
    const d = haversine(lat, lon, m.la, m.lo)
    if (d < bd) { bd = d; best = m }
  }
  return best && bd < 600 ? best : null
}

export function PlaceScreen({ onPick, onBack, out }: { onPick: (p: Place) => void; onBack: () => void; out?: boolean }) {
  const { t } = useI18n()
  const [markets, setMarkets] = useState<Market[] | null>(null)
  const [names, setNames] = useState<Record<string, string>>({})
  const [country, setCountry] = useState<string>('')
  const [q, setQ] = useState('')
  const [gpsBusy, setGpsBusy] = useState(false)
  const [gpsFail, setGpsFail] = useState(false)

  useEffect(() => {
    loadMarkets().then((f) => setMarkets(f.markets)).catch(() => setMarkets([]))
    loadCountries().then(setNames).catch(() => {})
  }, [])

  const countries = useMemo(() => {
    const set = new Set((markets ?? []).map((m) => m.c))
    return [...set].sort((a, b) => (names[a] ?? a).localeCompare(names[b] ?? b))
  }, [markets, names])

  const towns = useMemo(() => {
    if (!markets || !country) return []
    const seen = new Set<string>()
    return markets
      .filter((m) => m.c === country && (q === '' || `${m.n} ${m.a}`.toLowerCase().includes(q.toLowerCase())))
      .filter((m) => { const k = `${m.n}|${m.a}`; if (seen.has(k)) return false; seen.add(k); return true })
      .sort((a, b) => a.n.localeCompare(b.n))
      .slice(0, 80)
  }, [markets, country, q])

  async function useGps() {
    setGpsBusy(true); setGpsFail(false)
    try {
      const p = await getPosition()
      const m = markets ? nearestMarket(markets, p.lat, p.lon) : null
      onPick({ lat: p.lat, lon: p.lon, label: m ? `≈ ${m.n}` : `${p.lat.toFixed(2)}, ${p.lon.toFixed(2)}`, country: m?.c })
    } catch {
      setGpsFail(true)
    } finally {
      setGpsBusy(false)
    }
  }

  if (!markets) return <PushPage title={t('place.title')} onBack={onBack} out={out}><Spinner /></PushPage>
  return (
    <PushPage title={t('place.title')} onBack={onBack} out={out}>
      <button className="btn" onClick={useGps} disabled={gpsBusy}><Icon name="pin" size={22} />{t('place.gps')}</button>
      {gpsFail && <Note tone="warn" icon="alert">{t('place.gpsFail')}</Note>}
      <label className="field">
        <span>{t('place.country')}</span>
        <select value={country} onChange={(e) => { setCountry(e.target.value); setQ('') }}>
          <option value="">—</option>
          {countries.map((c) => <option key={c} value={c}>{names[c] ?? c}</option>)}
        </select>
      </label>
      {country && (
        <>
          <input className="search" type="search" placeholder={t('place.town')} value={q} onChange={(e) => setQ(e.target.value)} />
          <div className="group">
            {towns.map((m) => (
              <button key={m.id} className="row" onClick={() => onPick({ lat: m.la, lon: m.lo, label: m.n, country: m.c })}>
                <span className="badge gray"><Icon name="pin" size={18} /></span>
                <span className="grow"><b>{m.n}</b>{m.a && <span className="muted small">{m.a}</span>}</span>
                <Icon name="chevron" size={18} className="chev" />
              </button>
            ))}
          </div>
        </>
      )}
    </PushPage>
  )
}
