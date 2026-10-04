import { useEffect, useMemo, useState } from 'react'
import { cropShares, fertilizerPlan, nutrientLevel, parseLand, phClass, sampleLand, type Crop, type LandGrid, type LandModel, type Level, type Soil } from '../core/land/land'
import type { Place } from '../core/types'
import { loadLandBin, loadLandModel } from '../data/loaders'
import { useI18n } from '../i18n'
import { LargeTitle, Note, Spinner, stagger } from './common'
import { Icon, type IconName } from './Icon'

interface Props { place: Place | null; lastCrop: string | null; onLastCrop: (id: string | null) => void; onNeedPlace: () => void }

const NUTRIENTS: { key: 'k' | 'p' | 'n' | 'oc'; icon: IconName; unit: string }[] = [
  { key: 'k', icon: 'bolt', unit: 'mg/kg' }, { key: 'p', icon: 'flask', unit: 'mg/kg' },
  { key: 'n', icon: 'leaf', unit: 'g/kg' }, { key: 'oc', icon: 'layers', unit: 'g/kg' },
]

/** Position of a value on a Low | Fair | Rich gauge (piecewise so the three zones are equal width). */
function gaugePos(model: LandModel, key: string, v: number): number {
  const [lo, hi] = model.nutrient_classes[key]
  if (v < lo) return (v / lo) * 0.333
  if (v <= hi) return 0.333 + ((v - lo) / (hi - lo)) * 0.333
  return 0.667 + Math.min(1, (v - hi) / hi) * 0.333
}
const fmt = (v: number) => (v >= 100 ? v.toFixed(0) : v >= 10 ? v.toFixed(1) : v.toFixed(2))

export function LandScreen({ place, lastCrop, onLastCrop, onNeedPlace }: Props) {
  const { t, lang } = useI18n()
  const [model, setModel] = useState<LandModel | null>(null)
  const [grids, setGrids] = useState<LandGrid[] | null>(null)
  const [err, setErr] = useState(false)
  const [picked, setPicked] = useState<string | null>(null)

  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const m = await loadLandModel()
        const names = ['eac', 'africa']
        const bins = await Promise.all(names.map((n) => loadLandBin(n)))
        if (alive) { setModel(m); setGrids(names.map((n, i) => parseLand(bins[i], m, n))) }
      } catch (e) { console.error(e); if (alive) setErr(true) }
    })()
    return () => { alive = false }
  }, [])

  const soil = useMemo(() => (model && grids && place ? sampleLand(model, grids, place.lat, place.lon) : null), [model, grids, place])
  const crop = (id: string | null) => model?.crops.find((c) => c.id === id) ?? null
  const cname = (c: Crop) => c.names[lang] ?? c.names.en ?? c.id
  const prev = crop(lastCrop)
  const shares = useMemo(() => (model && soil ? cropShares(model, soil, prev) : []), [model, soil, prev])
  const base = useMemo(() => (model && soil && prev ? cropShares(model, soil, null) : []), [model, soil, prev])
  const top = shares.filter((s) => s.pct > 0).slice(0, 6)
  const sel = top.find((s) => s.crop.id === picked) ?? top[0]
  const plan = model && soil && sel ? fertilizerPlan(model, soil, sel.crop) : []
  const reason = top.find((s) => s.why)?.why ?? null

  return (
    <div className="view">
      <LargeTitle title={t('land.title')} sub={t('land.sub')} />
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
            {!soil && <Note tone="warn" icon="alert">{t('land.noData')}</Note>}
            {soil && <Body model={model} soil={soil} lang={lang} t={t} cname={cname} prev={prev} lastCrop={lastCrop} onLastCrop={onLastCrop}
              top={top} base={base} sel={sel?.crop.id ?? null} onPick={setPicked} plan={plan} reason={reason} />}
          </>
        )}
      </div>
    </div>
  )
}

