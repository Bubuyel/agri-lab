import { useEffect, useMemo, useRef, useState } from 'react'
import { bestMonth, forecastSeries, trendOf } from '../core/price/forecast'
import { convert, formatMoney, nearbyMarkets } from '../core/price/markets'
import type { FaoFile, FxFile, MarketsFile, Place, PriceModel, PriceSeries } from '../core/types'
import { loadCountries, loadFao, loadFx, loadMarkets, loadPriceModel, loadPriceSeries } from '../data/loaders'
import { setSubBackHandler } from '../router'
import { useI18n } from '../i18n'
import { commodityName } from '../i18n/strings'
import { PriceChart } from './Chart'
import { LargeTitle, Note, PushPage, Spinner, stagger, useMonthLabel } from './common'
import { Icon } from './Icon'
import { nearestMarket } from './PlaceScreen'

interface Data { model: PriceModel; series: PriceSeries[]; markets: MarketsFile; fx: FxFile; fao: FaoFile | null; countries: Record<string, string> }

interface Props {
  place: Place | null
  currency: string | null
  onCurrency: (c: string | null) => void
  onNeedPlace: () => void
}

export function PricesScreen({ place, currency, onCurrency, onNeedPlace }: Props) {
  const { t, lang } = useI18n()
  const [data, setData] = useState<Data | null>(null)
  const [err, setErr] = useState(false)
  const [sel, setSel] = useState<PriceSeries | null>(null)
  const [q, setQ] = useState('')
  const [out, setOut] = useState(false)
  const selRef = useRef<PriceSeries | null>(null)
  selRef.current = sel

  // device back button closes the crop detail first (we push one history entry when a crop is opened)
  useEffect(() => {
    setSubBackHandler(() => { if (selRef.current) { setOut(true); setTimeout(() => { setSel(null); setOut(false) }, 0); return true } return false })
    return () => setSubBackHandler(null)
  }, [])
  const openCrop = (s: PriceSeries) => { history.pushState({ r: 'sub' }, ''); setSel(s) }

  useEffect(() => {
    Promise.all([loadPriceModel(), loadPriceSeries(), loadMarkets(), loadFx(), loadFao().catch(() => null), loadCountries().catch(() => ({}))])
      .then(([model, series, markets, fx, fao, countries]) => setData({ model, series, markets, fx, fao, countries }))
      .catch(() => setErr(true))
  }, [])

  const country = useMemo(() => {
    if (!place || !data) return null
    return place.country ?? nearestMarket(data.markets.markets, place.lat, place.lon)?.c ?? null
  }, [place, data])

  const list = useMemo(() => {
    if (!data || !country) return []
    const ql = q.trim().toLowerCase()
    return data.series
      .filter((s) => s.c === country)
      .filter((s) => !ql || `${s.com} ${commodityName(s.com, lang)}`.toLowerCase().includes(ql))
      .sort((a, b) => commodityName(a.com, lang).localeCompare(commodityName(b.com, lang)))
  }, [data, country, q, lang])

  return (
    <>
      <div className="view">
        <LargeTitle title={t('price.title')} sub={t('home.pricesSub')} />
        <div className="stack">
          {err && <Note tone="bad" icon="alert">{t('error')}</Note>}
          {!data && !err && <Spinner label={t('loading')} />}
          {data && !place && (
            <>
              <Note icon="pin">{t('price.setPlace')}</Note>
              <button className="btn" onClick={onNeedPlace}><Icon name="pin" size={22} />{t('place.title')}</button>
            </>
          )}
          {data && place && (
            <>
              <button className="chip enter" style={{ alignSelf: 'flex-start' }} onClick={onNeedPlace}><Icon name="pin" size={16} />{place.label} · {data.countries[country ?? ''] ?? country}</button>
              <input className="search enter" style={stagger(1)} type="search" placeholder={t('price.search')} value={q} onChange={(e) => setQ(e.target.value)} />
              {list.length === 0 && <Note tone="warn" icon="alert">{t('price.noData')}</Note>}
              <div className="group enter" style={stagger(2)}>
                {list.map((s) => {
                  const tr = trendOf(s, forecastSeries(s, data.model))
                  return (
                    <button key={`${s.com}|${s.u}`} className="row" onClick={() => openCrop(s)}>
                      <span className="grow"><b>{commodityName(s.com, lang)}</b></span>
                      <span className="value">{formatMoney(s.p)} {s.cur}</span>
                      <span className={`trend ${tr.trend}`}><Icon name={tr.trend === 'up' ? 'up' : tr.trend === 'down' ? 'down' : 'chevron'} size={15} strokeWidth={2.4} /></span>
                    </button>
                  )
                })}
              </div>
            </>
          )}
        </div>
      </div>
      {sel && data && place && <Detail s={sel} data={data} place={place} currency={currency} onCurrency={onCurrency} onBack={() => history.back()} out={out} />}
    </>
  )
}

