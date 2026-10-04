# Data analysis – what is in each dataset and how we used it

## 1 · Crop images (`Data-crop-diseases`)

| Source | Content | Use |
|---|---|---|
| `plantvillage-dataset/color` | 54 305 leaf photos, **38 classes** (14 crops), uniform lab background | main training images |
| `…/segmented` | same photos with background removed (black) | **leaf masks** → paste leaves on random backgrounds (field realism) |
| `…/grayscale` | same photos in grey | reproduced with `RandomGrayscale` (identical pixels, no 2nd copy needed) |
| `Coffee` (RoCoLe) | 1 560 **real-field smartphone** photos, polygons: `healthy`, `unhealthy`, `red_spider_mite`, `rust_level_1-4` | 3 classes: healthy / rust / red spider mite; leaf cropped from its polygon |
| `Coffee/research paper.pdf` | RoCoLe data paper (Parraga-Alava et al. 2019) | confirms capture conditions (smartphone, field) and that severity = leaf area with spots → rust levels merged into one *rust* class (a severity grade can be added later) |

Class balance (PlantVillage): 152 (potato healthy) → 5 507 (citrus greening) images per class → **sqrt-inverse-frequency sampling**.
Leakage: files are named `<uuid>___<leaf id>`; several photos share a leaf id → the split is made **by leaf id**.
Real-world gap: PlantVillage is lab imagery (published field accuracy of lab-trained models is far lower than lab accuracy) – see ARCHITECTURE §5.

## 2 · Prices (`WFP Independent price`)

* 41 CSVs (1990 → 2026-09) + `markets`, `commodities`, `currencies`. **4.63 M rows, 99 countries, 895 commodities, 5 088 markets.**
* Columns: `countryiso3, date, admin1, admin2, market, market_id, latitude, longitude, category, commodity, commodity_id, unit, priceflag, pricetype, currency, price, usdprice`.
  `price` = local currency, `usdprice` = USD; dates are monthly; `latitude/longitude` ~0.6 % missing.
* Issues found and handled: mis-dated rows in the `1900` file (2 392 rows before 1995), 100+ different `unit` strings (normalised to kg / litre, non-weight units dropped),
  4 692 price outliers (rolling-median ratio test), mixed Retail / Wholesale (retail preferred), gaps (≤ 4 months interpolated in log space, longer gaps cut the series).
* Result: ~1 100 national monthly series with ≥ 36 continuous months and recent data. Every figure (counts per country, backtest table) is printed by notebook 02.
* **Offline FX:** exchange rate implied by the data itself (`price / usdprice`, median of the last 3 months) → 50+ currencies convertible offline.
* **Nearby markets:** market coordinates + latest price per commodity → nearest markets by distance, ranked by USD price.

## 3 · FAOSTAT (`FAOSTAT_T-Z_E`)

| Folder | Looked at | Used? |
|---|---|---|
| Value of Production (590 MB) | gross production value per country × crop × year | **Yes** – 5-year production value + growth (is the crop growing in your country?) |
| Trade – Detailed Trade Matrix (2.4 GB) | reporter → partner flows by crop, quantity & value | **Yes** – top export destinations per country × crop (streamed in 2 M-row chunks, filtered to staples) |
| Trade – Crops & Livestock, Indicators, Indices | national totals, import dependency, unit-value indices | Not used in the MVP: macro-level, no actionable meaning for a single farmer; kept for a future "market outlook" |
| Value shares industry / Census of Agriculture | structural statistics (farm sizes, holdings) | Not used: structural, not time-sensitive |

Country codes: FAOSTAT M49 → ISO3 through `pycountry` so they join WFP.

## 4 · Rainfall (`CHIRPS`)

* Monthly CHIRPS v2.0, **1981-01 → 2026-08 (548 months)**, 0.05° (~5 km), mm/month, nodata `-9999`.
  Africa = 1600 × 1500 px per month (≈ 5 GB for the archive), EAC = 380 × 320.
* Reduced to 0.5° (Africa, 24 k cells) and 0.25° (EAC) by ≥ 50 %-valid block means → 2.9 MB binary for the app.
* **Climatology** 1991-2020 (WMO normal), tercile thresholds per cell and month; dry-season cells (p67 < 5 mm) are flagged instead of forecast.
* **Model:** multinomial logistic per (origin month, lead) on [last-month anomaly, 3-month anomaly, 7×7-cell neighbourhood anomaly].
  Evaluated on 2013-2026 by RPSS vs climatology, plus reliability diagram and a smoothed per-cell skill flag. See notebook 03 output for the exact numbers.
* Why not a deep model? Monthly rainfall anomalies from rainfall alone carry little predictable signal beyond climatology; more capacity would mostly fit noise.
  Real gains need ocean predictors (ENSO / IOD indices) – a cheap, small add-on for a next version (they are a few numbers per month and could ship in the app).

## 5 · Measured results (this machine, CPU demo run)
| Component | Result |
|---|---|
| Vision (8 epochs, 200 img/class, CPU) | clean test: crop 97.4 %, disease 91.9 %; "bad phone" simulation: crop 78 %, disease 64 %; unseen non-plant AUROC 0.987; gate catches 96 % of unseen non-plants, asks 14 % of real leaves to retake; fp32 ONNX 3.85 MB, 4 ms/image desktop. int8 quantisation was rejected automatically (accuracy collapse). Full GPU training (all images, 12 epochs) will be higher. |
| Prices (1 264 series, 146 in EAC+) | GBDT beats "price unchanged" by 0.5 % (1 mo) → 8 % (6 mo); EAC+ at 3 / 6 months: 0.121 / 0.162 vs 0.130 / 0.178; 80 % interval coverage 77-80 % on test |
| Rain | RPSS vs climatology on 2013-26: +0.015 (1 mo), +0.004 (2 mo), +0.001 (3 mo); extra features (6/12-month memory, larger neighbourhood) changed this by < 0.004, so the simple model is kept |
| Advice | fr / sw human-written (140/140 sentences); rw / rn / so / yo machine translated, flagged |

## 6 · Agri Lab additions (daily rain, soil, crop suitability)
* **Daily rain (notebook 05):** CHIRPS daily 2011-2024 aggregated to 0.5° *on the IRI server* (the CHC file server is throttled to ~100 KB/s). Wet day = cell-mean ≥ 1 mm.
  Second-order Markov chain per cell/month, neighbourhood-shrunk. Test 2021-24: Brier skill vs monthly climatology **+5.0 % tomorrow, +1.6 % day 2, ≈ 0 from day 5**; reliability gap 0.007 (well calibrated).
  Offline the phone cannot know today's weather, so the user answers "did it rain today / yesterday?".
* **Soil (notebook 06):** iSDAsoil Africa (30 m ML maps) read as pyramid overviews → 0.25° Africa grid and 0.05° EAC grid; layers pH, N, P, K, organic C, CEC, clay, sand.
  Values for Kigali (pH 6.3, K 145, P 15, N 1.7 g/kg) are plausible for the Rwandan highlands. Averaging 30 m predictions over 5-25 km cells gives a **regional** picture, not a field test.
* **Crops:** no field-level yield labels exist here, so this is **FAO EcoCrop-style rule-based suitability** (temperature, rain, pH, frost, wet-season length, texture, mild fertility factor) → percentages;
  rotation multipliers from agronomy rules. Validation on 12 well-known regions: **70 % of textbook staples appear in the top-6**; requirement ranges got one calibration pass.
  Fertiliser advice = low nutrient (class thresholds) ∩ crop demand → product + indicative kg/ha, always "confirm with your extension officer".
