// Headless-Chrome click-through + screenshots of every screen (phone size, light + dark, plus a desktop "device frame" shot).
//   node scripts/e2e-shots.mjs [baseUrl] [leafImage]      env: LANG_CODE=en|fr|sw…  UA=ios|android (to preview the install sheet)
// Needs: puppeteer-core + a local Chrome/Edge. Output: ../artifacts/shots/*.png
import puppeteer from 'puppeteer-core'
import { existsSync, mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const base = process.argv[2] ?? 'http://127.0.0.1:5173/'
const leaf = process.argv[3]
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const out = fileURLToPath(new URL('../../artifacts/shots/', import.meta.url))
mkdirSync(out, { recursive: true })
const lang = process.env.LANG_CODE ?? 'en'
const wait = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] })
const errors = []
async function newPage(scheme, w = 390, h = 844, mobile = true) {
  const page = await browser.newPage()
  await page.setViewport({ width: w, height: h, deviceScaleFactor: 2, isMobile: mobile, hasTouch: mobile })
  await page.emulateMediaFeatures([{ name: 'prefers-color-scheme', value: scheme }])
  page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
  page.on('console', (m) => { if (m.type() === 'error' && !/favicon|manifest/.test(m.text())) errors.push('console: ' + m.text()) })
  return page
}
const seed = (page, extra = {}) => page.evaluate((l, e) => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: l, onboarded: true, theme: 'auto', place: { lat: -1.95, lon: 30.06, label: 'Kigali', country: 'RWA' }, currency: null, lastCrop: null, rain: null, ...e })), lang, extra)
const shot = (page, n) => page.screenshot({ path: out + n + '.png' })
const text = (page) => page.evaluate(() => document.body.innerText.replace(/\n+/g, ' | '))
const tab = async (page, i) => { await page.click(`.tabbar button:nth-of-type(${i})`); await wait(1700) }

// 1 ─ onboarding (fresh install, light)
let p = await newPage('light')
await p.goto(base, { waitUntil: 'networkidle0' })
await p.evaluate((l) => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: l })), lang)
await p.reload({ waitUntil: 'networkidle0' }); await wait(2300)
await shot(p, '01-welcome')
for (let i = 2; i <= 5; i++) { await p.click('.ob-bottom .btn'); await wait(1900); await shot(p, `0${i}-onboarding-${i - 1}`) }
await p.close()

// 2 ─ main app in light and dark
for (const scheme of ['light', 'dark']) {
  p = await newPage(scheme)
  await p.goto(base, { waitUntil: 'networkidle0' }); await seed(p); await p.reload({ waitUntil: 'networkidle0' }); await wait(1500)
  await shot(p, `10-home-${scheme}`)
  await tab(p, 2); await shot(p, `11-scan-${scheme}`)
  if (scheme === 'light' && leaf) {
    const input = await p.$('input[type=file]:not([capture])'); await input.uploadFile(leaf)
    await p.waitForSelector('.result-hero', { timeout: 60000 }); await wait(900); await shot(p, '12-scan-result')
    console.log('SCAN:', (await text(p)).slice(0, 300))
  }
  await tab(p, 3); await shot(p, `13-prices-${scheme}`)
  await p.click('.group .row'); await wait(1200); await shot(p, `14-price-detail-${scheme}`)
  console.log('PRICE DETAIL:', (await text(p)).slice(0, 260)); await p.goBack(); await wait(400)
  await tab(p, 4); await shot(p, `15-land-${scheme}`)
  console.log('LAND:', (await text(p)).slice(0, 700))
  if (scheme === 'light') {
    await seed(p, { lastCrop: 'maize' }); await p.reload({ waitUntil: 'networkidle0' }); await tab(p, 4); await shot(p, '16-land-after-maize')
    console.log('LAND after maize:', (await text(p)).slice(300, 900))
  }
  await tab(p, 5); await shot(p, `17-rain-days-${scheme}`)
  console.log('RAIN DAYS:', (await text(p)).slice(0, 400))
  await p.click('.seg button:nth-child(2)'); await wait(900); await shot(p, `18-rain-months-${scheme}`)
  await p.close()
}

// 3 ─ settings + install sheet (iPhone Safari, Android Chrome user agents)
for (const [name, ua] of [['ios', 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1'],
  ['android', 'Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36']]) {
  p = await newPage('light'); await p.setUserAgent(ua)
  await p.goto(base, { waitUntil: 'networkidle0' }); await seed(p); await p.reload({ waitUntil: 'networkidle0' }); await wait(1200)
  await p.click('.install-banner'); await wait(900); await shot(p, `20-install-${name}`)
  console.log(`INSTALL ${name}:`, (await p.evaluate(() => document.querySelector('.sheet')?.innerText ?? '')).replace(/\n+/g, ' | ').slice(0, 300))
  await p.close()
}
p = await newPage('dark')
await p.goto(base, { waitUntil: 'networkidle0' }); await seed(p); await p.reload({ waitUntil: 'networkidle0' }); await wait(1000)
await p.click('.largetitle .round-btn'); await wait(900); await shot(p, '21-settings-dark'); await p.close()

// 4 ─ desktop: the phone-style frame
p = await newPage('light', 1440, 900, false)
await p.goto(base, { waitUntil: 'networkidle0' }); await seed(p); await p.reload({ waitUntil: 'networkidle0' }); await wait(1500); await shot(p, '30-desktop-frame')
console.log(errors.length ? 'ERRORS:\n' + [...new Set(errors)].join('\n') : 'no console errors')
await browser.close()
