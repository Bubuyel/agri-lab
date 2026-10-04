import type { Lang } from '../core/types'
import { useI18n } from '../i18n'
import { langInfo } from '../i18n/languages'
import { useState } from 'react'
import { Flag } from './Flag'
import { LanguageSheet } from './LanguageSheet'
import { useInstall } from '../install'
import { hasDeviceVoice } from '../core/audio/speech'
import { useVoicePack } from '../core/audio/pack'
import type { ThemeChoice } from '../theme'
import { PushPage } from './common'
import { Icon } from './Icon'
import { AppIcon } from './Logo'

interface Props { lang: Lang; onLang: (l: Lang) => void; theme: ThemeChoice; onTheme: (t: ThemeChoice) => void; placeLabel?: string; onPlace: () => void; onInstall: () => void; onReplay: () => void; onBack: () => void; out?: boolean }

export function SettingsScreen({ lang, onLang, theme, onTheme, placeLabel, onPlace, onInstall, onReplay, onBack, out }: Props) {
  const { t } = useI18n()
  const { installed } = useInstall()
  const [pick, setPick] = useState(false)
  const voice = useVoicePack(lang)
  return (
    <PushPage title={t('settings.title')} onBack={onBack} out={out}>
      <div className="center enter" style={{ padding: '6px 0 0' }}>
        <AppIcon size={72} />
        <h2 style={{ fontSize: 24 }}>Agri Lab</h2>
        <p className="muted small">{t('settings.version')} {__APP_VERSION__}</p>
      </div>

      <div className="group enter">
        <button className="row" onClick={() => setPick(true)}>
          <Flag code={langInfo(lang).flag} size={30} />
          <span className="grow"><b>{t('settings.language')}</b></span>
          <span className="value">{langInfo(lang).native}</span><Icon name="chevron" size={18} className="chev" />
        </button>
        {(voice.state !== 'unavailable' || hasDeviceVoice(lang)) && <div className="row">
          <span className="badge gray"><Icon name="sound" size={20} /></span>
          <span className="grow"><b>{t('audio.pack')}</b></span>
          {voice.state === 'ready' && <span className="value">{t('audio.ready')}</span>}
          {voice.state === 'loading' && <span className="value">{t('audio.downloading')} {Math.round(voice.progress * 100)}%</span>}
          {voice.state === 'none' && <button className="chip sm accent" onClick={voice.download}>{t('audio.download')}</button>}
          {voice.state === 'unavailable' && <span className="value">{hasDeviceVoice(lang) ? t('audio.deviceVoice') : t('audio.noneSettings')}</span>}
        </div>}
        <button className="row" onClick={onPlace}>
          <span className="badge gray"><Icon name="pin" size={20} /></span>
          <span className="grow"><b>{t('place.current')}</b></span>
          <span className="value">{placeLabel ?? '—'}</span><Icon name="chevron" size={18} className="chev" />
        </button>
        <button className="row" onClick={onInstall}>
          <span className="badge gray"><Icon name="install" size={20} /></span>
          <span className="grow"><b>{t('settings.install')}</b></span>
          {installed ? <Icon name="check" size={18} className="chev" /> : <Icon name="chevron" size={18} className="chev" />}
        </button>
      </div>

      <section className="card enter">
        <h3 style={{ display: 'flex', gap: 10, alignItems: 'center' }}><Icon name={theme === 'dark' ? 'moon' : 'sun'} size={20} />{t('settings.theme')}</h3>
        <div className="seg">
          {(['auto', 'light', 'dark'] as ThemeChoice[]).map((c) => <button key={c} className={theme === c ? 'on' : ''} onClick={() => onTheme(c)}>{t(`theme.${c}`)}</button>)}
        </div>
      </section>

      <section className="card enter">
        <h3>{t('settings.about')}</h3>
        <p className="muted">{t('settings.aboutText')}</p>
        <button className="btn secondary" style={{ marginTop: 12 }} onClick={onReplay}><Icon name="sparkles" size={20} />{t('ob.welcome')}</button>
      </section>
      {pick && <LanguageSheet current={lang} onPick={(c) => { onLang(c); setPick(false) }} onClose={() => setPick(false)} />}
    </PushPage>
  )
}
