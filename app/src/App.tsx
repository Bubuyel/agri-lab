import { useCallback, useEffect, useRef, useState } from 'react'
import { StatusBar } from './ui/StatusBar'
import type { Lang, Place } from './core/types'
import { I18nProvider, useI18n } from './i18n'
import { runSubBack } from './router'
import { useSettings } from './store'
import { useTheme } from './theme'
import { HomeScreen, type Tab } from './ui/HomeScreen'
import { Icon, type IconName } from './ui/Icon'
import { InstallSheet } from './ui/InstallSheet'
import { LandScreen } from './ui/LandScreen'
import { autoDownloadVoicePack } from './core/audio/pack'
import { Onboarding } from './ui/Onboarding'
import { PlaceScreen } from './ui/PlaceScreen'
import { PricesScreen } from './ui/PricesScreen'
import { RainScreen } from './ui/RainScreen'
import { ScanScreen } from './ui/ScanScreen'
import { SettingsScreen } from './ui/SettingsScreen'

type Overlay = 'place' | 'settings'

export default function App() {
  const [settings, update] = useSettings()
  useTheme(settings.theme)
  useFitDevice()
  useEffect(() => { if (settings.lang) autoDownloadVoicePack(settings.lang) }, [settings.lang])
  const lang: Lang = settings.lang ?? 'en'
  return (
    <I18nProvider lang={lang}>
      <div className="device"><div className="app"><Shell settings={settings} update={update} lang={lang} /></div><StatusBar /></div>
    </I18nProvider>
  )
}

/** Desktop only: scale the 390×844 phone down so it always fits the window (CSS reads --s). */
function useFitDevice() {
  useEffect(() => {
    const fit = () => document.documentElement.style.setProperty('--s', String(Math.min(1, (window.innerHeight - 44) / 844, (window.innerWidth - 44) / 390)))
    fit()
    window.addEventListener('resize', fit)
    return () => window.removeEventListener('resize', fit)
  }, [])
}

const TABS: { id: Tab; icon: IconName; label: string }[] = [
  { id: 'home', icon: 'home', label: 'tab.home' }, { id: 'scan', icon: 'scan', label: 'tab.scan' }, { id: 'prices', icon: 'chart', label: 'tab.prices' },
  { id: 'land', icon: 'layers', label: 'tab.land' }, { id: 'rain', icon: 'rain', label: 'tab.rain' },
]

/**
 * Navigation: five tabs + pushed overlays (place picker, settings, install sheet).
 * Every overlay pushes one browser-history entry, so the Android/iOS back gesture closes it instead of leaving the app.
 */
function Shell({ settings, update, lang }: { settings: ReturnType<typeof useSettings>[0]; update: ReturnType<typeof useSettings>[1]; lang: Lang }) {
  const { t } = useI18n()
  const [tab, setTab] = useState<Tab>('home')
  const [overlays, setOverlays] = useState<Overlay[]>([])
  const [sheet, setSheet] = useState(false)
  const [replay, setReplay] = useState(false)
  const [closing, setClosing] = useState(false) // plays the exit animation of the top overlay before it unmounts
  const [dir, setDir] = useState<'r' | 'l'>('r')
  const tabRef = useRef<Tab>('home')
  tabRef.current = tab

  useEffect(() => {
    const onPop = () => {
      if (runSubBack()) return
      const exit = (fn: () => void) => { setClosing(true); setTimeout(() => { fn(); setClosing(false) }, 0) }
      if (sheet) return exit(() => setSheet(false))
      if (overlays.length) return exit(() => setOverlays((o) => o.slice(0, -1)))
      if (tab !== 'home') { setDir('l'); return setTab('home') }
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [sheet, overlays, tab])

  const openOverlay = useCallback((o: Overlay) => { history.pushState({ r: o }, ''); setOverlays((s) => [...s, o]) }, [])
  const closeTop = useCallback(() => history.back(), [])
  const openSheet = useCallback(() => { history.pushState({ r: 'sheet' }, ''); setSheet(true) }, [])
  const goTab = useCallback((id: Tab) => {
    setTab((cur) => {
      if (cur === 'home' && id !== 'home') history.pushState({ r: 'tab' }, '')
      setDir(TABS.findIndex((x) => x.id === id) >= TABS.findIndex((x) => x.id === cur) ? 'r' : 'l')
      return id
    })
  }, [])
  const pickPlace = (p: Place) => { update({ place: p }); history.back() }
  const needPlace = () => openOverlay('place')

  const showOnboarding = !settings.onboarded || replay
  return (
    <>
      <div className={`page dir-${dir} ${overlays.length || sheet ? 'under' : ''}`} key={tab}>
        {tab === 'home' && <HomeScreen key="home" place={settings.place} go={goTab} onSettings={() => openOverlay('settings')} onPlace={needPlace} onInstall={openSheet} />}
        {tab === 'scan' && <ScanScreen key="scan" />}
        {tab === 'prices' && <PricesScreen key="prices" place={settings.place} currency={settings.currency} onCurrency={(c) => update({ currency: c })} onNeedPlace={needPlace} />}
        {tab === 'land' && <LandScreen key="land" place={settings.place} lastCrop={settings.lastCrop} onLastCrop={(id) => update({ lastCrop: id })} onNeedPlace={needPlace} />}
        {tab === 'rain' && <RainScreen key="rain" place={settings.place} answer={settings.rain} onAnswer={(a) => update({ rain: a })} onNeedPlace={needPlace} />}
      </div>

      <nav className="tabbar glass" aria-label="Main" style={{ ['--i' as string]: TABS.findIndex((x) => x.id === tab), ['--n' as string]: TABS.length }}>
        <i className="lens" key={`lens-${tab}`} />
        {TABS.map((x) => (
          <button key={x.id} className={`tab ${tab === x.id ? 'on' : ''}`} onClick={() => goTab(x.id)} aria-current={tab === x.id ? 'page' : undefined}>
            <Icon name={x.icon} size={23} />{t(x.label)}
          </button>
        ))}
      </nav>

      {overlays.map((o, i) =>
        o === 'place' ? (
          <PlaceScreen key={`${o}${i}`} onPick={pickPlace} onBack={closeTop} out={closing && i === overlays.length - 1} />
        ) : (
          <SettingsScreen key={`${o}${i}`} lang={lang} onLang={(l) => update({ lang: l })} theme={settings.theme} onTheme={(th) => update({ theme: th })}
            placeLabel={settings.place?.label} onPlace={() => openOverlay('place')} onInstall={openSheet} onReplay={() => { setReplay(true); closeTop() }} onBack={closeTop} out={closing && i === overlays.length - 1} />
        ),
      )}
      {sheet && <InstallSheet onClose={closeTop} out={closing && !overlays.length} />}
      {showOnboarding && <Onboarding lang={lang} onLang={(l) => update({ lang: l })} onInstall={openSheet} onDone={() => { update({ onboarded: true }); setReplay(false) }} />}
    </>
  )
}
