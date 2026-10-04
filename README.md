# Agri Lab: offline AI for smallholder farmers

**Live app: https://agrilab-nu.vercel.app** (open it on a phone, add it to the home screen, then use it in airplane mode)

One phone app, **works offline after its first online load**, with four small AI components that run **on the phone**. Nothing is uploaded: photos, location and settings never leave the device.

> **Important: open it online once first.** The app downloads everything it needs (about 30 MB: models, data, languages) the first time you open it with an internet connection. Wait for the green **"Ready: works without internet"** badge on the home screen. After that, and every time after, it works fully offline, including in airplane mode. If the first load is interrupted, just open it again while online.

| # | Feature | What the farmer sees | Model (all on-device) | Size |
|---|---|---|---|---|
| 1 | **Plant doctor** | Live camera that unlocks the shutter only when it sees a plant; result = crop + disease with probability bars, or *"not a plant"*, *"not in our data yet"* (e.g. banana, cassava) or *"I am not sure, retake"* | MobileNetV3-Small, 2 heads (crop / disease), 0.97 M parameters, fp32 ONNX | 3.9 MB |
| 2 | **Answers in 16 languages** | Diagnosis names, advice and the whole interface in the farmer's language, plus an "Also read in" card (English / Français / Español) | NLLB-200 translated the expert advice **once at build time** → JSON (no translation model on the phone) | ~0.3 MB |
| 3 | **Crop prices** | Price now, forecast with a likely range, best month to sell, nearby markets, currency conversion | LightGBM on WFP prices, exported as JSON trees and evaluated in TypeScript, plus FAOSTAT insights | ~2 MB |
| 4 | **Rain** | Rain outlook for the next 3 months and a **7-day chance of rain** at my location | CHIRPS climatology + logistic model; wet/dry Markov chain per 0.5° cell and month | ~4 MB |
| 5 | **My land** | Soil nutrients (K, P, N, organic C, pH), fertiliser to buy, best crops in %, rotation by last season's crop | iSDAsoil + WorldClim + CHIRPS with FAO EcoCrop-style suitability rules | ~2.7 MB |

Languages: English, Français, Español, Português, العربية, हिन्दी, Kiswahili (written by people) + Kinyarwanda, Ikirundi, Soomaali, Yorùbá, Hausa, Igbo, አማርኛ, Afaan Oromoo, ትግርኛ (machine translated, marked **beta**).

## How good is it? (honest numbers)

| Measurement | Result |
|---|---|
| Crop / disease accuracy on clean, held-out leaf photos | 91.6 % / 85.2 % |
| Crop / disease accuracy on **field-style** photos (real-world, harder) | **72.3 % / 59.4 %** |
| "Not a plant" detection (unseen object classes), AUROC | 0.986 (catches 96 % of non-plants) |
| Plants the model has never seen (banana, bean, cassava, ...) correctly flagged "not in our data yet" | 84 % (the other 16 % are wrongly answered as a supported crop; e.g. mango can be mistaken for maize) |
| Speed on one CPU thread | about 4 ms per photo |
| int8 quantisation | 1.3 MB, but accuracy collapsed (≈ 1 %), so **float32 is shipped** |

Weak spots: tomato diseases on field photos, and any plant outside the supported list. The app shows probabilities and says "not sure" instead of guessing. It is a guide, not a doctor.

## What's new (latest changes)

