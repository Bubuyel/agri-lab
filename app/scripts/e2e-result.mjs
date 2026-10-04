// Scan one photo in a chosen language and screenshot the bottom of the result (the "Also read in" card).
//   LANG_CODE=rn node scripts/e2e-result.mjs <baseUrl> <image>
import puppeteer from 'puppeteer-core'
import { existsSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const [base, img] = [process.argv[2], process.argv[3]]
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const out = fileURLToPath(new URL('../../artifacts/shots/', import.meta.url))
const lang = process.env.LANG_CODE ?? 'en'
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const b = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] })
const p = await b.newPage()
await p.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
await p.goto(base, { waitUntil: 'networkidle0' })
await p.evaluate((l) => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: l, onboarded: true, theme: 'auto', place: { lat: -1.95, lon: 30.06, label: 'Kigali', country: 'RWA' }, currency: null, lastCrop: null, rain: null })), lang)
await p.reload({ waitUntil: 'networkidle0' }); await wait(1200)
await p.click('.tabbar button:nth-of-type(2)'); await wait(1500)
await (await p.$('input[type=file]:not([capture])')).uploadFile(img)
await p.waitForSelector('.result-hero', { timeout: 60000 }); await wait(1500)
await p.evaluate(() => { const v = document.querySelector('.view'); const a = document.querySelector('.also-read'); (a ?? v).scrollIntoView({ block: 'center' }) }); await wait(600)
console.log(process.argv[3].split('/').slice(-2).join('/'), '=>', await p.evaluate(() => document.querySelector('.result-hero')?.innerText.split(String.fromCharCode(10)).join(' / ')))
await p.screenshot({ path: out + 'result-' + lang + '-1.png' })
const pill = await p.$('.also-pills .pill'); if (pill) { await pill.click(); await wait(700); await p.evaluate(() => document.querySelector('.also-read')?.scrollIntoView({ block: 'start' })); await wait(400); await p.screenshot({ path: out + `result-${lang}-2.png` }) }
await b.close()
