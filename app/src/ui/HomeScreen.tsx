import { useEffect, useState } from 'react'
import { dailyForecast, parseDaily, type DailyGrid } from '../core/rain/daily'
import type { Place } from '../core/types'
import { loadDailyBin, loadDailyMeta } from '../data/loaders'
import { useI18n } from '../i18n'
import { useInstall } from '../install'
import { stagger } from './common'
import { Icon } from './Icon'
import { LogoMark } from './Logo'

export type Tab = 'home' | 'scan' | 'prices' | 'land' | 'rain'

function useOfflineReady() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    if (!('serviceWorker' in navigator)) return
    navigator.serviceWorker.ready.then(() => setReady(true)).catch(() => {})
  }, [])
  return ready
}

export function HomeScreen({ place, go, onSettings, onPlace, onInstall }: { place: Place | null; go: (t: Tab) => void; onSettings: () => void; onPlace: () => void; onInstall: () => void }) {
  const { t, month } = useI18n()
  const { installed } = useInstall()
  const ready = useOfflineReady()
  const [daily, setDaily] = useState<DailyGrid | null>(null)
  useEffect(() => {
    Promise.all([loadDailyMeta(), loadDailyBin()]).then(([m, b]) => setDaily(parseDaily(b, m))).catch(() => {})
  }, [])

  const now = new Date()
  const h = now.getHours()
  const greet = t(h < 12 ? 'greet.morning' : h < 18 ? 'greet.afternoon' : 'greet.evening')
  const chance = daily && place ? dailyForecast(daily, place.lat, place.lon, now.getMonth() + 1, false, false, 1)?.monthChance ?? null : null
  const pct = chance == null ? 0 : Math.round(chance * 100)
  const C = 2 * Math.PI * 44

  return (
    <div className="view">
      <div className="largetitle enter">
        <div>
          <div className="muted">{greet}</div>
          <h1 style={{ display: 'flex', alignItems: 'center', gap: 10 }}><LogoMark size={34} />Agri Lab</h1>
        </div>
        <button className="round-btn filled" onClick={onSettings} aria-label={t('home.settings')}><Icon name="settings" size={22} /></button>
      </div>

      <div className="stack">
        <section className="hero enter" style={stagger(1)}>
          {place ? (
            <>
              <div className="ring" aria-label={`${pct}%`}>
                <svg viewBox="0 0 100 100" width="104" height="104"><circle className="track" cx="50" cy="50" r="44" fill="none" strokeWidth="9" /><circle className="val" cx="50" cy="50" r="44" fill="none" strokeWidth="9" strokeDasharray={C} strokeDashoffset={C * (1 - (chance ?? 0))} /></svg>
                <div className="num">{chance == null ? '–' : pct}<small>{chance == null ? '' : '%'}</small></div>
              </div>
              <div>
                <button className="chip sm" onClick={onPlace}><Icon name="pin" size={14} />{place.label}</button>
                <p style={{ marginTop: 8, fontWeight: 600 }}>{t('home.rainToday', { month: month(now.getMonth() + 1, 'long') })}</p>
                <button className="muted small" style={{ background: 'none', border: 0, padding: 0, textDecoration: 'underline' }} onClick={() => go('rain')}>{t('rain.next7')} →</button>
              </div>
            </>
          ) : (
            <button style={{ all: 'unset', cursor: 'pointer', display: 'flex', gap: 14, alignItems: 'center', width: '100%' }} onClick={onPlace}>
              <span className="badge lg"><Icon name="pin" size={26} /></span>
              <span style={{ flex: 1, fontWeight: 600 }}>{t('home.setPlace')}</span>
              <Icon name="chevron" size={20} className="faint" />
            </button>
          )}
        </section>

        {!installed && (
          <button className="tile wide install-tile enter" style={stagger(2)} onClick={onInstall}>
            <span className="badge lg"><Icon name="install" size={26} /></span>
            <span><b>{t('home.install')}</b><small>{t('home.installSub')}</small></span>
            <Icon name="chevron" size={20} className="faint" />
          </button>
        )}
        <button className="install-banner scan-banner enter" style={stagger(3)} onClick={() => go('scan')}>
          <span className="badge lg"><Icon name="scan" size={26} /></span>
          <span style={{ flex: 1 }}><b>{t('home.scan')}</b><small>{t('home.scanSub')}</small></span>
          <Icon name="chevron" size={18} className="faint" />
        </button>
        <div className="tiles">
          <button className="tile enter" style={stagger(3)} onClick={() => go('land')}>
            <span className="badge lg"><Icon name="layers" size={26} /></span>
            <span><b>{t('home.land')}</b><small>{t('home.landSub')}</small></span>
          </button>
          <button className="tile enter" style={stagger(4)} onClick={() => go('prices')}>
            <span className="badge lg gray"><Icon name="chart" size={26} /></span>
            <span><b>{t('home.prices')}</b><small>{t('home.pricesSub')}</small></span>
          </button>
          <button className="tile wide enter" style={{ ...stagger(5), background: 'var(--surface)', color: 'var(--text)', borderColor: 'var(--line)' }} onClick={() => go('rain')}>
            <span className="badge lg"><Icon name="rain" size={26} /></span>
            <span><b>{t('home.rain')}</b><small style={{ color: 'var(--text-2)' }}>{t('home.rainSub')}</small></span>
            <Icon name="chevron" size={20} className="faint" />
          </button>
        </div>

        <p className="center small" style={{ color: ready ? 'var(--accent-strong)' : 'var(--text-3)', fontWeight: 600 }}>
          <span style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }}><Icon name={ready ? 'check' : 'wifiOff'} size={16} />{ready ? t('home.offlineReady') : t('home.offlinePrep')}</span>
        </p>
      </div>
    </div>
  )
}
