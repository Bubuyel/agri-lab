import { useI18n } from '../i18n'
import { useInstall, type Platform } from '../install'
import { Icon, type IconName } from './Icon'
import { AppIcon } from './Logo'

interface Step { text: string; icon?: IconName }

/** Platform-specific install steps. Chrome/Edge on Android get a real one-tap prompt; iOS has none, so we show the exact taps. */
function stepsFor(p: Platform, t: (k: string) => string): { steps: Step[]; note?: string; label: string } {
  switch (p) {
    case 'ios-safari': return { label: 'iPhone · Safari', steps: [{ text: t('in.ios.safari.1'), icon: 'share' }, { text: t('in.ios.safari.2'), icon: 'addSquare' }, { text: t('in.ios.safari.3') }] }
    case 'ios-chrome': return { label: 'iPhone · Chrome', steps: [{ text: t('in.ios.chrome.1'), icon: 'share' }, { text: t('in.ios.chrome.2'), icon: 'addSquare' }, { text: t('in.ios.chrome.3') }] }
    case 'ios-other': return { label: 'iPhone', steps: [], note: t('in.ios.other') }
    case 'android-chrome': return { label: 'Android · Chrome', steps: [{ text: t('in.and.chrome.1'), icon: 'dots' }, { text: t('in.and.chrome.2'), icon: 'install' }, { text: t('in.and.chrome.3') }] }
    case 'android-samsung': return { label: 'Android · Samsung Internet', steps: [{ text: t('in.and.samsung.1'), icon: 'menu' }, { text: t('in.and.samsung.2'), icon: 'addSquare' }, { text: t('in.and.samsung.3') }] }
    case 'android-firefox': return { label: 'Android · Firefox', steps: [{ text: t('in.and.firefox.1'), icon: 'dots' }, { text: t('in.and.firefox.2'), icon: 'install' }, { text: t('in.and.firefox.3') }] }
    case 'desktop-chromium': return { label: 'Chrome · Edge', steps: [{ text: t('in.desk.chromium.1'), icon: 'install' }, { text: t('in.desk.chromium.2') }] }
    case 'desktop-safari': return { label: 'Safari · Mac', steps: [{ text: t('in.desk.safari.1'), icon: 'share' }] }
    case 'desktop-firefox': return { label: 'Firefox', steps: [], note: t('in.desk.firefox') }
    default: return { label: '', steps: [], note: t('in.other') }
  }
}

export function InstallSheet({ onClose, out }: { onClose: () => void; out?: boolean }) {
  const { t } = useI18n()
  const { platform, installed, canPrompt: canPromptRaw, promptInstall } = useInstall()
  const canPrompt = canPromptRaw && !platform.startsWith('ios') // iOS never has a prompt: always show the exact taps
  const { steps, note, label } = stepsFor(platform, t)
  return (
    <div className={`overlay ${out ? 'out' : ''}`} onClick={onClose}>
      <div className={`sheet ${out ? 'out' : ''}`} onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label={t('in.title')}>
        <div className="grabber" />
        <div className="center" style={{ padding: '4px 0 6px' }}>
          <AppIcon size={76} />
          <h2 style={{ fontSize: 26 }}>{t('in.title')}</h2>
          <p className="muted" style={{ maxWidth: 300 }}>{t('in.sub')}</p>
          {label && <span className="platform-tag">{label}</span>}
        </div>
        {installed ? (
          <div className="note"><Icon name="check" size={18} /><div>{t('in.done')}</div></div>
        ) : (
          <>
            {canPrompt && <button className="btn" onClick={async () => { if (await promptInstall()) onClose() }}><Icon name="install" size={20} />{t('in.button')}</button>}
            {!canPrompt && steps.length > 0 && (
              <ol className="steps">
                {steps.map((s, i) => <li key={i}><span>{s.text}</span>{s.icon && <Icon name={s.icon} size={22} />}</li>)}
              </ol>
            )}
            {!canPrompt && note && <div className="note" style={{ margin: '14px 0' }}><Icon name="info" size={18} /><div>{note}</div></div>}
          </>
        )}
        <button className="btn ghost" onClick={onClose}>{installed ? t('close') : t('in.later')}</button>
      </div>
    </div>
  )
}