function Detail({ s, data, place, currency, onCurrency, onBack, out }: { s: PriceSeries; data: Data; place: Place; currency: string | null; onCurrency: (c: string | null) => void; onBack: () => void; out?: boolean }) {
  const { t, lang } = useI18n()
  const ml = useMonthLabel()
  const f = useMemo(() => forecastSeries(s, data.model), [s, data.model])
  const tr = trendOf(s, f)
  const best = bestMonth(f)
  const cur = currency ?? s.cur
  const conv = (v: number, from = s.cur) => (cur === from ? v : convert(v, from, cur, data.fx) ?? v)
  const unit = s.u === 'kg' ? t('price.perKg') : t('price.perL')
  const near = useMemo(() => nearbyMarkets(data.markets, s, place.lat, place.lon), [data.markets, s, place])
  const bestPriceUsd = Math.max(0, ...near.map((n) => n.priceUsd))
  const fao = data.fao
  const item = fao?.item_map && Object.entries(fao.item_map).find(([k]) => s.com.startsWith(k))?.[1]
  const dest = item ? fao?.export_destinations[s.c]?.[item] : undefined
  const prod = item ? fao?.production[s.c]?.[item] : undefined
  const currencies = useMemo(() => Object.entries(data.fx.rates).sort((a, b) => a[0].localeCompare(b[0])), [data.fx])

  return (
    <PushPage title={commodityName(s.com, lang)} onBack={onBack} out={out}>
      <div className="card price-hero enter">
        <div className="muted small">{t('price.now')} · {unit}</div>
        <div className="big-num">{formatMoney(conv(s.p))}<small>{cur}</small></div>
        <div className={`trend-pill ${tr.trend}`}><Icon name={tr.trend === 'up' ? 'up' : tr.trend === 'down' ? 'down' : 'chevron'} size={16} strokeWidth={2.4} />{t(`price.${tr.trend}`)} · {tr.pct > 0 ? '+' : ''}{tr.pct.toFixed(0)} % {t('price.in3m')}</div>
        <div className="faint small" style={{ marginTop: 10 }}>{t('price.updated')} {ml(s.last)}</div>
      </div>

      <section className="card enter" style={stagger(1)}>
        <h3>{t('price.next')}</h3>
        <PriceChart history={s.h} historyStart={s.h0} forecast={f.map((p) => ({ ...p, mid: conv(p.mid), lo: conv(p.lo), hi: conv(p.hi) }))} unit={cur} />
        <table className="tbl">
          <thead><tr><th /><th>{t('price.expected')}</th><th>{t('price.range')}</th></tr></thead>
          <tbody>
            {f.map((p) => (
              <tr key={p.h} className={p.h === best.h ? 'best' : ''}>
                <td>{ml(p.ym)}</td>
                <td><b>{formatMoney(conv(p.mid))}</b></td>
                <td className="muted">{formatMoney(conv(p.lo))} – {formatMoney(conv(p.hi))}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}><Icon name="star" size={18} className="faint" />{t('price.best')}: <b>{ml(best.ym)}</b></p>
        {s.mape != null && <p className="faint small">{t('price.err')} {(s.mape * 100).toFixed(0)} %</p>}
      </section>

      <label className="field enter" style={stagger(2)}>
        <span>{t('price.currency')}</span>
        <select value={cur} onChange={(e) => onCurrency(e.target.value === s.cur ? null : e.target.value)}>
          {currencies.map(([code, r]) => <option key={code} value={code}>{code} · {r.name}</option>)}
        </select>
      </label>

      {near.length > 0 && (
        <section className="enter" style={stagger(3)}>
          <h3 style={{ margin: '4px 4px 10px', display: 'flex', gap: 8, alignItems: 'center' }}><Icon name="pin" size={18} />{t('price.where')}</h3>
          <div className="group">
            {near.map((n) => {
              const isBest = n.priceUsd === bestPriceUsd
              return (
                <div key={n.market.id} className="row">
                  <span className="grow"><b>{n.market.n}</b><span className="muted small">{Math.round(n.km)} {t('price.km')} · {ml(n.ym)}</span></span>
                  <span className="value"><b style={{ color: 'var(--text)' }}>{formatMoney(conv(n.priceLocal, n.market.cur))}</b> <small>{cur}</small></span>
                  {isBest && <span className="badge" style={{ width: 28, height: 28, borderRadius: 10 }}><Icon name="star" size={15} /></span>}
                </div>
              )
            })}
          </div>
        </section>
      )}

      {(dest || prod) && (
        <section className="card enter" style={stagger(4)}>
          {dest && (<><h3>{t('price.buyers')}</h3><div className="chips">{dest.map(([c, pct]) => <span key={c} className="chip sm">{c} · {pct.toFixed(0)} %</span>)}</div></>)}
          {prod && <p className="faint small" style={{ marginTop: 10 }}>{t('price.prod')}: {prod.growth5y_pct != null ? `${prod.growth5y_pct > 0 ? '+' : ''}${prod.growth5y_pct.toFixed(0)} %` : '–'} · FAOSTAT {fao?.as_of_year}</p>}
        </section>
      )}
      <Note icon="info">{t('price.disclaimer')}</Note>
    </PushPage>
  )
}
