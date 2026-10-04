# Agri Lab app

Offline-first PWA: React 19 + TypeScript + Vite + onnxruntime-web (WASM). No backend.

```
src/
  core/            pure logic, no UI imports (reusable in React Native / Capacitor / Node)
    vision/        preprocess (centre-square → 160px → ImageNet norm), ONNX session, decision rule
    price/         tree/ridge forecast, nearby markets, currency conversion
    rain/          binary-grid reader + logistic outlook
    geo.ts         haversine + GPS
  data/loaders.ts  cached fetch of /data/*.json|bin
  i18n/            7 languages (UI strings + commodity names)
  ui/              screens: Scan, Prices, Rain, Place picker, Chart components
  App.tsx          history-aware mini router (Android back button works)
scripts/
  sync-artifacts.mjs   copy notebook outputs + ORT wasm into public/
  gen-sw.mjs           post-build: writes dist/sw.js (precache everything → offline)
  e2e-shots.mjs        headless-Chrome smoke test + screenshots of every screen
tests/core.test.ts     parity tests vs python-generated fixtures (price + rain) and decision-rule tests
```

| Command | What it does |
|---|---|
| `npm run sync-data` | pull the latest model/data artifacts from `../artifacts` |
| `npm run dev` | dev server (service worker disabled in dev) |
| `npm test` | unit + parity tests |
| `npm run build` | strict type-check → production build → offline service worker |
| `npm run preview` | serve `dist/` locally (use HTTPS hosting to test install/offline on a phone) |
| `node scripts/e2e-shots.mjs <url> <leaf.jpg>` | full click-through + screenshots in `../artifacts/shots` |

Data contract between notebooks and app (`public/data`):
`labels.json` (+ `models/*.onnx`), `advice.json`, `price_model.json`, `price_series.json`, `markets.json`, `fx.json`,
`faostat_insights.json`, `countries.json`, `rain_model.json`, `rain_africa.bin`, `rain_eac.bin`.
