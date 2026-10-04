# %% [markdown]
# # 05 · Daily rain chance, offline (CHIRPS daily → wet/dry Markov model)
#
# **Question a farmer asks:** "Will it rain *today / tomorrow / this week* where my field is?"
#
# **Honest constraint:** a phone with no internet has no live weather feed, so it can never know *today's* sky.
# What it **can** know offline is (a) how rain behaves at that place in that month and (b) what the farmer tells it:
# *"did it rain today / yesterday?"*. Rain days come in spells, so today's weather is informative about the next days.
#
# **Model:** a **second-order wet/dry Markov chain per grid cell and calendar month**.
# `state = (rained yesterday?, rained today?)` → `P(rain tomorrow | state, month)`. Iterating the chain gives day +2 … +7.
# Estimates are **shrunk toward the neighbourhood** (beta prior) so dry cells with few wet days stay stable.
#
# **Evaluation:** train on 2011-2020, test on 2021-2025, **Brier skill score vs. the monthly climatological chance**
# for leads 1-7 days (skill > 0 ⇒ knowing "did it rain today?" really helps).
#
# Data: CHIRPS v2 **daily** (0.05°) via the IRI Data Library, which averages to 0.5° *on the server* (the CHC file server is throttled to ~100 KB/s,
# which would need ~14 GB for 15 years).
# A *wet day* = cell-mean rainfall ≥ 1 mm.

# %%
import os, io, gzip, json, time, urllib.request, warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import tifffile
from scipy import ndimage
warnings.filterwarnings("ignore")

ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
CACHE = OUT / "cache" / "daily"; CACHE.mkdir(parents=True, exist_ok=True)
Y0, Y1, TRAIN_END = int(os.environ.get("Y0", 2011)), int(os.environ.get("Y1", 2024)), int(os.environ.get("TRAIN_END", 2020))
K = 10  # 0.05° → 0.5°
WET_MM = 1.0

# %%
import datetime as dt, calendar
IRI = ("https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0/.daily-improved/.global/.0p05/.prcp/X/-20/55/RANGEEDGES/Y/-40/40/RANGEEDGES/"
       "T/({d0})/({d1})/RANGEEDGES/X/0.5/boxAverage/Y/0.5/boxAverage/data.nc")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch_month(ym):
    """One month of CHIRPS daily, averaged to 0.5° **on the IRI server** (3 MB instead of 80 MB), cached as .npy (north → south)."""
    y, m = ym; f = CACHE / f"{y}{m:02d}.npy"
    if f.exists(): return np.load(f)
    n = calendar.monthrange(y, m)[1]
    url = IRI.format(d0=f"1%20{MONTHS[m-1]}%20{y}", d1=f"{n}%20{MONTHS[m-1]}%20{y}")
    import netCDF4
    for attempt in range(5):
        try:
            tmp = CACHE / f"{y}{m:02d}.nc"
            with urllib.request.urlopen(url, timeout=240) as r, open(tmp, "wb") as fh: fh.write(r.read())
            with netCDF4.Dataset(tmp) as d:
                a = np.ma.filled(d.variables["prcp"][:], np.nan).astype("float32")[:, ::-1, :]   # Y ascending → flip to north-first
            tmp.unlink(); np.save(f, a); return a
        except Exception as e:
            if attempt == 4: print("failed", ym, type(e).__name__, flush=True); return np.full((n, 160, 150), np.nan, "float32")
            time.sleep(3 * (attempt + 1))


months = [(y, m) for y in range(Y0, Y1 + 1) for m in range(1, 13)]
t0 = time.time(); stack = []
with ThreadPoolExecutor(6) as ex:
    for i, a in enumerate(ex.map(fetch_month, months)):
        stack.append(a)
        if i % 12 == 0: print(f"{months[i]}  {i+1}/{len(months)} months  {time.time()-t0:.0f}s", flush=True)
days = [dt.date(y, m, d) for (y, m), a in zip(months, stack) for d in range(1, len(a) + 1)]
stack = np.concatenate(stack)
R = stack; print("daily stack", R.shape, "missing days:", int(np.isnan(R).all((1, 2)).sum()))
dates = np.array(days)
yr = np.array([d.year for d in days]); mo = np.array([d.month for d in days])

# %% [markdown]
# ## Data audit
# Wet-day frequency by month for a few places, to sanity-check against known climates
# (Kigali: two rainy seasons; Nairobi: long rains Mar-May, short rains Oct-Dec; Lagos-like coast: Jun peak).

# %%
base_geo = dict(lat0=40.0, lon0=-20.0, res=0.5, nrow=R.shape[1], ncol=R.shape[2])
def cell(lat, lon): return int((40 - lat) / 0.5), int((lon + 20) / 0.5)
for name, lat, lon in [("Kigali", -1.95, 30.06), ("Nairobi", -1.29, 36.82), ("Kano", 12.0, 8.52), ("Cape Town", -33.9, 18.4)]:
    r, c = cell(lat, lon); w = (R[:, r, c] >= WET_MM)
    print(f"{name:10s} wet-day freq by month:", " ".join(f"{w[mo == m].mean():.2f}" for m in range(1, 13)))
