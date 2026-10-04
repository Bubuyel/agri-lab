import { useCallback, useEffect, useRef, useState } from 'react'
import type { AdviceBundle, Diagnosis, Lang, VisionMeta } from '../core/types'
import { classify, warmUp } from '../core/vision/classifier'
import { isHealthy, sureness } from '../core/vision/decide'
import { loadAdvice, loadVisionMeta } from '../data/loaders'
import { useI18n } from '../i18n'
import { ErrorBox, LargeTitle, Note, Spinner, stagger } from './common'
import { Icon } from './Icon'
import { Flag } from './Flag'
import { Listen } from './Listen'
import { LiveCamera } from './LiveCamera'
import { langInfo } from '../i18n/languages'

type State =
  | { s: 'idle' }
  | { s: 'busy'; url: string }
  | { s: 'done'; url: string; d: Diagnosis }
  | { s: 'error'; url?: string }

export function ScanScreen() {
  const { t, lang } = useI18n()
  const [meta, setMeta] = useState<VisionMeta | null>(null)
  const [advice, setAdvice] = useState<AdviceBundle | null>(null)
  const [st, setSt] = useState<State>({ s: 'idle' })
  const [missing, setMissing] = useState(false)
  const camRef = useRef<HTMLInputElement>(null)
  const galRef = useRef<HTMLInputElement>(null)
  const urlRef = useRef<string | null>(null)
  const [live, setLive] = useState(false)
  const canLive = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext
  const closeLive = useCallback(() => setLive(false), [])
  const liveFailed = useCallback(() => { setLive(false); camRef.current?.click() }, [])

  useEffect(() => {
    let alive = true
    Promise.all([loadVisionMeta(), loadAdvice()])
      .then(([m, a]) => { if (alive) { setMeta(m); setAdvice(a); warmUp(m) } })
      .catch(() => alive && setMissing(true))
    return () => { alive = false }
  }, [])
  // free the preview image when replaced / on unmount (NOT on every state change: the result view still shows it)
  useEffect(() => () => { if (urlRef.current) URL.revokeObjectURL(urlRef.current) }, [])

  async function onFile(f?: File | null) {
    if (!f || !meta) return
    if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    const url = URL.createObjectURL(f)
    urlRef.current = url
    setSt({ s: 'busy', url })
    try {
      const { diagnosis } = await classify(f, meta)
      setSt({ s: 'done', url, d: diagnosis })
    } catch (e) {
      console.error(e)
      setSt({ s: 'error', url })
    }
  }
  const reset = () => setSt({ s: 'idle' })

  return (
    <div className="view">
      <LargeTitle title={t('scan.title')} />
      <div className="stack">
        {missing && <Note tone="warn" icon="alert">{t('scan.noModel')}</Note>}

        {st.s === 'idle' && live && meta && <LiveCamera meta={meta} onClose={closeLive} onUnavailable={liveFailed} onShot={(b) => { setLive(false); void onFile(b as File) }} />}

        {st.s === 'idle' && !live && (
          <>
            <div className="viewfinder enter" style={stagger(1)}>
              <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
              <Icon name="leaf" size={92} strokeWidth={1.1} className="faint" />
              <div className="hint">{t('scan.tip1')}</div>
            </div>
            <input ref={camRef} type="file" accept="image/*" capture="environment" hidden onChange={(e) => onFile(e.target.files?.[0])} />
            <input ref={galRef} type="file" accept="image/*" hidden onChange={(e) => onFile(e.target.files?.[0])} />
            <button className="btn enter" style={stagger(2)} disabled={!meta} onClick={() => (canLive && meta ? setLive(true) : camRef.current?.click())}><Icon name="camera" size={22} />{t('scan.take')}</button>
            <button className="btn secondary enter" style={stagger(3)} disabled={!meta} onClick={() => galRef.current?.click()}><Icon name="photo" size={22} />{t('scan.gallery')}</button>
            <div className="card tips enter" style={stagger(4)}>
              <div><span className="badge"><Icon name="sun" size={20} /></span>{t('scan.tip2')}</div>
              <div><span className="badge gray"><Icon name="scan" size={20} /></span>{t('scan.tip3')}</div>
            </div>
            {advice && (
              <details className="card enter" style={stagger(5)}>
                <summary>{t('scan.which')}<Icon name="down" size={18} className="faint" /></summary>
                <p className="muted" style={{ marginTop: 8 }}>{Object.values((advice.advice[lang] ?? advice.advice.en)._crop).join(' · ')}</p>
              </details>
            )}
          </>
        )}

        {st.s === 'busy' && (
          <>
            <div className="preview-wrap"><img className="preview" src={st.url} alt="" /><div className="sweep" /></div>
            <Spinner label={t('scan.loading')} />
          </>
        )}

        {st.s === 'error' && (
          <>
            {st.url && <img className="preview" src={st.url} alt="" />}
            <ErrorBox />
            <button className="btn" onClick={reset}><Icon name="camera" size={22} />{t('scan.retake')}</button>
          </>
        )}

        {st.s === 'done' && advice && <Result url={st.url} d={st.d} advice={advice} lang={lang} onAgain={reset} />}
      </div>
    </div>
  )
}

