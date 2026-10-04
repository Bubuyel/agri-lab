import type { ForecastPoint } from '../core/types'
import { addMonths } from '../core/price/forecast'
import { useMonthLabel } from './common'

interface Props {
  history: number[]
  historyStart: string // YYYY-MM of history[0]
  forecast: ForecastPoint[]
  unit: string
}

/** Dependency-free SVG chart: past prices (solid), forecast (dashed) and the likely range (band). */
export function PriceChart({ history, historyStart, forecast }: Props) {
  const label = useMonthLabel()
  const hist = history.slice(-12)
  const hStart = addMonths(historyStart, history.length - hist.length)
  const n = hist.length + forecast.length
  const all = [...hist, ...forecast.flatMap((f) => [f.lo, f.hi])]
  const lo = Math.min(...all) * 0.95
  const hi = Math.max(...all) * 1.05
  const W = 340, H = 170, pl = 8, pr = 8, pt = 10, pb = 26
  const x = (i: number) => pl + (i * (W - pl - pr)) / (n - 1)
  const y = (v: number) => pt + ((hi - v) / (hi - lo || 1)) * (H - pt - pb)
  const last = hist.length - 1
  const line = hist.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')
  const fpts = [{ i: last, mid: hist[last], lo: hist[last], hi: hist[last] }, ...forecast.map((f, k) => ({ i: last + 1 + k, ...f }))]
  const fline = fpts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.mid).toFixed(1)}`).join(' ')
  const band =
    fpts.map((p, k) => `${k ? 'L' : 'M'}${x(p.i).toFixed(1)},${y(p.hi).toFixed(1)}`).join(' ') + ' ' +
    [...fpts].reverse().map((p) => `L${x(p.i).toFixed(1)},${y(p.lo).toFixed(1)}`).join(' ') + ' Z'
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="price chart">
      <path d={band} className="band" />
      <path d={line} className="hist" />
      <path d={fline} className="fore" />
      <line x1={x(last)} x2={x(last)} y1={pt} y2={H - pb} className="now" />
      <circle cx={x(last)} cy={y(hist[last])} r="4" className="dot" />
      <text x={pl} y={H - 8} className="axis">{label(hStart)}</text>
      <text x={x(last)} y={H - 8} className="axis" textAnchor="middle">{label(addMonths(hStart, last))}</text>
      <text x={W - pr} y={H - 8} className="axis" textAnchor="end">{label(forecast[forecast.length - 1].ym)}</text>
    </svg>
  )
}

/** 12-month bars: observed vs usual. */
export function RainBars({ values, labels, usual, highlight = [] }: { values: number[]; labels: string[]; usual?: number[]; highlight?: number[] }) {
  const W = 340, H = 140, pb = 20, pt = 8
  const max = Math.max(...values, ...(usual ?? []), 10)
  const bw = (W - 10) / values.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="rain chart">
      {values.map((v, i) => {
        const h = (v / max) * (H - pb - pt)
        return (
          <g key={i}>
            <rect x={5 + i * bw + 2} y={H - pb - h} width={bw - 4} height={Math.max(h, 1)} rx="3" className={highlight.includes(i) ? 'bar hl' : 'bar'} />
            {usual && <line x1={5 + i * bw} x2={5 + (i + 1) * bw} y1={H - pb - (usual[i] / max) * (H - pb - pt)} y2={H - pb - (usual[i] / max) * (H - pb - pt)} className="usual" />}
            <text x={5 + i * bw + bw / 2} y={H - 6} className="axis" textAnchor="middle">{labels[i]}</text>
          </g>
        )
      })}
    </svg>
  )
}
