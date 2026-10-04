// Proves the *production build* really works with the network switched OFF (all 5 tabs incl. the on-device scan).
//   npx vite preview --port 4173 &   then   node scripts/e2e-offline.mjs http://127.0.0.1:4173/ [leaf.jpg]
import puppeteer from 'puppeteer-core'
import { existsSync } from 'node:fs'

const base = process.argv[2] ?? 'http://127.0.0.1:4173/'
const leaf = process.argv[3]
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)
const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] })
const page = await browser.newPage()
await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true })
const errors = []
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message))
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const text = () => page.evaluate(() => document.body.innerText)
const ok = (c) => (c ? '✔' : 'FAILED ✘')
const tab = async (i) => { await page.click(`.tabbar button:nth-of-type(${i})`); await wait(1800) }

await page.goto(base, { waitUntil: 'networkidle0' })
await page.evaluate(() => localStorage.setItem('agriai.settings.v2', JSON.stringify({ lang: 'en', onboarded: true, theme: 'auto', place: { lat: -1.95, lon: 30.06, label: 'Kigali', country: 'RWA' } })))
await page.reload({ waitUntil: 'networkidle0' })
await page.evaluate(() => navigator.serviceWorker.ready.then(() => true))
await wait(1500)
console.log('online  home   :', ok((await text()).includes('Ready: works without internet')), 'offline-ready badge')

await page.setOfflineMode(true)
await page.reload({ waitUntil: 'load' }); await wait(1500)
console.log('offline home   :', ok((await text()).includes('Agri Lab')))
await tab(3); console.log('offline prices :', ok(/Bananas|Maize/.test(await text())))
await tab(4); console.log('offline land   :', ok((await text()).includes('Potassium')), 'soil nutrients')
await tab(5); console.log('offline rain   :', ok((await text()).includes('Next 7 days')), 'daily chances')
await page.click('.seg button:nth-child(2)'); await wait(800); console.log('offline months :', ok((await text()).includes('Rain through the year')))
if (leaf) {
  await tab(2)
  const input = await page.$('input[type=file]:not([capture])'); await input.uploadFile(leaf)
  await page.waitForSelector('.result-hero', { timeout: 60000 })
  console.log('offline scan   :', ok(true), (await text()).replace(/\n+/g, ' | ').slice(0, 150))
}
console.log(errors.length ? 'ERRORS:\n' + errors.join('\n') : 'no page errors')
await browser.close()
