/**
 * Supported languages. `human` = interface + advice written/reviewed by a person (reliable);
 * the others are machine translated with NLLB-200 (FLORES-200) and quality-screened → shown with a "beta" tag, and for them the
 * app still shows the reviewed English advice as the main text (see ScanScreen).
 */
export type Lang = string

export interface LangInfo {
  code: Lang
  native: string
  english: string
  /** ISO 3166 country used for the flag (a language has no flag; we use its main country) */
  flag: string
  dir: 'ltr' | 'rtl'
  human: boolean
  region: 'africa' | 'asia' | 'world'
  /** FLORES-200 code used by the translation pipeline */
  nllb: string
  /** BCP-47 tag for Intl / speech synthesis */
  bcp: string
}

const L = (code: string, native: string, english: string, flag: string, region: LangInfo['region'], nllb: string, human = false, dir: 'ltr' | 'rtl' = 'ltr', bcp = code): LangInfo =>
  ({ code, native, english, flag, dir, human, region, nllb, bcp })

export const LANGUAGES: LangInfo[] = [
  // ── core (human-written) ──
  L('en', 'English', 'English', 'GB', 'world', 'eng_Latn', true),
  L('fr', 'Français', 'French', 'FR', 'world', 'fra_Latn', true),
  L('es', 'Español', 'Spanish', 'ES', 'world', 'spa_Latn', true),
  L('pt', 'Português', 'Portuguese', 'PT', 'world', 'por_Latn', true),
  L('ar', 'العربية', 'Arabic', 'EG', 'world', 'arb_Arab', true, 'rtl'),
  L('hi', 'हिन्दी', 'Hindi', 'IN', 'asia', 'hin_Deva', true),
  L('sw', 'Kiswahili', 'Swahili', 'KE', 'africa', 'swh_Latn', true),
  // ── Africa ──
  L('rw', 'Kinyarwanda', 'Kinyarwanda', 'RW', 'africa', 'kin_Latn'),
  L('rn', 'Ikirundi', 'Kirundi', 'BI', 'africa', 'run_Latn'),
  L('so', 'Soomaali', 'Somali', 'SO', 'africa', 'som_Latn'),
  L('yo', 'Yorùbá', 'Yoruba', 'NG', 'africa', 'yor_Latn'),
  L('ha', 'Hausa', 'Hausa', 'NG', 'africa', 'hau_Latn'),
  L('ig', 'Igbo', 'Igbo', 'NG', 'africa', 'ibo_Latn'),
  L('am', 'አማርኛ', 'Amharic', 'ET', 'africa', 'amh_Ethi'),
  L('om', 'Afaan Oromoo', 'Oromo', 'ET', 'africa', 'gaz_Latn'),
  L('ti', 'ትግርኛ', 'Tigrinya', 'ER', 'africa', 'tir_Ethi'),
  // ── Asia ──
]

export const LANG_BY_CODE: Record<string, LangInfo> = Object.fromEntries(LANGUAGES.map((l) => [l.code, l]))
export const langInfo = (c: string): LangInfo => LANG_BY_CODE[c] ?? LANG_BY_CODE.en
/** Languages shown first in pickers (the most widely used in the target regions). */
export const TOP_LANGS = ['en', 'fr', 'sw', 'es', 'hi', 'pt', 'ar']
/** the quick-pick pills on the first-run screen (the full list is one tap away) */
export const ONBOARDING_LANGS = ['en', 'fr', 'sw', 'es', 'hi', 'rn', 'yo']
