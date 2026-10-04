import { useEffect, useState } from 'react'
import { canSpeak, isSpeaking, onSpeechChange, speak, stopSpeaking } from '../core/audio/speech'
import { useI18n } from '../i18n'
import { Icon } from './Icon'

/** "Listen" pill: reads the given sentences aloud in `lang` (voice pack clip if shipped, else the phone's voice). Hidden when no voice exists. */
export function Listen({ sentences, lang, className = '' }: { sentences: string[]; lang: string; className?: string }) {
  const { t } = useI18n()
  const [ok, setOk] = useState(false)
  const [on, setOn] = useState(false)
  useEffect(() => { let alive = true; canSpeak(lang, sentences).then((v) => alive && setOk(v)); const off = onSpeechChange(() => setOn(isSpeaking())); return () => { alive = false; off() } }, [lang, sentences.join('|')])
  useEffect(() => () => stopSpeaking(), [])
  if (!ok || sentences.length === 0) return null
  return (
    <button className={`listen ${className}`} onClick={() => (on ? stopSpeaking() : void speak(sentences, lang))} aria-label={t('audio.listen')}>
      <Icon name={on ? 'close' : 'sound'} size={16} />{on ? t('audio.stop') : t('audio.listen')}
    </button>
  )
}
