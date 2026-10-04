import { useEffect, useMemo, useState } from 'react'
import { dailyForecast, parseDaily, type DailyGrid } from '../core/rain/daily'
import { parseGrid, rainOutlook, type Grid, type RainResult } from '../core/rain/outlook'
import type { Place, RainModel } from '../core/types'
import { loadDailyBin, loadDailyMeta, loadRainBin, loadRainModel } from '../data/loaders'
import { useI18n } from '../i18n'
import { todayKey, type RainAnswer } from '../store'
import { RainBars } from './Chart'
import { LargeTitle, Note, Spinner, stagger } from './common'
import { Icon } from './Icon'

interface Props { place: Place | null; answer: RainAnswer | null; onAnswer: (a: RainAnswer) => void; onNeedPlace: () => void }

/** Today's yes/no answers, carrying "today" over as "yesterday" on the next day. */
export function currentAnswer(a: RainAnswer | null): RainAnswer {
  const today = todayKey()
  if (a?.d === today) return a
  const y = todayKey(new Date(Date.now() - 864e5))
  return { d: today, y: a?.d === y ? a.t : false, t: false }
}

export function RainScreen({ place, answer, onAnswer, onNeedPlace }: Props) {
  const { t, month, lang } = useI18n()
  const [tab, setTab] = useState<'days' | 'months'>('days')
  const [model, setModel] = useState<RainModel | null>(null)
  const [grids, setGrids] = useState<Grid[] | null>(null)
  const [daily, setDaily] = useState<DailyGrid | null>(null)
  const [err, setErr] = useState(false)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const [m, dm] = await Promise.all([loadRainModel(), loadDailyMeta()])
        const names = ['eac', 'africa'] // finest first
        const [bins, db] = await Promise.all([Promise.all(names.map((n) => loadRainBin(n))), loadDailyBin()])
        if (alive) { setModel(m); setGrids(names.map((n, i) => parseGrid(bins[i], m.grids[n]))); setDaily(parseDaily(db, dm)) }
      } catch (e) { console.error(e); if (alive) setErr(true) }
    })()
    return () => { alive = false }
  }, [])

  const ans = currentAnswer(answer)
  const now = new Date()
  const d = useMemo(() => (daily && place ? dailyForecast(daily, place.lat, place.lon, now.getMonth() + 1, ans.y, ans.t, 7) : null), [daily, place, ans.y, ans.t]) // eslint-disable-line react-hooks/exhaustive-deps
  const outlook: RainResult | null = model && grids && place ? rainOutlook(model, grids, place) : null

  return (
    <div className="view">
      <LargeTitle title={t('rain.title')} sub={t('home.rainSub')} />
      <div className="stack">
        {err && <Note tone="bad" icon="alert">{t('error')}</Note>}
        {!model && !err && <Spinner label={t('loading')} />}
        {model && !place && (
          <>
            <Note icon="pin">{t('price.setPlace')}</Note>
            <button className="btn" onClick={onNeedPlace}><Icon name="pin" size={22} />{t('place.title')}</button>
          </>
        )}
        {model && place && (
          <>
            <button className="chip enter" style={{ alignSelf: 'flex-start' }} onClick={onNeedPlace}><Icon name="pin" size={16} />{place.label}</button>
            <div className="seg enter" style={stagger(1)}>
              <button className={tab === 'days' ? 'on' : ''} onClick={() => setTab('days')}>{t('rain.days')}</button>
              <button className={tab === 'months' ? 'on' : ''} onClick={() => setTab('months')}>{t('rain.months')}</button>
            </div>
            {tab === 'days' && <Days d={d} ans={ans} onAnswer={onAnswer} lang={lang} now={now} />}
            {tab === 'months' && (outlook ? <Months r={outlook} t={t} month={month} /> : <Note tone="warn" icon="alert">{t('rain.noData')}</Note>)}
            <Note icon="info">{tab === 'days' ? t('rain.offlineNote') : t('rain.disclaimer')}</Note>
          </>
        )}
      </div>
    </div>
  )
}