wetfrac = np.nanmean(R >= WET_MM, 0)
land = np.isfinite(R).mean(0) > 0.9
print("land cells:", int(land.sum()), "| mean wet-day frequency over land:", float(np.nanmean(wetfrac[land])).__round__(3))

# %% [markdown]
# ## Counting transitions & shrinkage
# For every cell and month: counts of `next day wet` given each of the 4 states, from the **training years only**.
# Counts are pooled with the 5×5 neighbourhood (weight 0.5) → the prior; posterior mean = (n_wet + a·prior) / (n + a), a = 20.

# %%
W = (R >= WET_MM).astype("int8"); valid = np.isfinite(R)
def transitions(sel_years):
    n = np.zeros((12, 4, R.shape[1], R.shape[2]), "float64"); k = n.copy()
    for t in range(2, len(days) - 1):
        if not (sel_years[0] <= yr[t] <= sel_years[1]): continue
        ok = valid[t - 2:t + 2].all(0)                # yesterday, today, tomorrow all observed
        s = (W[t - 1] * 2 + W[t]).astype(int)         # state 0..3
        m = mo[t] - 1
        for st in range(4):
            sel = ok & (s == st)
            n[m, st] += sel; k[m, st] += sel & (W[t + 1] == 1)
    return n, k

def posterior(n, k, a=20.0):
    sm = lambda x: ndimage.uniform_filter(np.nan_to_num(x), size=(1, 1, 5, 5), mode="nearest")
    prior = (sm(k) + 1e-3) / (sm(n) + 2e-3)
    return (k + a * prior) / (n + a)

t0 = time.time()
n_tr, k_tr = transitions((Y0, TRAIN_END)); P_tr = posterior(n_tr, k_tr)
print(f"transitions counted in {time.time()-t0:.0f}s; mean P(wet|wet,wet)={np.nanmean(P_tr[:,3][:, land]):.2f}  P(wet|dry,dry)={np.nanmean(P_tr[:,0][:, land]):.2f}")

# %% [markdown]
# ## Evaluation on 2021-2025 (never seen): Brier skill vs monthly climatology, leads 1-7
# Lead-L forecast = apply the 4-state chain L times starting from the observed (yesterday, today).
# Baseline = long-run chance of rain in that month at that cell (what you would know without asking "did it rain today?").

# %%
def trans_matrix(P):          # P: (4, r, c) = P(wet tomorrow | state)  → T[(s)->(s')]
    T = np.zeros((4, 4) + P.shape[1:], "float32")
    for s in range(4):
        wprev, wtoday = divmod(s, 2)
        nxt_wet = wtoday * 2 + 1; nxt_dry = wtoday * 2 + 0
        T[s, nxt_wet] = P[s]; T[s, nxt_dry] = 1 - P[s]
    return T

clim = np.zeros((12,) + R.shape[1:], "float32")
for m in range(12):
    sel = (mo == m + 1) & (yr <= TRAIN_END)
    clim[m] = np.nanmean(W[sel].astype("float32") * np.where(valid[sel], 1, np.nan), 0)

LEADS = 7
bs_model = np.zeros(LEADS); bs_clim = np.zeros(LEADS); cnt = np.zeros(LEADS)
bs_model_m = np.zeros((LEADS, 12)); bs_clim_m = np.zeros((LEADS, 12)); cnt_m = np.zeros((LEADS, 12))
land_idx = np.nonzero(land)
test_t = [t for t in range(2, len(days) - LEADS - 1) if yr[t] > TRAIN_END and valid[t - 1:t + LEADS + 1][:, land].all()]
for t in test_t[::2]:                                     # every 2nd day → faster, still ~900 days
    m = mo[t] - 1
    Tm = trans_matrix(P_tr[m][:, land])                   # (4,4,N)
    s0 = (W[t - 1][land] * 2 + W[t][land]).astype(int)
    dist = np.zeros((4, s0.size), "float32"); dist[s0, np.arange(s0.size)] = 1
    for L in range(1, LEADS + 1):
        dist = np.einsum("an,abn->bn", dist, Tm)
        p_wet = dist[1] + dist[3]                         # P(today' = wet) = states with last digit 1
        y = W[t + L][land]; mm = mo[t + L] - 1
        pc = clim[mm][land]
        b1 = ((p_wet - y) ** 2).mean(); b0 = ((pc - y) ** 2).mean()
        bs_model[L - 1] += b1; bs_clim[L - 1] += b0; cnt[L - 1] += 1
        bs_model_m[L - 1, m] += b1; bs_clim_m[L - 1, m] += b0; cnt_m[L - 1, m] += 1
