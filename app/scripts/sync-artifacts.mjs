// Copy the artifacts produced by the training notebooks into the app's public/ folder.
//   node scripts/sync-artifacts.mjs [artifactsDir]
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync } from 'node:fs'
import { join, resolve } from 'node:path'

const src = resolve(process.argv[2] ?? '../artifacts')
const pub = resolve('public')
const data = ['labels.json', 'advice.json', 'price_model.json', 'price_series.json', 'markets.json', 'fx.json',
  'faostat_insights.json', 'countries.json', 'rain_model.json', 'rain_africa.bin', 'rain_eac.bin',
  'land_model.json', 'land_africa.bin', 'land_eac.bin', 'rain_daily.json', 'rain_daily.bin']
mkdirSync(join(pub, 'data'), { recursive: true })
mkdirSync(join(pub, 'models'), { recursive: true })
mkdirSync(join(pub, 'ort'), { recursive: true })

let missing = 0
for (const f of data) {
  if (existsSync(join(src, f))) copyFileSync(join(src, f), join(pub, 'data', f))
  else { console.warn('MISSING', f); missing++ }
}
// the model file name is declared in labels.json
if (existsSync(join(src, 'labels.json'))) {
  const mf = JSON.parse(readFileSync(join(src, 'labels.json'), 'utf8')).model_file
  if (existsSync(join(src, mf))) copyFileSync(join(src, mf), join(pub, 'models', mf))
  else { console.warn('MISSING model', mf); missing++ }
}
// onnxruntime-web WASM runtime (served locally so the app never needs a CDN)
const ort = resolve('node_modules/onnxruntime-web/dist')
for (const f of ['ort-wasm-simd-threaded.wasm', 'ort-wasm-simd-threaded.mjs']) copyFileSync(join(ort, f), join(pub, 'ort', f))
console.log(missing ? `done with ${missing} missing file(s)` : 'all artifacts synced')

// language packs (machine-translated UI) and voice packs (MP3 clips), copied as folders
function copyDir(from, to) {
  if (!existsSync(from)) return 0
  rmSync(to, { recursive: true, force: true }); mkdirSync(to, { recursive: true })
  let n = 0
  for (const e of readdirSync(from, { withFileTypes: true })) {
    if (e.isDirectory()) n += copyDir(join(from, e.name), join(to, e.name))
    else { copyFileSync(join(from, e.name), join(to, e.name)); n++ }
  }
  return n
}
console.log('language packs:', copyDir(join(src, 'lang'), join(pub, 'data', 'lang')), '| voice clips:', copyDir(join(src, 'audio'), join(pub, 'data', 'audio')))
