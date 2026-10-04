// Export the language list + English UI strings (+ which keys are hand-written per language) for the translation notebooks.
//   node scripts/export-i18n.mjs      → ../artifacts/languages.json, ui_en.json, ui_hand.json
import { build } from 'esbuild'
import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { join } from 'node:path'

const art = fileURLToPath(new URL('../../artifacts/', import.meta.url))
const tmp = fileURLToPath(new URL('../node_modules/.cache-i18n/', import.meta.url))
mkdirSync(tmp, { recursive: true })
for (const f of ['languages', 'strings']) {
  await build({ entryPoints: [fileURLToPath(new URL(`../src/i18n/${f}.ts`, import.meta.url))], bundle: true, format: 'esm', outfile: join(tmp, f + '.mjs'), logLevel: 'error' })
}
const { LANGUAGES } = await import(pathToFileURL(join(tmp, 'languages.mjs')).href)
const { STRINGS } = await import(pathToFileURL(join(tmp, 'strings.mjs')).href)
writeFileSync(art + 'languages.json', JSON.stringify(LANGUAGES, null, 1))
writeFileSync(art + 'ui_en.json', JSON.stringify(STRINGS.en, null, 1))
const hand = {}
for (const l of LANGUAGES) hand[l.code] = Object.keys(STRINGS[l.code] ?? {})
writeFileSync(art + 'ui_hand.json', JSON.stringify(hand))
writeFileSync(art + 'ui_strings.json', JSON.stringify(STRINGS))   // every hand-written UI dictionary (used by the assistant notebook)
console.log(`languages: ${LANGUAGES.length}, English UI keys: ${Object.keys(STRINGS.en).length}`)
