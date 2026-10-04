import { useMemo, useState } from 'react'
import { useI18n } from '../i18n'
import { LANGUAGES, TOP_LANGS, langInfo, type LangInfo } from '../i18n/languages'
import { Flag } from './Flag'
import { Icon } from './Icon'

const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Searchable bottom sheet with flag + native name for every language, grouped by region. */
export function LanguageSheet({ current, onPick, onClose }: { current: string; onPick: (code: string) => void; onClose: () => void }) {
  const { t } = useI18n()
  const [q, setQ] = useState('')
  const groups = useMemo(() => {
    const f = fold(q.trim())
    const match = (l: LangInfo) => !f || fold(`${l.native} ${l.english} ${l.code}`).includes(f)
    const all = LANGUAGES.filter(match)
    if (f) return [{ id: 'results', items: all }]
    return [
      { id: 'top', items: TOP_LANGS.map(langInfo) },
      { id: 'africa', items: all.filter((l) => l.region === 'africa' && !TOP_LANGS.includes(l.code)).sort((x, y) => Number(y.code === 'rn') - Number(x.code === 'rn')) },
      { id: 'asia', items: all.filter((l) => l.region === 'asia' && !TOP_LANGS.includes(l.code)) },
    ]
  }, [q])

  return (
    <div className="overlay" onClick={onClose}>
      <div className="sheet lang-sheet" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={t('settings.language')}>
        <div className="grabber" />
        <h2 style={{ fontSize: 24, marginBottom: 12 }}>{t('settings.language')}</h2>
        <input className="search" type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('lang.search')} autoComplete="off" />
        {groups.map((g) => g.items.length > 0 && (
          <section key={g.id}>
            {g.id !== 'results' && <div className="lang-h">{t(`lang.group.${g.id}`)}</div>}
            <div className="group">
              {g.items.map((l) => (
                <button key={l.code} className={`row lang-row ${l.code === current ? 'on' : ''}`} onClick={() => onPick(l.code)}>
                  <Flag code={l.flag} size={30} />
                  <span className="grow"><b>{l.native}</b><span className="muted small">{l.english}</span></span>
                  {!l.human && <span className="beta">{t('lang.beta')}</span>}
                  {l.code === current && <Icon name="check" size={20} className="chev" />}
                </button>
              ))}
            </div>
          </section>
        ))}
        {groups.every((g) => g.items.length === 0) && <p className="muted center">—</p>}
        <p className="faint small" style={{ marginTop: 14 }}>{t('lang.betaNote')}</p>
      </div>
    </div>
  )
}