function YesNo({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  const { t } = useI18n()
  return (
    <div style={{ display: 'grid', gap: 8 }}>
      <b style={{ fontSize: '0.95rem' }}>{label}</b>
      <div className="seg">
        <button className={value ? 'on' : ''} onClick={() => onChange(true)}><Icon name="drop" size={14} /> {t('rain.yes')}</button>
        <button className={!value ? 'on' : ''} onClick={() => onChange(false)}><Icon name="sun" size={14} /> {t('rain.no')}</button>
      </div>
    </div>
  )
}

function Days({ d, ans, onAnswer, lang, now }: { d: ReturnType<typeof dailyForecast>; ans: RainAnswer; onAnswer: (a: RainAnswer) => void; lang: string; now: Date }) {
  const { t, month } = useI18n()
  if (!d) return <Note tone="warn" icon="alert">{t('rain.noData')}</Note>
  const wd = (i: number) => {
    const dt = new Date(now.getTime() + i * 864e5)
    try { return new Intl.DateTimeFormat(lang, { weekday: 'short' }).format(dt) } catch { return new Intl.DateTimeFormat('en', { weekday: 'short' }).format(dt) }
  }
  const labels = d.chance.map((_, i) => wd(i + 1))
  const order = d.chance.map((c, i) => ({ c, i })).sort((a, b) => a.c - b.c)
  const dry = order.slice(0, 2).map((x) => labels[x.i]).join(' · ')
  const wet = order.slice(-2).reverse().map((x) => labels[x.i]).join(' · ')
  return (
    <>
      <section className="card stack enter" style={stagger(2)}>
        <YesNo label={t('rain.didRain')} value={ans.t} onChange={(v) => onAnswer({ ...ans, t: v })} />
        <YesNo label={t('rain.yesterday')} value={ans.y} onChange={(v) => onAnswer({ ...ans, y: v })} />
      </section>
      <section className="card enter" style={stagger(3)}>
        <h3>{t('rain.next7')}</h3>
        <div className="daybars">
          {d.chance.map((c, i) => (
            <div className="daybar" key={i}>
              <b>{Math.round(c * 100)}%</b>
              <div className={`col ${c < 0.3 ? 'dry' : ''}`} style={{ height: `${Math.max(6, c * 100)}%` }} />
              <span>{labels[i]}</span>
            </div>
          ))}
        </div>
      </section>
      <section className="card enter" style={stagger(4)}>
        <div className="row" style={{ padding: '4px 0', minHeight: 0 }}><span className="badge gray"><Icon name="sun" size={18} /></span><span className="grow"><b>{t('rain.tipDry')}</b><span className="muted small">{dry}</span></span></div>
        <div className="row" style={{ padding: '10px 0 4px', minHeight: 0 }}><span className="badge"><Icon name="drop" size={18} /></span><span className="grow"><b>{t('rain.tipWet')}</b><span className="muted small">{wet}</span></span></div>
        <p className="faint small" style={{ marginTop: 10 }}>{month(now.getMonth() + 1, 'long')} · {t('rain.typical', { n: d.wetDays.toFixed(0) })} · {t('rain.heavy', { mm: d.wetMm.toFixed(0) })}</p>
      </section>
    </>
  )
}

function Months({ r, t, month }: { r: RainResult; t: (k: string, v?: Record<string, string | number>) => string; month: (m: number, s?: 'short' | 'long') => string }) {
  const upcoming = r.months.map((m) => m.month - 1)
  const usualForLast = r.last12Months.map((m) => r.calendar[m - 1])
  const totalObs = r.last12.reduce((a, b) => a + b, 0)
  const totalUsual = usualForLast.reduce((a, b) => a + b, 0)
  const pct = totalUsual > 0 ? Math.round((totalObs / totalUsual - 1) * 100) : 0
  return (
    <>
      {r.months.map((m, k) => (
        <section key={m.lead} className="card month-row enter" style={stagger(2 + k)}>
          <div className="rain-hero">
            <span className="badge lg"><Icon name={m.dry ? 'sun' : m.signal === 'wetter' ? 'rain' : m.signal === 'drier' ? 'sun' : 'drop'} size={26} /></span>
            <div><b className="cap" style={{ fontFamily: 'var(--font-display)', fontSize: '1.15rem' }}>{month(m.month, 'long')}</b><div className="muted">{m.dry ? t('rain.dry') : t(`rain.${m.signal}`)}</div></div>
          </div>
          {!m.dry && m.probs && (
            <>
              <div className="prob" role="img" aria-label="probabilities">
                <span className="a" style={{ width: `${m.probs[0] * 100}%` }}>{Math.round(m.probs[0] * 100)}%</span>
                <span className="b" style={{ width: `${m.probs[1] * 100}%` }}>{Math.round(m.probs[1] * 100)}%</span>
                <span className="c" style={{ width: `${m.probs[2] * 100}%` }}>{Math.round(m.probs[2] * 100)}%</span>
              </div>
              <div className="legend"><span>{t('rain.drier')}</span><span>{t('rain.normal')}</span><span>{t('rain.wetter')}</span></div>
              <p className="faint small">{t('rain.usualRain')}: {m.normalBand[0]}–{m.normalBand[1]} mm · {m.confidence === 'low' ? t('rain.lowConf') : t('rain.someConf')}</p>
            </>
          )}
        </section>
      ))}
      <section className="card enter" style={stagger(5)}>
        <h3>{t('rain.calendar')}</h3>
        <RainBars values={r.calendar} labels={Array.from({ length: 12 }, (_, i) => month(i + 1).slice(0, 1).toUpperCase())} highlight={upcoming} />
      </section>
      <section className="card enter" style={stagger(6)}>
        <h3>{t('rain.last')}</h3>
        <RainBars values={r.last12} usual={usualForLast} labels={r.last12Months.map((m) => month(m).slice(0, 1).toUpperCase())} />
        <p className="faint small">{pct > 0 ? '+' : ''}{pct} % {t('rain.vsUsual')} · {t('rain.dataTo')} {month(r.lastMonth[1])} {r.lastMonth[0]}</p>
      </section>
    </>
  )
}