* **Open-set vision model (v2):** extra classes for banana / bean / cassava / other plants and a synthetic *not-a-plant* class, trained with PlantDoc field photos; fixes "banana leaf → red spider mite".
* **Live camera gate:** on-device plant / light / sharpness check before the shutter (needs `https`, so it works on the deployed site).
* **16 languages** with flags, RTL support, native names (Ikirundi first in the African list) and per-string quality checks with English fallback; translations run once at build time.
* **Answers always in the chosen language**; machine-translated languages show a warning and an English/French/Spanish reference card.
* **Listen button** uses the phone's own voice and is hidden when the phone has none (no voice packs are bundled, to keep the app small; the pack generator in notebook 09 remains).
* Removed the "Ask" chat screen; premium minimal UI, Liquid-Glass tab bar, install guide and desktop phone frame.
* **First-run notice everywhere:** the app, install guide and docs now say clearly that it must be opened **once online** to save everything, then works offline (16 languages).
* **Deployed on Vercel** with cache headers for the service worker (`app/vercel.json`).
* **Demo-video tooling** in `video/` (HTML scenes rendered frame by frame + ElevenLabs voice/effects/music). The videos themselves are not in the repo.

## Data sources and licences

We **do not redistribute the raw datasets** (they are downloaded by the notebooks/scripts). The repo contains only small derived artefacts (model weights, JSON/binary summaries). Licences below were read from each dataset's own card or file where possible; where marked *check*, confirm on the source page before any commercial use.

### Training data (plant photos)

| Data | Used for | Licence | Source / citation |
|---|---|---|---|
| PlantVillage (colour, grayscale, segmented) | Leaf crop + disease classes, leaf cut-outs for background-swap augmentation | No licence file in our copy; common mirrors tag it CC0 1.0 (*check*) | Hughes & Salathé 2015, arXiv:1511.08060 |
| PlantDoc (`Project-AgML/plant_doc_classification`) | Real-world field photos | **CC BY-SA 4.0** (share-alike) | Singh et al. 2020, CoDS-COMAD |
| RoCoLe robusta coffee leaves | Coffee leaf classes | CC BY 4.0 (file shipped with the dataset) | Parraga-Alava et al. 2019, *Data in Brief* |
| Beans (`AI-Lab-Makerere/beans`) | Bean class ("not in our data yet") | MIT | Makerere AI Lab |
| Banana leaf disease / nutrient (`Project-AgML/banana_*`) | Banana class | CC BY 4.0 | Project AgML |
| Cassava (`dpdl-benchmark/cassava`) | Cassava class | Not stated on the card (*check*) | Kaggle Cassava Leaf Disease data |
| Sugarcane leaf disease (`Project-AgML/...`) | "Other plant" examples | CC BY 4.0 | Project AgML |
| Cotton and tea leaf disease (`Project-AgML/...`) | "Other plant" examples | **CC BY-NC 4.0 (non-commercial)** | Project AgML |
| Rice and mango leaf disease (`Project-AgML/...`) | "Other plant" examples | Not stated on the card (*check*) | Project AgML |
| Indian plant leaves species (`avaishnav/...`) | "Other plant" examples | Apache-2.0 | Hugging Face |
| CIFAR-100 | Everyday objects/animals as *not-a-plant* negatives | No explicit licence; widely used for research | Krizhevsky 2009 |

### Prices, climate and soil

| Data | Used for | Licence | Source / citation |
|---|---|---|---|
| WFP food prices (market prices, 1990s-today) | Price forecast, markets, implied exchange rates | CC BY-IGO (HDX "WFP Food Prices"; *check* current terms) | World Food Programme, HDX |
| FAOSTAT (crop production, trade) | Export / production insights | FAO terms (CC BY-NC-SA 3.0 IGO or CC BY 4.0 depending on date; *check*) | FAO |
| CHIRPS v2 (monthly + daily rainfall, via UCSB-CHC and IRI Data Library) | Rain outlook, daily rain chance, climate normals | Free to use with citation | Funk et al. 2015, *Scientific Data* |
| iSDAsoil Africa (30 m soil maps) | Soil nutrients, pH, organic carbon | CC BY 4.0 | Hengl et al. 2021, *Scientific Reports* |
| WorldClim 2.1 (bio1, bio6) | Temperature limits for crop suitability | Free with citation; WorldClim's terms limit some commercial uses (*check*) | Fick & Hijmans 2017, *Int. J. Climatology* |
| FAO EcoCrop (crop requirements) | Suitability thresholds, re-typed as rules | FAO terms (*check*) | FAO EcoCrop database |

