// Renders the Agri Lab mark to PNG app icons (192, 512, maskable 512, apple-touch 180) + favicon.svg using headless Chrome.
//   node scripts/make-icons.mjs
import puppeteer from 'puppeteer-core'
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const out = fileURLToPath(new URL('../public/icons/', import.meta.url))
mkdirSync(out, { recursive: true })
const chrome = ['C:/Program Files/Google/Chrome/Application/chrome.exe', 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'].find(existsSync)

const mark = (fg) => `
<g fill="none" stroke="${fg}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"><path d="M40.5 38V52L24.5 79.5C19.5 88.5 25 92 31 92H69C75 92 80.5 88.5 75.5 79.5L59.5 52V38M35.5 38H64.5"/></g>
<path d="M29.5 80.5Q39 74.5 50 79.5T70.5 80.5" fill="none" stroke="#4cd787" stroke-width="4.5" stroke-linecap="round"/>
<g fill="#4cd787"><path d="M47.5 33.5C39 33.5 34.2 27.4 35.2 19.6C42.4 19.6 47.4 24.8 47.5 33.5Z"/><path d="M52.5 33.5C51.6 22 59.6 13.6 74.5 11.4C75.6 25.6 66.8 33.6 52.5 33.5Z"/>
<path d="M50 62L52.7 67.3L58 70L52.7 72.7L50 78L47.3 72.7L42 70L47.3 67.3Z"/><path d="M61.5 61.5L62.5 63.6L64.6 64.6L62.5 65.6L61.5 67.7L60.5 65.6L58.4 64.6L60.5 63.6Z" opacity=".85"/></g>`

/** `scale` < 1 leaves a safe zone (maskable icons are cropped to a circle/squircle by the OS). */
const page = (size, scale, radius) => `<html><body style="margin:0;background:transparent">
<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 100 100">
<rect width="100" height="100" rx="${radius}" fill="#0b0b0c"/>
<g transform="translate(${50 - 50 * scale} ${50 - 50 * scale + 1}) scale(${scale})">${mark('#ffffff')}</g></svg></body></html>`

const browser = await puppeteer.launch({ executablePath: chrome, headless: true, args: ['--no-sandbox'] })
const p = await browser.newPage()
for (const [name, size, scale, radius] of [['icon-192.png', 192, 0.74, 22], ['icon-512.png', 512, 0.74, 22], ['maskable-512.png', 512, 0.56, 0], ['apple-touch-icon.png', 180, 0.74, 0]]) {
  await p.setViewport({ width: size, height: size, deviceScaleFactor: 1 })
  await p.setContent(page(size, scale, radius))
  await p.screenshot({ path: out + name, omitBackground: true })
}
await browser.close()

writeFileSync(out + 'favicon.svg', `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" rx="22" fill="#0b0b0c"/><g transform="translate(13 14) scale(0.74)">${mark('#ffffff')}</g></svg>`)
writeFileSync(out + '../manifest.webmanifest', JSON.stringify({
  name: 'Agri Lab', short_name: 'Agri Lab', description: 'Offline plant doctor, crop prices, rain outlook and soil advice for farmers',
  start_url: './', scope: './', display: 'standalone', orientation: 'portrait', background_color: '#0a0a0b', theme_color: '#0a0a0b', categories: ['agriculture', 'productivity'], prefer_related_applications: false, related_applications: [{ platform: 'webapp', url: 'manifest.webmanifest' }],
  icons: [{ src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' }, { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
    { src: 'icons/maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }],
}, null, 1))
console.log('icons + manifest written')
