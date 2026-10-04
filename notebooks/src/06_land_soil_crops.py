# %% [markdown]
# # 06 · "My land": soil nutrients, fertiliser and crop recommendation from satellite-derived maps (offline)
#
# **What the farmer gets after choosing a place:**
# 1. which nutrients the area is **rich / poor** in (potassium, phosphorus, nitrogen, organic matter, pH, CEC, texture);
# 2. **which fertiliser to buy** (and a rough rate), driven by those nutrient levels;
# 3. **which crops suit the area, as percentages**, and how that changes after **what was planted last season** (rotation);
# all computed **on the phone, offline**.
#
# ## Data (all open, downloaded here)
# | Layer | Source | How read |
# |---|---|---|
# | pH, N, P, K, organic C, CEC, clay, sand (0-20 cm) | **iSDAsoil Africa** (30 m, ML on remote-sensing + >100 k soil samples; CC-BY 4.0) – public Cloud-Optimized GeoTIFFs on AWS | HTTP range reads of the *pyramid overviews* (we never download the 28 GB files) |
# | Mean annual temperature, coldest-month minimum | **WorldClim 2.1** (bio1, bio6, 10′) | zip download (50 MB) |
# | Annual rain, length of the wet season | **CHIRPS** monthly 1991-2020 (your folder) | climatology |
#
# ## Model (and why it is *not* a black box)
# We have **no field-level crop-yield labels** for Africa in this project, so a supervised crop model would be a fiction.
# Instead we use the standard agronomic approach of **FAO EcoCrop-style suitability**: each crop has an *optimal* and an *absolute*
# range for temperature, annual rain, soil pH, coldest-month minimum (frost) and a minimum wet-season length. Each factor is a
# trapezoidal membership (1 inside the optimal range, falling to 0 at the absolute limits); a soil-texture factor is added;
# the score is a geometric mean. Scores are turned into **percentages** (`score³`, normalised over the viable crops).
# **Rotation** multiplies scores by agronomic rules (legumes after cereals ↑, same crop/family again ↓, …).
# We *validate* it against 12 well-known farming regions (does the textbook staple crop appear in the top-6?).
# It is a decision aid, **not a substitute for a soil test**: iSDAsoil predictions are 30 m model estimates which we average over 5-28 km cells here.

# %%
import os, io, json, gzip, glob, re, time, zipfile, urllib.request, warnings
from pathlib import Path
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import from_origin
from rasterio.windows import from_bounds
warnings.filterwarnings("ignore")

ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
CH = Path(os.environ.get("CHIRPS_DIR", ROOT / "CHIRPS"))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts")); OUT.mkdir(parents=True, exist_ok=True)
WORK = Path(os.environ.get("WORK_DIR", ROOT / "agri-ai" / "work")); WORK.mkdir(parents=True, exist_ok=True)
S3 = "https://isdasoil.s3.amazonaws.com/soil_data/{n}/{n}.tif"
GENV = dict(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="5", GDAL_HTTP_RETRY_DELAY="2")

# grids: Africa 0.25° (continent picture) and the EAC at 0.05° (≈5 km) aligned with the CHIRPS EAC grid
rm = json.load(open(OUT / "rain_model.json"))["grids"]
AFR = dict(name="africa", lon0=-20.0, lat0=40.0, res=0.25, nrow=320, ncol=300, ovr=128)
EAC = dict(name="eac", lon0=rm["eac"]["lon0"], lat0=rm["eac"]["lat0"], res=0.05, nrow=rm["eac"]["nrow"] * 5, ncol=rm["eac"]["ncol"] * 5, ovr=32)   # rain grid is 0.25° → ×5 = 0.05°
print("EAC grid:", EAC)

# %% [markdown]
# ## 1 · Read soil layers (remote overviews → regular lat/lon grid)
# iSDAsoil stores 8-bit transformed values: pH = x/10; N(g/kg) = exp(x/100) − 1; P, K (mg/kg), organic C (g/kg), CEC (cmol/kg) = exp(x/10) − 1;
# clay and sand are % as is. Value 255 = no data (desert, water, dense forest). We average the *encoded* values when aggregating to a coarser grid
# (for the log-scaled layers this is a geometric mean, which is the sensible average for skewed nutrient data).

