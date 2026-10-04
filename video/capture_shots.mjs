// Captures the real app screens used in the demo video (phone size, 3x) -> video/shots/*.png.   node capture_shots.mjs <baseUrl> <leafImage>
import puppeteer from 'puppeteer-core'
import { existsSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const base = process.argv[2] ?? 'http://127.0.0.1:4173/'
const leaf = process.argv[3]
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const out = fileURLToPath(new URL('./shots/', import.meta.url))
mkdirSync(out, { recursive: true })
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const b = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] })

async function page(lang = 'en', extra = {}) {
  const p = await b.newPage()
  await p.setViewport({ width: 390, height: 844, deviceScaleFactor: 3, isMobile: true, hasTouch: true })
  await p.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: 'light' }])
  await p.goto(base, { waitUntil: 'networkidle0' })
  await p.evaluate((l, e) => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: l, onboarded: true, theme: 'light', place: { lat: -1.95, lon: 30.06, label: 'Kigali', country: 'RWA' }, currency: null, lastCrop: null, rain: null, ...e })), lang, extra)
  await p.reload({ waitUntil: 'networkidle0' }); await wait(1400)
  return p
}
const shot = (p, n) => p.screenshot({ path: out + n + '.png' })
const tab = async (p, i) => { await p.click(`.tabbar button:nth-of-type(${i})`); await wait(1800) }

for (const lang of (process.env.LANGS ?? 'en,rn').split(',')) {
  const p = await page(lang)
  await shot(p, `${lang}-home`)
  await tab(p, 2); await shot(p, `${lang}-scan`)
  if (leaf) {
    await (await p.$('input[type=file]:not([capture])')).uploadFile(leaf)
    await p.waitForSelector('.result-hero', { timeout: 60000 }); await wait(1200)
    console.log(lang, 'RESULT:', (await p.evaluate(() => document.querySelector('.result-hero')?.innerText.split(String.fromCharCode(10)).join(' / '))))
    await shot(p, `${lang}-result`)
    await p.evaluate(() => { document.querySelector('.view')?.scrollTo?.(0, 520); window.scrollTo(0, 520) }); await wait(500); await shot(p, `${lang}-result-2`)
  }
  await p.close()
}

if (!process.env.LANGS) {
const p = await page('en')
await tab(p, 3); await shot(p, 'en-prices')
await p.evaluate(() => { const r = [...document.querySelectorAll('.group .row')].find((x) => /Maize\b/.test(x.textContent) && !/flour/i.test(x.textContent)); (r ?? document.querySelector('.group .row')).click() })
await wait(1800); await shot(p, 'en-price-detail')
await p.goBack(); await wait(500)
await tab(p, 4); await shot(p, 'en-land')
await tab(p, 5); await shot(p, 'en-rain')
await p.close()

const q = await page('en')
await q.click('.settings-btn, button[aria-label*="ettings"], header button:last-of-type').catch(() => {}); await wait(1000)
await q.evaluate(() => [...document.querySelectorAll('button.row')].find((x) => /English/.test(x.textContent))?.click()); await wait(1000)
await shot(q, 'en-languages')
}
await b.close()
console.log('done')