function Result({ url, d, advice, lang, onAgain }: { url: string; d: Diagnosis; advice: AdviceBundle; lang: Lang; onAgain: () => void }) {
  const { t } = useI18n()
  const A = advice.advice[lang] ?? advice.advice.en
  const msgLines = (k: string) => A._msg[k] ?? advice.advice.en._msg[k] ?? []
  const msg = (k: string) => msgLines(k).join(' ')

  if (d.kind === 'unsupported') {
    const named = d.crop !== 'other_plant'
    const cropName = A._crop[d.crop] ?? advice.advice.en._crop[d.crop] ?? d.crop
    return (
      <>
        <img className="preview enter" src={url} alt="" />
        <div className="result-hero enter" style={stagger(1)}>
          <span className="badge lg gray"><Icon name="leaf" size={26} /></span>
          <h2>{t('scan.unsupported')}</h2>
          <p className="muted">{named ? t('scan.unsupportedBody', { crop: cropName }) : t('scan.unsupportedOther')}</p>
          <div className="pct-row"><Pct label={named ? cropName : t('scan.plant')} p={d.cropConf} /></div>
        </div>
        <Note icon="sparkles">{t('scan.unsupportedMore')}</Note>
        <button className="btn enter" style={stagger(2)} onClick={onAgain}><Icon name="camera" size={22} />{t('scan.retake')}</button>
      </>
    )
  }

  if (d.kind === 'not_plant' || d.kind === 'unsure') {
    const notPlant = d.kind === 'not_plant'
    return (
      <>
        <img className="preview enter" src={url} alt="" />
        <div className="result-hero enter" style={stagger(1)}>
          <span className="badge lg gray"><Icon name={notPlant ? 'close' : 'help'} size={26} /></span>
          <h2>{notPlant ? t('scan.notPlant') : t('scan.unsure')}</h2>
          <p className="muted">{msg(notPlant ? 'not_plant' : 'unsure')}</p>
          <Listen lang={lang} sentences={msgLines(notPlant ? 'not_plant' : 'unsure')} className="center-btn" />
          <div className="pct-row"><Pct label={notPlant ? t('scan.notPlantPct') : t('scan.bestGuess')} p={notPlant ? d.p : d.cropConf} /></div>
        </div>
        <button className="btn enter" style={stagger(2)} onClick={onAgain}><Icon name="camera" size={22} />{t('scan.retake')}</button>
      </>
    )
  }

  const machine = lang !== 'en' && !advice.reviewed[lang]
  // The answer is always shown (and read aloud) in the chosen language. Machine-translated languages carry a visible
  // warning and keep the reviewed English text one tap away.
  const base = A
  const e = base.labels[d.label]
  const healthy = isHealthy(d.label)
  const cropName = A._crop[d.crop] ?? d.crop
  const sure = sureness(Math.min(d.cropConf, d.condConf))
  return (
    <>
      <img className="preview enter" src={url} alt="" />
      <div className={`result-hero enter ${sure !== 'low' && healthy ? 'good' : ''}`} style={stagger(1)}>
        <span className={`badge lg ${sure === 'low' || !healthy ? 'gray' : ''}`}><Icon name={sure === 'low' ? 'help' : healthy ? 'check' : 'alert'} size={26} /></span>
        <div className="kv">{t('scan.crop')}<b>{cropName}</b></div>
        <h2>{e?.name ?? d.label}</h2>
        <p className="muted">{healthy ? t('scan.healthy') : t('scan.sick')} · {t(`scan.sure.${sure}`)}</p>
        <div className="pct-row"><Pct label={cropName} p={d.cropConf} /><Pct label={e?.name ?? d.label} p={d.condConf} /></div>
        {e && <Listen lang={lang} sentences={[e.name, ...e.what, ...e.treat, ...e.prevent]} className="center-btn" />}
      </div>

      {/* the "take the photo again" hint appears ONLY when the model is genuinely unsure */}
      {sure === 'low' && <Note tone="warn" icon="help">{msg('unsure')}</Note>}
      {sure === 'low' && d.alternatives.length > 0 && (
        <Note icon="sparkles">{t('scan.maybe')}: {d.alternatives.map((a) => base.labels[a.label]?.name ?? a.label).join(', ')}</Note>
      )}

      {e && (
        <>
          <Section i={2} icon="info" title={t('scan.what')} lines={e.what} />
          <Section i={3} icon="bolt" title={t('scan.treat')} lines={e.treat} numbered />
          {e.prevent.length > 0 && <Section i={4} icon="leaf" title={t('scan.prevent')} lines={e.prevent} numbered />}
        </>
      )}
      {machine && <Note tone="warn" icon="alert">{t('scan.machine')}</Note>}
      <AlsoRead label={d.label} advice={advice} current={lang} />
      <Note icon="info">{msg('see_expert')} {msg('disclaimer')}</Note>
      <button className="btn" onClick={onAgain}><Icon name="camera" size={22} />{t('scan.retake')}</button>
    </>
  )
}

