# Localization (en · fr · sw · rw · rn · so · yo)

Two layers of text:

| Layer | Where | How produced | Review status |
|---|---|---|---|
| **UI strings** (buttons, labels) | `app/src/i18n/strings.ts` | hand-written | en ✔ · fr ✔ · sw ✔ · **rw / rn / so / yo = draft, needs native review** |
| **Disease advice** (what / what to do / prevention) | `artifacts/advice.json` | expert English KB → **NLLB-200 (FLORES-200)** at build time (notebook 04) | en ✔ · others **machine translated** until overridden |
| Crop names (15) | `notebooks/src/04_advice_translation.py` `CROP_NAMES` | hand-written | review rw/rn/so/yo for non-EAC crops (apple, cherry…) |
| Commodity names (price screen) | `COMMODITY_NAMES` in `strings.ts` | hand-written for ~18 staples | others show the English WFP name |

## How a native speaker fixes a sentence (no coding)

1. Open `artifacts/review_sheet.json` – per language, the sentences whose round-trip quality score was low (most likely wrong) come first.
2. Create/extend `artifacts/translation_overrides.json`:
   ```json
   { "rw": { "Act today.": "Kora uyu munsi." } }
   ```
   Key = the **English** source sentence, value = your corrected translation.
3. Re-run `python notebooks/src/04_advice_translation.py` (seconds – translations are cached), then `npm run sync-data && npm run build`.
   Overrides always win over NLLB. A language is shown as "reviewed" (no *machine translated* banner) once it has an override file entry.

UI strings are edited directly in `strings.ts`; missing keys fall back to English, so partial translations are safe.

## Why the advice is pre-translated rather than generated on the phone
See ARCHITECTURE.md §3.4: closed label set → safer, instant, ~0.2 MB. Do **not** let a free-running model invent treatment advice.
A good next step for low-literacy users is **audio read-out** (MMS-TTS for rw/sw/yo/so are available) generated at build time from the same sentences.

## Safety decision (found during testing)
Raw NLLB output was unsafe for treatment advice: Kinyarwanda rendered "fungus" as *ingurube* (pig) and "fungicide" as "medicine that causes flu";
Swahili turned "Late blight" into "early pain". Round-trip chrF was only 46-59 for rw/rn/so/yo (57-68 of 140 sentences flagged).
Therefore every sentence is screened (placeholders, symbols, length, round-trip chrF) and unsafe ones fall back to English. In the app the answer is **always shown in the
chosen language** (the user asked for it); for languages without human-reviewed advice (`advice.json → reviewed[lang] = false`) a visible *"translated by computer, check with an
expert"* warning is shown, and an **"Also read in" card (English / Français / Español)** shows the reviewed text of the same diagnosis. Add native-speaker overrides to remove the warning.

**Shipped languages (16):** English, French, Spanish, Portuguese, Arabic, Hindi, Swahili (human-written/reviewed) + Kinyarwanda, Kirundi, Somali, Yoruba, Hausa, Igbo, Amharic,
Oromo, Tigrinya (machine translated, *beta*). The language list lives in `app/src/i18n/languages.ts`; the notebooks (07, 04) read the exported `artifacts/languages.json`, so
adding a language = one line there + `node scripts/export-i18n.mjs` + re-run notebooks 07 and 04 (the NLLB cache makes it incremental). 07 gives each string several candidate
translations and keeps the one whose back-translation is closest to the English (accept bar chrF 18).

**Audio:** to keep the app small **no voice packs are shipped**; Listen uses the phone's own speech engine (English, French, Spanish, Portuguese, Arabic, Hindi and Swahili are common on Android).
Where the phone has no voice for the language, the Listen button and the Settings voice row are hidden. The pack machinery is kept: `VOICE_LANGS=rn python notebooks/src/09_voice_packs.py` generates
offline Meta MMS-TTS clips (~1-2 MB per language, downloaded on demand, cached by the service worker) for languages whose phones have no voice, e.g. Kirundi.
