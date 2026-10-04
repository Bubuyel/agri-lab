import { useState } from 'react'
import type { Lang } from '../core/types'
import { LANGUAGES, ONBOARDING_LANGS, langInfo } from '../i18n/languages'
import { Flag } from './Flag'
import { LanguageSheet } from './LanguageSheet'
import { useI18n } from '../i18n'
import { useInstall } from '../install'
import { Icon } from './Icon'
import { LogoMark, Wordmark } from './Logo'

/* Small animated illustrations: pure SVG + CSS keyframes (no libraries, no images → works offline, tiny). */
function ArtScan() {
  return (
    <svg className="art-svg" viewBox="0 0 240 240" width="100%" role="img" aria-hidden="true">
      <rect className="card-f" x="30" y="30" width="180" height="180" rx="38" />
      <path className="acc-s" d="M52 78V62a14 14 0 0 1 14-14h16M158 48h16a14 14 0 0 1 14 14v16M188 162v16a14 14 0 0 1-14 14h-16M82 192H66a14 14 0 0 1-14-14v-16" />
      <g className="float">
        <path className="acc" d="M120 74c-30 2-48 20-50 52 0 6 1 10 2 14 8-26 24-40 44-48-14 12-24 26-30 44 8 8 16 10 26 10 30 0 44-26 44-60 0-6-10-12-36-12Z" opacity=".95" />
        <path className="stroke" d="M74 164c10-26 28-50 52-66" />
      </g>
      <g className="scanline"><rect x="56" y="62" width="128" height="3.5" rx="2" className="acc" /></g>
      <path className="acc" d="M180 54l3.2 7.8 7.8 3.2-7.8 3.2L180 76l-3.2-7.8-7.8-3.2 7.8-3.2Z" />
    </svg>
  )
}
function ArtPricesRain() {
  return (
    <svg className="art-svg" viewBox="0 0 240 240" width="100%" role="img" aria-hidden="true">
      <rect className="card-f" x="26" y="52" width="188" height="150" rx="34" />
      <path className="gray" d="M54 190V150h18v40zM84 190v-58h18v58zM114 190v-76h18v76zM144 190v-48h18v48z" opacity=".9" />
      <path className="stroke draw-line" d="M52 146 86 118l30 12 34-44 36 18" />
      <circle className="acc" cx="186" cy="104" r="6" />
      <g transform="translate(150 20)">
        <path className="stroke" d="M26 40a16 16 0 0 1 2-31 20 20 0 0 1 38 6 13 13 0 0 1-2 25z" transform="translate(-8 4)" />
        <path className="acc drop" d="M18 50c3 4 5 7 5 10a5 5 0 0 1-10 0c0-3 2-6 5-10Z" />
        <path className="acc drop d2" d="M36 52c3 4 5 7 5 10a5 5 0 0 1-10 0c0-3 2-6 5-10Z" />
        <path className="acc drop d3" d="M54 50c3 4 5 7 5 10a5 5 0 0 1-10 0c0-3 2-6 5-10Z" />
      </g>
    </svg>
  )
}
function ArtLand() {
  return (
    <svg className="art-svg" viewBox="0 0 240 240" width="100%" role="img" aria-hidden="true">
      <rect className="gray layer" x="40" y="178" width="160" height="34" rx="12" />
      <rect className="layer y2" x="40" y="146" width="160" height="30" rx="12" fill="color-mix(in srgb, var(--accent) 45%, var(--surface-3))" />
      <rect className="acc layer y3" x="40" y="116" width="160" height="28" rx="12" />
      <g className="sprout">
        <path className="stroke" d="M120 116V70" />
        <path className="acc" d="M120 82c0-22-14-34-38-34 0 24 14 34 38 34Z" />
        <path className="acc" d="M120 92c0-18 12-30 38-30 0 22-14 30-38 30Z" opacity=".8" />
      </g>
      <circle className="stroke" cx="70" cy="196" r="3" /><circle className="stroke" cx="130" cy="160" r="3" /><circle className="stroke" cx="172" cy="196" r="3" />
    </svg>
  )
}
function ArtOffline() {
  return (
    <svg className="art-svg" viewBox="0 0 240 240" width="100%" role="img" aria-hidden="true">
      <circle className="acc pulse" cx="120" cy="120" r="64" opacity=".25" />
      <circle className="acc pulse p2" cx="120" cy="120" r="64" opacity=".25" />
      <rect className="card-f" x="76" y="38" width="88" height="164" rx="22" />
      <rect className="gray" x="108" y="46" width="24" height="5" rx="3" />
      <g transform="translate(94 92)" fill="none" stroke="var(--text)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 14a34 34 0 0 1 44 0M10 24a22 22 0 0 1 28 0" /><circle cx="24" cy="34" r="1.5" fill="var(--text)" /><path d="M4 2l40 44" stroke="var(--accent)" strokeWidth="4" />
      </g>
      <circle className="acc" cx="164" cy="168" r="20" />
      <path d="m155 168 6 6 11-12" fill="none" stroke="#052e16" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const PAGES = [
  { art: <ArtScan />, t: 'ob.1.t', d: 'ob.1.d' },
  { art: <ArtPricesRain />, t: 'ob.2.t', d: 'ob.2.d' },
  { art: <ArtLand />, t: 'ob.3.t', d: 'ob.3.d' },
  { art: <ArtOffline />, t: 'ob.4.t', d: 'ob.4.d' },
]

/** First-run walkthrough: welcome + language, then four short animated slides. */
export function Onboarding({ lang, onLang, onDone, onInstall }: { lang: Lang; onLang: (l: Lang) => void; onDone: () => void; onInstall: () => void }) {
  const { t } = useI18n()
  const { installed } = useInstall()
  const [i, setI] = useState(0)
  const [more, setMore] = useState(false)
  const last = PAGES.length
  const next = () => (i === last ? onDone() : setI(i + 1))
  return (
    <div className="ob" role="dialog" aria-label="Agri Lab">
      <div className="ob-top">{i > 0 && i < last && <button className="ob-skip" onClick={onDone}>{t('ob.skip')}</button>}</div>
      <div className="ob-track" style={{ transform: `translateX(-${i * 100}%)` }}>
        <section className="ob-page">
          <LogoMark size={132} animate />
          <div><Wordmark size={40} /><p>{t('ob.pickLang')}</p></div>
          <div className="lang-pills">
            {ONBOARDING_LANGS.map((c) => { const l = langInfo(c); return (
              <button key={c} className={c === lang ? 'on' : ''} onClick={() => onLang(c)}><Flag code={l.flag} size={22} />{l.native}</button>
            ) })}
            {!ONBOARDING_LANGS.includes(lang) && <button className="on" onClick={() => setMore(true)}><Flag code={langInfo(lang).flag} size={22} />{langInfo(lang).native}</button>}
            <button className="more" onClick={() => setMore(true)}><Icon name="globe" size={18} />{t('lang.more', { n: LANGUAGES.length })}</button>
          </div>
        </section>
        {PAGES.map((p, k) => (
          <section className="ob-page" key={k} aria-hidden={i !== k + 1}>
            <div className="ob-art">{i === k + 1 && p.art}</div>
            <div><h2>{t(p.t)}</h2><p>{t(p.d)}</p></div>
          </section>
        ))}
      </div>
      {more && <LanguageSheet current={lang} onPick={(c) => { onLang(c); setMore(false) }} onClose={() => setMore(false)} />}
      <div className="ob-bottom">
        <div className="dots">{Array.from({ length: last + 1 }, (_, k) => <i key={k} className={k === i ? 'on' : ''} />)}</div>
        <button className="btn" onClick={next}>{i === last ? t('ob.start') : t('ob.next')}{i < last && <Icon name="chevron" size={20} />}</button>
        {i === last && !installed && <button className="btn secondary" onClick={onInstall}><Icon name="install" size={20} />{t('in.title')}</button>}
      </div>
    </div>
  )
}
