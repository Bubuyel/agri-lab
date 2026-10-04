# Agri Lab – offline AI for smallholder farmers (MVP)

One phone app, **no internet needed after the first install**, four small AI components:

| # | Feature | What the farmer sees | Model (all on-device) | Size |
|---|---|---|---|---|
| 1 | **Plant doctor** | Take a leaf photo → crop + disease (or *"not a plant, retake"*) | MobileNetV3-Small, 2 heads (crop / disease), int8 ONNX | ~1.5 MB |
| 2 | **Advice in 7 languages** | What it is, what to do, how to prevent (en, fr, sw, rw, rn, so, yo) | NLLB-200 (FLORES-200) translated the expert KB at build time → JSON | ~0.2 MB |
| 3 | **Crop prices** | Price now, 6-month forecast with range, best month to sell, nearby markets, currency conversion, export buyers | Gradient-boosted trees on WFP prices (exported as JSON trees) + FAOSTAT insights | ~2 MB |
| 4b | **Daily rain chance** | "Did it rain today/yesterday?" → chance of rain for the next 7 days at my location | 2nd-order wet/dry Markov chain per 0.5° cell and month (CHIRPS daily 2011-24) | ~1.7 MB |
| 5 | **My land** | Soil nutrients (K, P, N, organic C, pH), fertiliser to buy, best crops in %, rotation by last season’s crop | iSDAsoil + WorldClim + CHIRPS, FAO EcoCrop-style suitability rules | ~2.7 MB |
| 4 | **Rain outlook** | Next 3 months wetter/drier than normal at *my* location, rain calendar, last 12 months | Climatology + logistic model on CHIRPS anomalies, binary grids | ~3 MB |

```
agri-ai/
├─ notebooks/            ← run these (Colab/Kaggle/laptop); each is generated from notebooks/src/*.py
│   ├─ 01_crop_disease_vision.ipynb     PlantVillage + RoCoLe coffee → onnx (+ tflite best effort)
│   ├─ 02_crop_price_forecast.ipynb     WFP prices + FAOSTAT → price model, markets, fx
│   ├─ 03_rainfall_outlook.ipynb        CHIRPS → rain model + grids
│   ├─ 04_advice_translation.ipynb      expert KB → NLLB-200 → advice.json (7 languages)
│   ├─ 05_daily_rain.ipynb              CHIRPS daily (via IRI) → daily rain Markov model
│   └─ 06_land_soil_crops.ipynb         iSDAsoil + WorldClim + CHIRPS → soil, fertiliser, crop suitability
├─ artifacts/            ← everything the notebooks export (models, json, bin)  → copied into the app
├─ app/                  ← the mobile app (React + TypeScript + onnxruntime-web, installable PWA)
├─ scripts/              ← build_notebooks.py, build_overrides.py (fr/sw text + disease glossary), make_aux.py (countries, icons, test fixtures)
└─ docs/                 ← DEPLOY.md, ARCHITECTURE.md, DATA_ANALYSIS.md, LOCALIZATION.md
```

## Quick start

```bash
# 1. train / export (skip if artifacts/ is already filled)
pip install torch torchvision onnx onnxruntime pandas scikit-learn lightgbm tifffile transformers sentencepiece sacrebleu pycountry matplotlib
python notebooks/src/02_crop_price_forecast.py     # ~5 min  CPU
python notebooks/src/03_rainfall_outlook.py        # ~5 min  CPU
python notebooks/src/01_crop_disease_vision.py     # GPU ~20 min (set MAX_PER_CLASS=150 EPOCHS=4 for a CPU demo)
python scripts/build_overrides.py                  # hand-written fr/sw text + disease-name glossary
python notebooks/src/04_advice_translation.py      # downloads NLLB-600M (2.4 GB) once, translates rw/rn/so/yo
python notebooks/src/05_daily_rain.py             # ~15 min, downloads daily CHIRPS pre-averaged by IRI (~0.5 GB)
python notebooks/src/06_land_soil_crops.py         # ~3 min, reads iSDAsoil overviews over HTTP + WorldClim (50 MB)
python scripts/make_aux.py countries fixtures land daily   # countries.json, test fixtures

# 2. app
cd app && npm install && npm run sync-data && npm test && npm run build
```

The `.ipynb` files are generated from the `.py` sources: `python scripts/build_notebooks.py` (adds a Colab/Kaggle setup cell).
Paths are controlled by env vars (`AGRI_ROOT`, `CROP_DATA`, `WFP_DIR`, `FAO_DIR`, `CHIRPS_DIR`, `OUT_DIR`) so the notebooks run on
Colab/Kaggle unchanged.

See **[docs/DEPLOY.md](docs/DEPLOY.md)** to put it in testers' hands today and **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** for the design decisions.
