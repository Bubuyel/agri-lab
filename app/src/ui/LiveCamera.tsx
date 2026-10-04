import { useCallback, useEffect, useRef, useState } from 'react'
import type { VisionMeta } from '../core/types'
import { glance } from '../core/vision/classifier'
import { useI18n } from '../i18n'
import { Icon } from './Icon'

type Hint = 'starting' | 'noPlant' | 'dark' | 'bright' | 'blur' | 'ready'
const MIN_BRIGHT = 45, MAX_BRIGHT = 238, MIN_SHARP = 18

/** Live viewfinder: the shutter unlocks only when the on-device model sees a plant in good light and in focus. Nothing leaves the phone. */
export function LiveCamera({ meta, onShot, onClose, onUnavailable }: { meta: VisionMeta; onShot: (f: Blob) => void; onClose: () => void; onUnavailable: () => void }) {
  const { t } = useI18n()
  const video = useRef<HTMLVideoElement>(null)
  const stream = useRef<MediaStream | null>(null)
  const [hint, setHint] = useState<Hint>('starting')
  const [pct, setPct] = useState(0)
  const [stale, setStale] = useState(false)

  useEffect(() => {
    let alive = true
    navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 1280 } }, audio: false })
      .then((st) => {
        if (!alive) return st.getTracks().forEach((x) => x.stop())
        stream.current = st
        if (video.current) { video.current.srcObject = st; void video.current.play() }
      })
      .catch(() => alive && onUnavailable())
    return () => { alive = false; stream.current?.getTracks().forEach((x) => x.stop()) }
  }, [onUnavailable])

  useEffect(() => {
    let busy = false
    const id = window.setInterval(async () => {
      const v = video.current
      if (busy || !v || v.readyState < 2 || !v.videoWidth) return
      busy = true
      try {
        const g = await glance(v, meta)
        setPct(Math.round(g.pPlant * 100))
        setHint(!g.plant ? 'noPlant' : g.brightness < MIN_BRIGHT ? 'dark' : g.brightness > MAX_BRIGHT ? 'bright' : g.sharpness < MIN_SHARP ? 'blur' : 'ready')
      } catch { /* keep the last hint */ } finally { busy = false }
    }, 650)
    const late = window.setTimeout(() => setStale(true), 7000)
    return () => { clearInterval(id); clearTimeout(late) }
  }, [meta])

  const shoot = useCallback(() => {
    const v = video.current
    if (!v || !v.videoWidth) return
    const c = document.createElement('canvas')
    c.width = v.videoWidth; c.height = v.videoHeight
    c.getContext('2d')!.drawImage(v, 0, 0)
    c.toBlob((b) => b && onShot(b), 'image/jpeg', 0.92)
  }, [onShot])

  const ready = hint === 'ready'
  return (
    <div className="live enter">
      <div className={`live-frame ${ready ? 'ok' : ''}`}>
        <video ref={video} playsInline muted autoPlay />
        <i className="corner tl" /><i className="corner tr" /><i className="corner bl" /><i className="corner br" />
        <div className={`live-hint ${ready ? 'ok' : ''}`}>
          <Icon name={ready ? 'check' : hint === 'starting' ? 'camera' : 'leaf'} size={16} />
          {t(`scan.live.${hint}`)}{hint !== 'starting' && ` · ${pct}%`}
        </div>
      </div>
      <button className="shutter" disabled={!ready} onClick={shoot} aria-label={t('scan.take')}><i /></button>
      <div className="live-links">
        <button className="link" onClick={onClose}>{t('scan.live.close')}</button>
        {stale && !ready && <button className="link" onClick={shoot}>{t('scan.live.anyway')}</button>}
      </div>
    </div>
  )
}