bss = 1 - bs_model / bs_clim
print("Brier skill score vs monthly climatology (test 2021-25):")
for L in range(LEADS): print(f"  +{L+1} day: BSS = {bss[L]:+.3f}   (Brier model {bs_model[L]/cnt[L]:.4f} vs clim {bs_clim[L]/cnt[L]:.4f})")
bss_m = 1 - bs_model_m / np.maximum(bs_clim_m, 1e-9)
print("lead-1 BSS by month:", " ".join(f"{v:+.2f}" for v in bss_m[0]))

# %% [markdown]
# **Reading the result.** Skill is clearly positive tomorrow and decays within ~3-5 days as the chain forgets
# the starting state – exactly what physics says. Beyond that the app honestly shows only the climatological chance.
# We also verify the probabilities are **calibrated** (reliability, below), otherwise "70 % chance" would mislead.

# %%
rel_p, rel_o = [], []
for t in test_t[::6]:
    m = mo[t] - 1; Tm = trans_matrix(P_tr[m][:, land])
    s0 = (W[t - 1][land] * 2 + W[t][land]).astype(int)
    dist = np.zeros((4, s0.size), "float32"); dist[s0, np.arange(s0.size)] = 1
    dist = np.einsum("an,abn->bn", dist, Tm)
    rel_p.append(dist[1] + dist[3]); rel_o.append(W[t + 1][land])
rel_p, rel_o = np.concatenate(rel_p), np.concatenate(rel_o)
bins = np.linspace(0, 1, 11); bi = np.digitize(rel_p, bins) - 1
print("reliability (+1 day): forecast → observed (n)")
rel_table = []
for b in range(10):
    s = bi == b
    if s.sum() > 2000:
        rel_table.append((float(rel_p[s].mean()), float(rel_o[s].mean()))); print(f"  {rel_p[s].mean():.2f} → {rel_o[s].mean():.2f}  ({int(s.sum())})")
gap = float(np.mean([abs(a - b) for a, b in rel_table]))
print("mean reliability gap:", round(gap, 3))

# %% [markdown]
# ## Final model (all years) and export
# `rain_daily.bin` layout (little-endian, uint8): `p[12,4,nrow,ncol]` (P(rain tomorrow | state), ×255), `clim[12,nrow,ncol]`
# (monthly wet-day chance ×255), `amt[12,nrow,ncol]` (mean mm on wet days ×4). Nodata = 255 in `clim`.

# %%
n_all, k_all = transitions((Y0, Y1)); P_all = posterior(n_all, k_all)
clim_all = np.zeros_like(clim); amt = np.zeros_like(clim)
for m in range(12):
    sel = mo == m + 1
    clim_all[m] = np.nanmean(W[sel].astype("float32") * np.where(valid[sel], 1, np.nan), 0)
    Rm = np.where(R[sel] >= WET_MM, R[sel], np.nan)
    amt[m] = np.nan_to_num(np.nanmean(Rm, 0), nan=0)
p_u8 = np.where(land[None, None], np.clip(np.round(P_all * 255), 0, 254), 255).astype("u1")
clim_u8 = np.where(land[None], np.clip(np.round(clim_all * 255), 0, 254), 255).astype("u1")
amt_u8 = np.where(land[None], np.clip(np.round(amt * 4), 0, 254), 255).astype("u1")
blob = p_u8.tobytes() + clim_u8.tobytes() + amt_u8.tobytes()
(OUT / "rain_daily.bin").write_bytes(blob)
meta = {"version": 1, "nrow": R.shape[1], "ncol": R.shape[2], "res": 0.5, "lon0": -20.0, "lat0": 40.0, "wet_mm": WET_MM, "nodata": 255,
        "years": [Y0, Y1], "layout": [["p", "u8", [12, 4, R.shape[1], R.shape[2]]], ["clim", "u8", [12, R.shape[1], R.shape[2]]], ["amt", "u8", [12, R.shape[1], R.shape[2]], 4]],
        "eval": {"test_years": [TRAIN_END + 1, Y1], "brier_skill_by_lead": [round(float(x), 4) for x in bss],
                 "reliability_gap_lead1": round(gap, 4)}}
(OUT / "rain_daily.json").write_text(json.dumps(meta, separators=(",", ":")))
print(f"rain_daily.bin {len(blob)/1e6:.2f} MB")

# parity reference for the app tests: P(rain) for 7 days at a few places starting from (dry,wet) and (wet,wet) in July
for name, lat, lon in [("Kigali", -1.95, 30.06), ("Nairobi", -1.29, 36.82), ("Kano", 12.0, 8.52)]:
    r, c = cell(lat, lon)
    m = 3
    out = []
    for s0 in (0, 3):
        d = np.zeros(4); d[s0] = 1; Tm = trans_matrix(np.round(P_all[m][:, r, c] * 255)[:, None, None] / 255)[:, :, 0, 0]
        row = []
        for L in range(7):
            d = d @ Tm; row.append(round(float(d[1] + d[3]), 4))
        out.append(row)
    print(name, "April, start dry-dry →", out[0], "| wet-wet →", out[1])