type T = (k: string, v?: Record<string, string | number>) => string
function Body({ model, soil, t, cname, prev, lastCrop, onLastCrop, top, base, sel, onPick, plan, reason }: {
  model: LandModel; soil: Soil & { grid: string }; lang: string; t: T; cname: (c: Crop) => string; prev: Crop | null; lastCrop: string | null
  onLastCrop: (id: string | null) => void; top: ReturnType<typeof cropShares>; base: ReturnType<typeof cropShares>; sel: string | null
  onPick: (id: string) => void; plan: ReturnType<typeof fertilizerPlan>; reason: ReturnType<typeof cropShares>[number]['why']
}) {
  const levels = NUTRIENTS.map((n) => ({ ...n, v: soil[n.key], lvl: nutrientLevel(model, n.key, soil[n.key]) as Level }))
  const rich = levels.filter((l) => l.lvl === 'high')
  const low = levels.filter((l) => l.lvl === 'low')
  const ph = phClass(model, soil.ph)
  const texture = soil.sand >= 60 ? 'sandy' : soil.clay >= 40 ? 'clayey' : 'loam'
  const selCrop = model.crops.find((c) => c.id === sel)

  return (
    <>
      <div className="kpis enter" style={stagger(1)}>
        <div className="kpi"><small>{t('land.temp')}</small><b>{soil.tmean.toFixed(0)}°C</b></div>
        <div className="kpi"><small>{t('land.rain')}</small><b>{Math.round(soil.rain)} mm</b></div>
        <div className="kpi"><small>{t('land.texture')}</small><b>{t(`land.tex.${texture}`)}</b></div>
      </div>

      <section className="card enter" style={stagger(2)}>
        <h3>{t('land.soil')}</h3>
        <div className="stack" style={{ gap: 10, marginBottom: 16 }}>
          <div className="chips"><span className="faint small" style={{ alignSelf: 'center', minWidth: 74 }}>{t('land.rich')}</span>
            {rich.length ? rich.map((l) => <span key={l.key} className="chip sm accent">{t(`land.${l.key}`)}</span>) : <span className="chip sm">—</span>}</div>
          <div className="chips"><span className="faint small" style={{ alignSelf: 'center', minWidth: 74 }}>{t('land.low')}</span>
            {low.length ? low.map((l) => <span key={l.key} className="chip sm">{t(`land.${l.key}`)}</span>) : <span className="chip sm accent">{t('land.balanced')}</span>}</div>
        </div>
        <div className="nutri">
          {levels.map((l) => (
            <div className="nutri-row" key={l.key}>
              <div className="top"><b>{t(`land.${l.key}`)}</b><span>{fmt(l.v)} {l.unit} · {t(`land.lvl.${l.lvl}`)}</span></div>
              <div className="gauge"><i style={{ left: `${gaugePos(model, l.key, l.v) * 100}%` }} /></div>
            </div>
          ))}
          <div className="nutri-row">
            <div className="top"><b>{t('land.ph')}</b><span>{soil.ph.toFixed(1)} · {t(`land.ph.${ph}`)}</span></div>
            <div className="gauge"><i style={{ left: `${Math.min(1, Math.max(0, (soil.ph - 4) / 4)) * 100}%` }} /></div>
          </div>
        </div>
      </section>

      <section className="enter" style={stagger(3)}>
        <h3 style={{ margin: '4px 4px 10px' }}>{t('land.last')}</h3>
        <div className="scroll-x">
          <button className={`chip ${!lastCrop ? 'on' : ''}`} onClick={() => onLastCrop(null)}>{t('land.lastNone')}</button>
          {model.crops.map((c) => <button key={c.id} className={`chip ${lastCrop === c.id ? 'on' : ''}`} onClick={() => onLastCrop(c.id)}>{cname(c)}</button>)}
        </div>
      </section>

      <section className="card enter" style={stagger(4)}>
        <h3>{t('land.best')}</h3>
        {top.map((s) => {
          const b = base.find((x) => x.crop.id === s.crop.id)?.pct ?? s.pct
          const d = Math.round(s.pct - b)
          return (
            <button key={s.crop.id} className={`share ${sel === s.crop.id ? 'sel' : ''} ${s === top[0] ? 'top' : ''}`} onClick={() => onPick(s.crop.id)}>
              <span className="name">{cname(s.crop)}{prev && Math.abs(d) >= 3 && <span className={`delta ${d > 0 ? 'up' : 'down'}`}>{d > 0 ? '+' : ''}{d}</span>}</span>
              <span className="pct">{s.pct.toFixed(0)}%</span>
              <span className="bar"><i style={{ width: `${s.pct}%` }} /></span>
            </button>
          )
        })}
        {prev && reason && <Note icon="sparkles">{t(`land.why.${reason}`)}</Note>}
        <p className="faint small" style={{ marginTop: 10 }}>{t('land.pickCrop')}</p>
      </section>

      {selCrop && (
        <section className="card enter" style={stagger(5)}>
          <h3>{t('land.fert')} · {cname(selCrop)}</h3>
          {plan.length === 0 && <p className="muted">{t('land.fertNone')}</p>}
          {plan.map((f) => (
            <div className="fert" key={f.nutrient}>
              <span className="badge"><Icon name={f.nutrient === 'ph' ? 'drop' : f.nutrient === 'oc' ? 'layers' : 'flask'} size={20} /></span>
              <div><b>{t(`land.prod.${f.product}`)}</b><small>{t('land.rate', { a: f.rate[0], b: f.rate[1] })}</small></div>
            </div>
          ))}
          <p className="faint small" style={{ marginTop: 10 }}>{t('land.fertNote')}</p>
        </section>
      )}

      <Note icon="info">{t('land.approx')} {t('land.source')}</Note>
    </>
  )
}
