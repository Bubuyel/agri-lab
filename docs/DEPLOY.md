# Deploying Agri Lab to testers (today)

Agri Lab ships as an **installable offline web app (PWA)**. Testers open one link in Chrome on Android, tap
**Install / Add to Home screen**, and from then on it works with **no internet** (all models and data are cached by the
service worker on first load).

## 0 · Build

```bash
cd agri-ai/app
npm install
npm run sync-data        # copies notebook outputs from ../artifacts into public/
npm test                 # parity tests: app math == notebook math
npm run build            # → dist/  (+ dist/sw.js, the offline cache)
```

`dist/` is a plain static folder (≈ 25 MB before compression, ≈ 8-10 MB over the wire with gzip/brotli).

## 1 · Host it (pick ONE, all free, all < 5 minutes)

| Option | Steps |
|---|---|
| **Netlify Drop** (easiest) | Go to <https://app.netlify.com/drop>, drag the `dist` folder in, copy the `https://….netlify.app` link. |
| **Cloudflare Pages** | Dashboard → Pages → *Upload assets* → drag `dist`. |
| **GitHub Pages** | Push `dist/` to a `gh-pages` branch → Settings → Pages. (`base: './'` makes sub-paths work.) |

HTTPS is **required** for the service worker and "Install" (all three give it for free).
No server code, no database, no API keys: nothing to maintain.

## 2 · What testers do

1. Open the link in **Chrome (Android)** while they have internet (≈ 10 MB first load).
2. Wait for the green **"Ready: works without internet"** on the home screen.
3. Menu ⋮ → **Install app** / **Add to Home screen**.
4. Turn on airplane mode and try it: scan a leaf, prices, rain.

iPhone: Safari → Share → *Add to Home Screen* (works the same; camera opens via the file picker).

## 3 · Updating

Re-run `npm run build` and re-upload `dist/`. The service worker cache is versioned by a content hash, so phones pick
up the new version the next time they open the app online (old cache is deleted automatically).

## 4 · Want a real `.apk` / Play Store build later? (same code, no rewrite)

```bash
npm i -D @capacitor/core @capacitor/cli @capacitor/android
npx cap init Agri Lab org.example.agriai --web-dir=dist
npx cap add android
npm run build && npx cap sync
npx cap open android        # Android Studio → Build → Build APK
```

Needs Android Studio + JDK (not installed on the dev machine used for this MVP). Camera/GPS work through the same web APIs.
If you later outgrow the web runtime, the notebooks already export a `.onnx` (and best-effort `.tflite`) for a native
Flutter / React-Native build.

## 5 · Troubleshooting

| Symptom | Cause / fix |
|---|---|
| "Install" button missing | Page not on HTTPS, or opened inside an in-app browser (WhatsApp/Facebook). Open in Chrome. |
| Works online, fails offline | First load was interrupted. Open once on Wi-Fi until "Ready: works without internet" appears. |
| "model is not installed" | `npm run sync-data` was run before the notebooks produced `labels.json` + the `.onnx`. Re-run both steps. |
| Old version after redeploy | Close all tabs of the app once, reopen online. |