# %%
LAYERS = [  # name, iSDA layer, decode(x) -> physical value, unit
    ("ph", "ph", lambda x: x / 10, ""), ("n", "nitrogen_total", lambda x: np.expm1(x / 100), "g/kg"),
    ("p", "phosphorous_extractable", lambda x: np.expm1(x / 10), "mg/kg"), ("k", "potassium_extractable", lambda x: np.expm1(x / 10), "mg/kg"),
    ("oc", "carbon_organic", lambda x: np.expm1(x / 10), "g/kg"), ("cec", "cation_exchange_capacity", lambda x: np.expm1(x / 10), "cmol/kg"),
    ("clay", "clay_content", lambda x: x, "%"), ("sand", "sand_content", lambda x: x, "%")]


def read_isda(layer, g):
    lon1 = g["lon0"] + g["ncol"] * g["res"]; lat1 = g["lat0"]; lat0 = g["lat0"] - g["nrow"] * g["res"]
    with rasterio.Env(**GENV), rasterio.open(S3.format(n=layer)) as ds:
        b = transform_bounds("EPSG:4326", ds.crs, g["lon0"], lat0, lon1, lat1)
        win = from_bounds(*b, transform=ds.transform)
        h, w = max(2, int(win.height // g["ovr"])), max(2, int(win.width // g["ovr"]))
        a = ds.read(1, window=win, out_shape=(h, w), boundless=True, fill_value=255, resampling=Resampling.average).astype("float32")
        wt = ds.window_transform(win); tr = wt * wt.scale(win.width / w, win.height / h)
        a[a >= 254.5] = np.nan
        dst = np.full((g["nrow"], g["ncol"]), np.nan, "float32")
        reproject(a, dst, src_transform=tr, src_crs=ds.crs, dst_transform=from_origin(g["lon0"], lat1, g["res"], g["res"]), dst_crs="EPSG:4326",
                  src_nodata=np.nan, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def soil_stack(g):
    cp = WORK / f"soil_{g['name']}.npz"
    if cp.exists(): return {k: v for k, v in np.load(cp).items()}
    d = {}
    for key, layer, dec, unit in LAYERS:
        t0 = time.time(); raw = read_isda(layer, g); d[key] = dec(raw).astype("float32"); print(f"  {g['name']:6s} {key:4s} {np.isfinite(d[key]).mean():.2f} valid  {time.time()-t0:.0f}s", flush=True)
    np.savez(cp, **d); return d


SOIL = {g["name"]: soil_stack(g) for g in (AFR, EAC)}
for nm, d in SOIL.items():
    print(nm, {k: tuple(np.nanpercentile(v, [5, 50, 95]).round(1)) for k, v in d.items()})

# %% [markdown]
# ## 2 · Climate: temperature (WorldClim) and rainfall (CHIRPS)

# %%
def worldclim():
    z = WORK / "wc2.1_10m_bio.zip"
    if not z.exists():
        print("downloading WorldClim 10' bioclim (50 MB)…")
        urllib.request.urlretrieve("https://geodata.ucdavis.edu/climate/worldclim/2_1/base/wc2.1_10m_bio.zip", z)
    out = {}
    with zipfile.ZipFile(z) as zf:
        for key, n in (("tmean", 1), ("tmin", 6)):
            name = [x for x in zf.namelist() if x.endswith(f"_bio_{n}.tif")][0]
            zf.extract(name, WORK); out[key] = WORK / name
    return out

WC = worldclim()


def climate_grid(path, g, resampling=Resampling.bilinear):
    with rasterio.open(path) as ds:
        dst = np.full((g["nrow"], g["ncol"]), np.nan, "float32")
        reproject(rasterio.band(ds, 1), dst, dst_transform=from_origin(g["lon0"], g["lat0"], g["res"], g["res"]), dst_crs="EPSG:4326",
                  src_nodata=ds.nodata, dst_nodata=np.nan, resampling=resampling)
    return dst

CLIM = {g["name"]: {k: climate_grid(p, g) for k, p in WC.items()} for g in (AFR, EAC)}

# CHIRPS monthly climatology 1991-2020 (mm/month)
def chirps_clim(g):
    cp = WORK / f"chirps_clim_{g['name']}.npy"
    if cp.exists(): return np.load(cp)
    if g["name"] == "africa":                                  # reuse the 0.5° monthly cache from notebook 03, upsample ×2 to 0.25°
        z = np.load(OUT / "cache" / "africa_k10.npz", allow_pickle=True); X, M = z["x"], z["months"]
        c = np.stack([np.nanmean(X[(M[:, 0] >= 1991) & (M[:, 0] <= 2020) & (M[:, 1] == m)], 0) for m in range(1, 13)])
        c = np.repeat(np.repeat(c, 2, 1), 2, 2)
    else:                                                      # EAC: native 0.05° monthly tifs
        import tifffile
        files = sorted(glob.glob(str(CH / "EAC_monthly" / "tifs" / "*.tif.gz")))
        acc = np.zeros((12, g["nrow"], g["ncol"])); cnt = np.zeros_like(acc)
        for f in files:
            y, m = map(int, re.search(r"(\d{4})\.(\d{2})", f).groups())
            if 1991 <= y <= 2020:
                a = tifffile.imread(io.BytesIO(gzip.open(f).read())).astype("float32"); ok = a >= 0
                acc[m - 1] += np.where(ok, a, 0); cnt[m - 1] += ok
        c = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    np.save(cp, c.astype("float32")); return c.astype("float32")

for g in (AFR, EAC):
    c = chirps_clim(g); CLIM[g["name"]]["rain_m"] = c
    CLIM[g["name"]]["rain"] = np.nansum(c, 0); CLIM[g["name"]]["rain"][np.isnan(c).all(0)] = np.nan
    # longest run of consecutive months (circular) with ≥ 50 mm = length of the growing season
    wet = (np.nan_to_num(c) >= 50).astype(int); best = np.zeros(c.shape[1:], int); run = np.zeros_like(best)
    for m in list(range(12)) * 2:
        run = np.where(wet[m] == 1, run + 1, 0); best = np.maximum(best, np.minimum(run, 12))
    CLIM[g["name"]]["wet"] = np.where(np.isnan(c).all(0), np.nan, best).astype("float32")
    print(g["name"], "annual rain pctl", np.nanpercentile(CLIM[g["name"]]["rain"], [5, 50, 95]).round(0), "| wet months pctl", np.nanpercentile(best, [5, 50, 95]))
for nm in CLIM: print(nm, "tmean pctl", np.nanpercentile(CLIM[nm]["tmean"], [5, 50, 95]).round(1), "tmin", np.nanpercentile(CLIM[nm]["tmin"], [5, 50, 95]).round(1))

# fill NaN soil/climate cells that lie within 3 cells of valid data (coastlines, small lakes, mask edges) with the nearest valid value,
# so a point on the coast does not return "no data"; far-away desert/ocean stays empty.
from scipy import ndimage
def fill_near(a, radius=3):
    bad = ~np.isfinite(a)
    if bad.all(): return a
    d, (ri, ci) = ndimage.distance_transform_edt(bad, return_indices=True)
    return np.where(bad & (d <= radius), a[ri, ci], a)
for nm in SOIL:
    ok = np.isfinite(SOIL[nm]["ph"]); rad = 3 if nm == "africa" else 8
    for k in SOIL[nm]: SOIL[nm][k] = fill_near(SOIL[nm][k], rad)
    for k in ("tmean", "tmin", "rain", "wet"): CLIM[nm][k] = fill_near(CLIM[nm][k], rad)

# %% [markdown]
# ## 3 · Crop requirements (FAO EcoCrop-style) and the suitability model
# Ranges `[absolute-min, optimal-min, optimal-max, absolute-max]`. Annual rain is the *rain-fed* requirement (irrigated vegetables get wide ranges).
# `cycle` = months of rain needed (annuals); `kill` = coldest-month mean minimum below which the crop suffers; `tex` = texture preference.
# Values are rounded from the FAO EcoCrop database and extension handbooks – **edit this table with your agronomists**; the app reads it from JSON.

# %%
CROPS = [
 # id, family, perennial, legume, T, rain, pH, cycle, kill, tex, N/P/K demand
 dict(id="maize", fam="cereal", T=[10, 18, 27, 35], R=[400, 600, 1500, 2200], pH=[4.8, 5.5, 7.0, 8.0], cycle=4, kill=2, tex="any", dem="NPK"),
 dict(id="sorghum", fam="cereal", T=[15, 22, 30, 38], R=[300, 450, 1000, 1600], pH=[4.5, 5.5, 7.5, 8.5], cycle=4, kill=5, tex="any", dem="NP"),
 dict(id="millet", fam="cereal", T=[17, 25, 32, 40], R=[200, 300, 900, 1400], pH=[4.5, 5.5, 7.5, 8.5], cycle=3, kill=8, tex="light", dem="NP"),
 dict(id="rice", fam="cereal", T=[16, 22, 30, 38], R=[700, 1000, 2000, 3000], pH=[4.2, 5.0, 6.5, 7.8], cycle=4, kill=8, tex="heavy", dem="NPK"),
 dict(id="wheat", fam="cereal", T=[5, 12, 20, 28], R=[300, 400, 800, 1200], pH=[5.0, 6.0, 7.5, 8.5], cycle=4, kill=-6, tex="any", dem="NP"),
 dict(id="cassava", fam="root", T=[15, 22, 29, 35], R=[500, 800, 1500, 3000], pH=[4.5, 5.5, 7.0, 8.0], cycle=3, kill=8, tex="light", dem="K"),
 dict(id="sweetpotato", fam="root", T=[12, 20, 27, 32], R=[500, 750, 1500, 2500], pH=[4.5, 5.5, 6.5, 8.0], cycle=4, kill=5, tex="light", dem="K"),
 dict(id="potato", fam="solanaceae", T=[8, 14, 20, 26], R=[400, 600, 1200, 2000], pH=[4.5, 5.0, 6.5, 7.5], cycle=4, kill=0, tex="light", dem="NPK"),
 dict(id="bean", fam="legume", legume=True, T=[10, 16, 24, 30], R=[350, 500, 1500, 2200], pH=[5.0, 6.0, 7.0, 8.0], cycle=3, kill=5, tex="any", dem="P"),
 dict(id="groundnut", fam="legume", legume=True, T=[15, 22, 28, 35], R=[400, 600, 1200, 2000], pH=[4.5, 5.5, 7.0, 8.0], cycle=4, kill=6, tex="light", dem="PK"),
 dict(id="soybean", fam="legume", legume=True, T=[14, 20, 28, 34], R=[450, 600, 1200, 1800], pH=[5.0, 6.0, 7.0, 8.0], cycle=4, kill=5, tex="any", dem="PK"),
 dict(id="cowpea", fam="legume", legume=True, T=[15, 22, 30, 38], R=[300, 500, 1100, 1800], pH=[4.5, 5.5, 7.0, 8.5], cycle=3, kill=8, tex="light", dem="P"),
 dict(id="banana", fam="perennial", perennial=True, T=[15, 22, 28, 35], R=[900, 1200, 2500, 4000], pH=[4.5, 5.5, 7.0, 8.0], cycle=7, kill=10, tex="any", dem="NK"),
 dict(id="coffee_arabica", fam="perennial", perennial=True, T=[10, 16, 22, 28], R=[800, 1200, 2000, 2800], pH=[4.5, 5.5, 6.5, 7.5], cycle=6, kill=4, tex="any", dem="NK"),
 dict(id="coffee_robusta", fam="perennial", perennial=True, T=[18, 22, 26, 30], R=[1000, 1500, 2500, 3000], pH=[4.5, 5.5, 6.5, 7.5], cycle=6, kill=8, tex="any", dem="NK"),
 dict(id="tea", fam="perennial", perennial=True, T=[10, 15, 22, 28], R=[1100, 1500, 3000, 4000], pH=[4.0, 4.5, 5.5, 6.5], cycle=8, kill=0, tex="any", dem="N"),
 dict(id="tomato", fam="solanaceae", T=[12, 20, 27, 32], R=[400, 600, 1500, 2500], pH=[5.0, 6.0, 7.0, 8.0], cycle=2, kill=6, tex="any", dem="NPK"),
 dict(id="onion", fam="alliaceae", T=[8, 14, 24, 30], R=[350, 500, 1000, 1500], pH=[5.0, 6.0, 7.0, 8.0], cycle=2, kill=-6, tex="light", dem="NPK"),
 dict(id="cabbage", fam="brassica", T=[7, 14, 20, 26], R=[350, 500, 1200, 2000], pH=[5.0, 6.0, 7.0, 8.0], cycle=2, kill=-6, tex="any", dem="NPK"),
 dict(id="sunflower", fam="asteraceae", T=[10, 18, 25, 32], R=[350, 500, 1000, 1500], pH=[5.0, 6.0, 7.5, 8.5], cycle=3, kill=0, tex="any", dem="NP"),
]
for c in CROPS:
    c.setdefault("legume", False); c.setdefault("perennial", False)
    c["w"] = 0.6 if c["id"] in ("tomato", "onion", "cabbage") else 1.0   # vegetables: need irrigation, inputs and a market → down-weighted
NAMES = {  # display names (hand-written; review rw/rn/so/yo with native speakers)
 "maize": dict(en="Maize", fr="Maïs", sw="Mahindi", rw="Ibigori", rn="Ibigori", so="Galley", yo="Àgbàdo"),
 "sorghum": dict(en="Sorghum", fr="Sorgho", sw="Mtama", rw="Amasaka", rn="Amasaka", so="Durra", yo="Ọkà baba"),
 "millet": dict(en="Millet", fr="Mil", sw="Ulezi", rw="Uburo", rn="Uburo", so="Hirsi", yo="Ọkà bàbà"),
 "rice": dict(en="Rice", fr="Riz", sw="Mpunga", rw="Umuceri", rn="Umuceri", so="Bariis", yo="Ìrẹsì"),
 "wheat": dict(en="Wheat", fr="Blé", sw="Ngano", rw="Ingano", rn="Ingano", so="Sarreen", yo="Alikama"),
 "cassava": dict(en="Cassava", fr="Manioc", sw="Muhogo", rw="Imyumbati", rn="Imyumbati", so="Rooti", yo="Ẹ̀gẹ́"),
 "sweetpotato": dict(en="Sweet potato", fr="Patate douce", sw="Viazi vitamu", rw="Ibijumba", rn="Ibijumba", so="Baradho macaan", yo="Ànàmọ́"),
 "potato": dict(en="Potato", fr="Pomme de terre", sw="Viazi mviringo", rw="Ibirayi", rn="Ibirayi", so="Baradho", yo="Ọdùnkún"),
 "bean": dict(en="Beans", fr="Haricots", sw="Maharage", rw="Ibishyimbo", rn="Ibiharage", so="Digir", yo="Ẹ̀wà"),
 "groundnut": dict(en="Groundnut", fr="Arachide", sw="Karanga", rw="Ubunyobwa", rn="Ubunyobwa", so="Fuul sudaan", yo="Ẹ̀pà"),
 "soybean": dict(en="Soybean", fr="Soja", sw="Soya", rw="Soya", rn="Soya", so="Soya", yo="Soyà"),
 "cowpea": dict(en="Cowpea", fr="Niébé", sw="Kunde", so="Digir yar", yo="Ẹ̀wà ewùrà"),
 "banana": dict(en="Banana", fr="Banane", sw="Ndizi", rw="Ibitoki", rn="Ibitoke", so="Muuz", yo="Ọ̀gẹ̀dẹ̀"),
 "coffee_arabica": dict(en="Coffee (arabica)", fr="Café arabica", sw="Kahawa (arabika)", rw="Ikawa (arabika)", rn="Ikawa (arabika)", so="Bun (arabika)", yo="Kọfí (arabika)"),
 "coffee_robusta": dict(en="Coffee (robusta)", fr="Café robusta", sw="Kahawa (robusta)", rw="Ikawa (robusta)", rn="Ikawa (robusta)", so="Bun (robusta)", yo="Kọfí (robusta)"),
 "tea": dict(en="Tea", fr="Thé", sw="Chai", rw="Icyayi", rn="Icayi", so="Shaah", yo="Tíì"),
 "tomato": dict(en="Tomato", fr="Tomate", sw="Nyanya", rw="Inyanya", rn="Inyanya", so="Yaanyo", yo="Tòmátì"),
 "onion": dict(en="Onion", fr="Oignon", sw="Kitunguu", rw="Igitunguru", rn="Igitunguru", so="Basal", yo="Alubọ́sà"),
 "cabbage": dict(en="Cabbage", fr="Chou", sw="Kabichi", rw="Amashu", rn="Amashu", so="Kabaash", yo="Kábéèjì"),
 "sunflower": dict(en="Sunflower", fr="Tournesol", sw="Alizeti", so="Dabaqa", yo="Ìtànná oòrùn"),
}
for c in CROPS: c["names"] = NAMES[c["id"]]


def trap(x, q):
    """Membership in [0,1]: 0 outside the absolute range, 0.85 at the edge of the optimal range, rising to 1.0 at its centre.
    (A flat 1.0 over the whole optimal range made many crops tie; this rewards being *near the optimum*.)"""
    a, b, c_, d = q
    x = np.asarray(x, float)
    half = (c_ - b) / 2 + 1e-9; mid = (b + c_) / 2
    inside = 0.85 + 0.15 * (1 - np.abs(x - mid) / half)
    below = 0.85 * (x - a) / (b - a); above = 0.85 * (d - x) / (d - c_)
    return np.clip(np.where((x >= b) & (x <= c_), inside, np.where(x < b, below, above)), 0, 1)


def texture_factor(tex, clay, sand):
    if tex == "light":  return np.where(clay > 45, 0.7, np.where(clay > 35, 0.9, 1.0))
    if tex == "heavy":  return np.where(sand > 70, 0.7, np.where(sand > 60, 0.9, 1.0))
    return np.where((clay > 60) | (sand > 80), 0.75, 1.0)


def fertility_factor(oc, n, cec):
    """Mild bonus/penalty for natural fertility (0.8-1.0); fertiliser can compensate, so it is deliberately small."""
    idx = (np.clip(oc / 20, 0, 1) + np.clip(n / 2, 0, 1) + np.clip(cec / 20, 0, 1)) / 3
    return 0.8 + 0.2 * idx


def suitability(c, T, Tmin, R, wet, pH, clay, sand, oc=15.0, n=1.5, cec=15.0):
    """Score in [0,1]: geometric mean of the climate/soil memberships × texture × fertility."""
    mT, mR, mP = trap(T, c["T"]), trap(R, c["R"]), trap(pH, c["pH"])
    mF = np.clip((Tmin - (c["kill"] - 3)) / 3, 0, 1)
    season = np.clip((wet + (3 if c["perennial"] else 0.5)) / c["cycle"], 0, 1) if c["cycle"] > 2 else 1.0
    s = np.cbrt(np.clip(mT * mR * mP * mF * season, 0, 1)) * texture_factor(c["tex"], clay, sand) * fertility_factor(oc, n, cec) * c["w"]
    return np.where(np.isfinite(s), s, np.nan)


SHARE_POWER, SHARE_FLOOR = 6, 0.4
def shares(S, mult=None, top=8, floor=SHARE_FLOOR):
    """S: (nCrops,) scores → percentages (sum to 100 over the viable crops; a high power sharpens the ranking)."""
    s = np.array(S, float) * (np.array(mult) if mult is not None else 1)
    s = np.where(s >= floor, s, 0) ** SHARE_POWER
    if s.sum() == 0: return np.zeros_like(s)
    idx = np.argsort(-s)[top:]; s[idx] = 0
    return 100 * s / s.sum()

# %% [markdown]
# ## 4 · Validation against well-known farming regions
# For 12 places we list the staple crops any extension officer would name. Metric: **share of those staples that appear in the model's top-6**
# (random guessing would score ~30 %, because 20 crops are candidates).

# %%
REF = {  # place: (lat, lon, expected staples)
 "Kigali RW": (-1.95, 30.06, {"bean", "maize", "potato", "banana", "sweetpotato", "coffee_arabica"}),
 "Nairobi KE": (-1.29, 36.82, {"maize", "bean", "potato", "cabbage", "coffee_arabica", "wheat"}),
 "Kisumu KE": (-0.10, 34.75, {"maize", "sorghum", "cassava", "sweetpotato", "bean", "rice"}),
 "Dodoma TZ": (-6.17, 35.74, {"sorghum", "millet", "groundnut", "sunflower", "maize"}),
 "Kano NG": (12.00, 8.52, {"sorghum", "millet", "groundnut", "cowpea", "maize"}),
 "Lagos NG": (6.50, 3.40, {"cassava", "maize", "banana", "rice"}),
 "Kampala UG": (0.35, 32.58, {"banana", "coffee_robusta", "cassava", "bean", "sweetpotato", "maize"}),
 "Mbeya TZ": (-8.90, 33.45, {"maize", "potato", "bean", "tea", "coffee_arabica", "wheat"}),
 "Gitega BI": (-3.43, 29.93, {"bean", "banana", "maize", "sweetpotato", "cassava", "coffee_arabica"}),
 "Lusaka ZM": (-15.40, 28.30, {"maize", "groundnut", "soybean", "sunflower", "sorghum"}),
 "Bamako ML": (12.60, -8.00, {"sorghum", "millet", "maize", "groundnut", "cowpea"}),
 "Gondar ET": (12.60, 37.45, {"wheat", "maize", "bean", "potato", "sorghum", "millet"}),
}

def cell_vals(nm, g, lat, lon):
    r, c = int((g["lat0"] - lat) / g["res"]), int((lon - g["lon0"]) / g["res"])
    S, C = SOIL[nm], CLIM[nm]
    return dict(T=C["tmean"][r, c], Tmin=C["tmin"][r, c], R=C["rain"][r, c], wet=C["wet"][r, c], pH=S["ph"][r, c], clay=S["clay"][r, c], sand=S["sand"][r, c],
                oc=S["oc"][r, c], n=S["n"][r, c], cec=S["cec"][r, c])

def rank_at(nm, g, lat, lon):
    v = cell_vals(nm, g, lat, lon)
    if not all(np.isfinite(list(v.values()))): return None, v
    sc = np.array([suitability(c, **v) for c in CROPS]); return sc, v

hits, tot = 0, 0
for place, (lat, lon, exp) in REF.items():
    nm, g = ("eac", EAC) if (EAC["lon0"] < lon < EAC["lon0"] + EAC["ncol"] * EAC["res"] and EAC["lat0"] - EAC["nrow"] * EAC["res"] < lat < EAC["lat0"]) else ("africa", AFR)
    sc, v = rank_at(nm, g, lat, lon)
    if sc is None: print(f"{place:12s} no soil data"); continue
    sh = shares(sc); order = np.argsort(-sh)[:6]; top = [CROPS[i]["id"] for i in order]
    h = len(exp & set(top)); hits += h; tot += len(exp)
    txt = ", ".join("%s %.0f%%" % (CROPS[i]["id"], sh[i]) for i in order)
    print("%-12s T%.0f° R%.0fmm pH%.1f wet%.0fm → %s | hit %d/%d" % (place, v["T"], v["R"], v["pH"], v["wet"], txt, h, len(exp)))
print(f"\nstaple-crop recall in top-6: {hits}/{tot} = {hits/tot:.0%}")
VALIDATION = {"staple_recall_top6": round(hits / tot, 3), "places": len(REF)}

# %% [markdown]
# ## 5 · Rotation and fertiliser rules
# * **Rotation multipliers** (applied to scores before percentages): same crop again ×0.45; same family ×0.55 (solanaceae, brassica ×0.4: shared soil diseases);
#   cereal after cereal ×0.8; legume after legume ×0.65; **legume after cereal/root ×1.25** (fixes nitrogen); **cereal after legume ×1.2**; root after legume ×1.1.
# * **Nutrient classes** (Mehlich-3-type thresholds used by extension services; **indicative**): K < 80 low, 80-150 medium, > 150 high mg/kg; P < 8 low, 8-20 medium, > 20 high mg/kg;
#   total N < 1 low, 1-2 medium, > 2 high g/kg; organic C < 10 low, 10-20 medium, > 20 high g/kg; pH < 5.2 acidic (lime), > 7.8 alkaline; CEC < 10 low.
# * **Fertiliser**: low N → urea/CAN (not for legumes); low P → DAP/TSP; low K → MOP; acid → agricultural lime; low organic C → compost/manure.
#   Indicative rates are given per class and marked *"confirm with your extension officer / a soil test"*.

# %%
FAMILIES = {"cereal": "cereal", "legume": "legume", "root": "root", "solanaceae": "solanaceae", "brassica": "brassica", "alliaceae": "alliaceae",
            "asteraceae": "asteraceae", "perennial": "perennial"}
def rotation_multiplier(prev, c):
    if prev is None: return 1.0
    p = next(x for x in CROPS if x["id"] == prev)
    if p["perennial"] or c["perennial"]: return 1.0
    if p["id"] == c["id"]: return 0.45
    if p["fam"] == c["fam"]:
        if c["fam"] in ("solanaceae", "brassica"): return 0.4
        if c["fam"] == "legume": return 0.65
        if c["fam"] == "cereal": return 0.8
        return 0.55
    if c["fam"] == "legume" and p["fam"] in ("cereal", "root", "solanaceae", "brassica", "alliaceae", "asteraceae"): return 1.25
    if c["fam"] == "cereal" and p["fam"] == "legume": return 1.2
    if c["fam"] == "root" and p["fam"] == "legume": return 1.1
    return 1.0

NUTRIENT_CLASSES = {"k": [80, 150], "p": [8, 20], "n": [1.0, 2.0], "oc": [10, 20], "cec": [10, 20]}
FERT = {  # nutrient → product & indicative rate by deficiency (kg/ha) – generic, to be confirmed locally
 "n": dict(product="urea", rate_low=[50, 100], note="split in 2 doses; skip for legumes"),
 "p": dict(product="dap", rate_low=[80, 150], note="at planting"),
 "k": dict(product="mop", rate_low=[40, 80], note="at planting or early growth"),
 "ph_low": dict(product="lime", rate_low=[1000, 2000], note="2-3 months before planting"),
 "oc": dict(product="compost", rate_low=[5000, 10000], note="manure/compost, every season"),
}
print("rotation example (maize last season, Kigali):")
sc, v = rank_at("eac", EAC, -1.95, 30.06)
for prev in (None, "maize", "bean"):
    m = [rotation_multiplier(prev, c) for c in CROPS]; sh = shares(sc, m); o = np.argsort(-sh)[:5]
    print("  last=%-6s →" % prev, ", ".join("%s %.0f%%" % (CROPS[i]["id"], sh[i]) for i in o))

# %% [markdown]
# ## 6 · Pack for the phone
# Each layer is stored as **uint8** (`value = q·scale + offset`, optionally `exp(·) − 1`), 255 = no data.
# Size: Africa 0.25° ≈ 0.8 MB, EAC 0.05° ≈ 1.5 MB. The app re-runs the same `suitability()` in TypeScript (parity-tested).

# %%
PACK = [  # key, source dict, name, lo, hi, log
    ("tmean", "clim", "tmean", -5, 35, False), ("tmin", "clim", "tmin", -10, 30, False), ("rain", "clim", "rain", 0, 3500, False),
    ("wet", "clim", "wet", 0, 12, False), ("ph", "soil", "ph", 3.0, 9.0, False), ("n", "soil", "n", 0, 6.0, False),
    ("p", "soil", "p", 0, 150.0, True), ("k", "soil", "k", 0, 1500.0, True), ("oc", "soil", "oc", 0, 80.0, True),
    ("cec", "soil", "cec", 0, 80.0, True), ("clay", "soil", "clay", 0, 100, False), ("sand", "soil", "sand", 0, 100, False)]
layers_meta = []
for key, src, name, lo, hi, log in PACK:
    f = (lambda v: np.log1p(v)) if log else (lambda v: v)
    flo, fhi = float(f(lo)), float(f(hi)); layers_meta.append(dict(key=key, offset=round(flo, 5), scale=round((fhi - flo) / 254, 7), log=log))

def pack(nm, g):
    soil_valid = np.isfinite(SOIL[nm]["ph"]) & np.isfinite(SOIL[nm]["k"]) & np.isfinite(CLIM[nm]["tmean"]) & np.isfinite(CLIM[nm]["rain"])
    arrs = []
    for (key, src, name, lo, hi, log), lm in zip(PACK, layers_meta):
        v = (SOIL if src == "soil" else CLIM)[nm][name]; v = np.log1p(np.maximum(v, 0)) if log else v
        q = np.clip(np.round((v - lm["offset"]) / lm["scale"]), 0, 254)
        arrs.append(np.where(soil_valid & np.isfinite(v), q, 255).astype("u1"))
    blob = np.stack(arrs).tobytes(); (OUT / f"land_{nm}.bin").write_bytes(blob)
    print(f"land_{nm}.bin {len(blob)/1e6:.2f} MB, usable cells {int(soil_valid.sum())} ({soil_valid.mean():.0%})")
    return dict(nrow=g["nrow"], ncol=g["ncol"], res=g["res"], lon0=g["lon0"], lat0=g["lat0"])

grids = {g["name"]: pack(g["name"], g) for g in (AFR, EAC)}
model = {"version": 1, "layers": layers_meta, "grids": grids, "crops": CROPS, "nutrient_classes": NUTRIENT_CLASSES, "fert": FERT,
         "ph_acid": 5.2, "ph_alkaline": 7.8, "share_top": 8, "share_floor": SHARE_FLOOR, "share_power": SHARE_POWER, "validation": VALIDATION,
         "source": "iSDAsoil Africa (CC-BY 4.0), WorldClim 2.1, CHIRPS v2; FAO EcoCrop-style requirements"}
(OUT / "land_model.json").write_text(json.dumps(model, ensure_ascii=False, separators=(",", ":")))
print("land_model.json", (OUT / "land_model.json").stat().st_size // 1024, "KB")

# reference values for the TypeScript parity tests
fx = []
for place, (lat, lon, _) in list(REF.items())[:8]:
    nm, g = ("eac", EAC) if (EAC["lon0"] < lon < EAC["lon0"] + EAC["ncol"] * EAC["res"] and EAC["lat0"] - EAC["nrow"] * EAC["res"] < lat < EAC["lat0"]) else ("africa", AFR)
    r, c = int((g["lat0"] - lat) / g["res"]), int((lon - g["lon0"]) / g["res"])
    q = [int(np.frombuffer((OUT / f"land_{nm}.bin").read_bytes(), "u1").reshape(len(PACK), g["nrow"], g["ncol"])[i, r, c]) for i in range(len(PACK))]
    fx.append(dict(place=place, grid=nm, lat=lat, lon=lon, q=q))
(OUT / "land_fixtures_src.json").write_text(json.dumps(fx))