### Models, translation and software

| Component | Licence | Note |
|---|---|---|
| NLLB-200 (`facebook/nllb-200-distilled-600M`) and FLORES-200 | Model **CC BY-NC 4.0 (non-commercial)**; FLORES-200 CC BY-SA 4.0 | Used only at build time to produce the translated text shipped in the app. Treat the translated advice as research / non-commercial output until reviewed by native speakers or re-licensed. |
| MMS-TTS voices (`facebook/mms-tts-*`) | CC BY-NC 4.0 | Optional notebook 09 only; no clips are bundled |
| MobileNetV3-Small, ImageNet-pretrained weights | torchvision (BSD-3 code); ImageNet terms apply to the pretraining data | Fine-tuned on the datasets above |
| onnxruntime-web, React, Vite, TypeScript, LightGBM, PyTorch | MIT / BSD / Apache | See each package |
| Inter and Outfit fonts (bundled via `@fontsource`) | SIL Open Font License 1.1 | |
| Country flags | Simple inline SVG drawings | |

**Commercial use.** A commercial launch needs attention to: the CC BY-NC items (cotton / tea images, NLLB translations), PlantDoc's share-alike condition, WorldClim's terms, and the "check" rows above. The **source code in this repository has no licence file yet**, so by default all rights are reserved; add a licence (for example MIT or Apache-2.0) if you want others to reuse it.

## Repository layout

```
agri-ai/
├─ notebooks/src/        training / export code (01 vision, 02 prices, 03 rain outlook, 04 advice translation,
│                        05 daily rain, 06 land & soil, 07 UI language packs, 09 optional voice packs)
├─ scripts/              data download, hand-written translations (human/), build helpers
├─ artifacts/            exported models and data, copied into the app (no raw data, no caches)
├─ app/                  the PWA: React + TypeScript + onnxruntime-web, service worker, tests, vercel.json
├─ video/                demo-video tooling (scenes, ElevenLabs scripts; needs your own key in video/.env)
└─ docs/                 DEPLOY, ARCHITECTURE, DATA_ANALYSIS, LOCALIZATION, TESTER_GUIDE
```

## Quick start

```bash
# 1. train / export (skip if artifacts/ is already filled)
pip install torch torchvision onnx onnxruntime pandas scikit-learn lightgbm tifffile transformers sentencepiece sacrebleu pycountry matplotlib huggingface_hub
python scripts/fetch_extra_data.py                 # open-set / field photos from Hugging Face -> work/extra
python notebooks/src/02_crop_price_forecast.py
python notebooks/src/03_rainfall_outlook.py
python notebooks/src/01_crop_disease_vision.py     # CPU is fine but slow (about 10 min per epoch)
python notebooks/src/05_daily_rain.py
python notebooks/src/06_land_soil_crops.py
python scripts/build_overrides.py && python notebooks/src/04_advice_translation.py
python notebooks/src/07_ui_language_packs.py       # UI translations (set ONLY_LANGS=rn,yo to limit)

# 2. app
cd app && npm install && npm run sync-data && npm test && npm run build
npx vite preview            # try it locally; deploy the dist/ folder to any static host
```

Paths are controlled by env vars (`AGRI_ROOT`, `CROP_DATA`, `WFP_DIR`, `FAO_DIR`, `CHIRPS_DIR`, `OUT_DIR`). The raw PlantVillage, RoCoLe, WFP, FAOSTAT and CHIRPS downloads are expected next to the repo as described in the notebooks.

See **[docs/DEPLOY.md](docs/DEPLOY.md)**, **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**, **[docs/LOCALIZATION.md](docs/LOCALIZATION.md)** and **[docs/TESTER_GUIDE.md](docs/TESTER_GUIDE.md)**.
