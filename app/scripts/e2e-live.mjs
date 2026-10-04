// Opens the live camera with Chrome's fake webcam and prints what the plant gate says. Screenshots: ../artifacts/shots/live-*.png
//   node scripts/e2e-live.mjs <baseUrl>
import puppeteer from 'puppeteer-core'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const base = process.argv[2] ?? 'http://localhost:4180/'
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const out = fileURLToPath(new URL('../../artifacts/shots/', import.meta.url))
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const b = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox', '--use-fake-device-for-media-stream', '--use-fake-ui-for-media-stream'] })
const p = await b.newPage()
const errors = []
p.on('pageerror', (e) => errors.push(e.message))
await p.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
await p.goto(base, { waitUntil: 'networkidle0' })
await p.evaluate(() => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: 'en', onboarded: true, theme: 'auto', place: { lat: -1.95, lon: 30.06, label: 'Kigali', country: 'RWA' }, currency: null, lastCrop: null, rain: null })))
await p.reload({ waitUntil: 'networkidle0' }); await wait(1200)
await p.click('.tabbar button:nth-of-type(2)'); await wait(1500)
await p.click('.btn.enter'); await wait(4500)
const hint = () => p.evaluate(() => ({ hint: document.querySelector('.live-hint')?.textContent, ok: !!document.querySelector('.live-frame.ok'), shutterDisabled: document.querySelector('.shutter')?.disabled }))
console.log('state:', await hint())
await p.screenshot({ path: out + 'live-1.png' })
// force the "plant found" look to check the animation styling regardless of what the fake webcam shows
await p.evaluate(() => { document.querySelector('.live-frame')?.classList.add('ok'); document.querySelector('.live-hint')?.classList.add('ok'); const s = document.querySelector('.shutter'); if (s) s.disabled = false })
await wait(900); console.log('after force:', await p.evaluate(() => ({ cls: document.querySelector('.live-frame')?.className, tl: getComputedStyle(document.querySelector('.live-frame .tl')).transform, outline: getComputedStyle(document.querySelector('.live-frame')).outlineColor }))); await p.screenshot({ path: out + 'live-2-ok.png' })
console.log('errors:', errors.length ? errors : 'none')
await b.close()