/** Model probability as a labelled percentage bar. */
function Pct({ label, p }: { label: string; p: number }) {
  const v = Math.round(p * 100)
  return (
    <div className="pct">
      <div className="pct-top"><span>{label}</span><b>{v}%</b></div>
      <div className="pct-bar"><i style={{ width: `${v}%` }} /></div>
    </div>
  )
}

function Section({ title, lines, numbered, icon, i, flat }: { title: string; lines: string[]; numbered?: boolean; icon: 'info' | 'bolt' | 'leaf'; i?: number; flat?: boolean }) {
  const body = (
    <>
      <h3 style={{ display: 'flex', alignItems: 'center', gap: 10 }}><span className="badge" style={{ width: 32, height: 32, borderRadius: 11 }}><Icon name={icon} size={17} /></span>{title}</h3>
      {numbered ? <ol>{lines.map((l, k) => <li key={k}>{l}</li>)}</ol> : <p>{lines.join(' ')}</p>}
    </>
  )
  return flat ? <div>{body}</div> : <section className="card enter" style={i ? stagger(i) : undefined}>{body}</section>
}

/** "Also read in": the three international languages (English, French, Spanish) as tappable pills; shows the reviewed text of the same diagnosis. */
const INTL = ['en', 'fr', 'es']
function AlsoRead({ label, advice, current }: { label: string; advice: AdviceBundle; current: string }) {
  const { t } = useI18n()
  const [open, setOpen] = useState<string | null>(null)
  const options = INTL.filter((c) => c !== current && advice.advice[c]?.labels[label])
  if (options.length === 0) return null
  const e = open ? advice.advice[open].labels[label] : null
  return (
    <section className="card also-read enter">
      <div className="also-h"><Icon name="globe" size={18} />{t('scan.alsoRead')}</div>
      <div className="also-pills" role="tablist">
        {options.map((c) => (
          <button key={c} role="tab" aria-selected={open === c} className={`pill ${open === c ? 'on' : ''}`} onClick={() => setOpen(open === c ? null : c)}>
            <Flag code={langInfo(c).flag} size={20} />{langInfo(c).native}
          </button>
        ))}
      </div>
      {open && e && (
        <div className="stack also-body">
          <h3>{e.name}</h3>
          <p>{e.what.join(' ')}</p>
          <h4 className="also-sub">{t('scan.treat')}</h4>
          <ol>{e.treat.map((l, k) => <li key={k}>{l}</li>)}</ol>
          {e.prevent.length > 0 && <><h4 className="also-sub">{t('scan.prevent')}</h4><ol>{e.prevent.map((l, k) => <li key={k}>{l}</li>)}</ol></>}
          <Listen lang={open} sentences={[e.name, ...e.what, ...e.treat, ...e.prevent]} className="center-btn" />
        </div>
      )}
    </section>
  )
}
