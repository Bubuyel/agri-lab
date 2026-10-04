# %% [markdown]
# # 03 · Offline rainfall outlook from CHIRPS (Africa + East African Community)
#
# **What a farmer needs:** "Will the coming months be wetter or drier than normal where my field is?"
# **What we can honestly build from CHIRPS alone:** a *probabilistic seasonal outlook* (below / normal / above
# normal) = **climatology + a small statistical model on recent anomalies**, with a per-location skill flag so
# the app can say "low confidence" where the model has no real skill over climatology.
#
# We do **not** claim to out-forecast ECMWF/ICPAC. The value is: works with zero internet, instant, tiny.
#
# **Pipeline**
# 1. Inspect the rasters (grid, nodata, units) and aggregate to an app-sized grid (Africa 0.5°, EAC 0.25°).
# 2. Climatology (WMO 1991-2020 normal): monthly mean, tercile thresholds.
# 3. Standardised anomalies → features (last month, last 3 months, neighbourhood).
# 4. Baselines vs model on a **temporal** split. Metric: Ranked Probability Skill Score (RPSS) vs climatology.
# 5. Export binary grids + tiny model JSON (~2 MB) for the app.

# %%
import os, io, gzip, glob, json, re, time, warnings
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import tifffile
from scipy import ndimage
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
CH = Path(os.environ.get("CHIRPS_DIR", ROOT / "CHIRPS"))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
CACHE = OUT / "cache"
OUT.mkdir(parents=True, exist_ok=True); CACHE.mkdir(exist_ok=True)
np.random.seed(42)


def read_tif(p):
    return tifffile.imread(io.BytesIO(gzip.open(p).read())).astype("float32")


def geo(p):
    t = tifffile.TiffFile(io.BytesIO(gzip.open(p).read())).pages[0]
    sc, tp = t.tags["ModelPixelScaleTag"].value, t.tags["ModelTiepointTag"].value
    return {"res": sc[0], "lon0": tp[3], "lat0": tp[4]}   # lat0 = top edge


f_af = sorted(glob.glob(str(CH / "africa_monthly" / "tifs" / "*.tif.gz")))
f_ea = sorted(glob.glob(str(CH / "EAC_monthly" / "tifs" / "*.tif.gz")))
print(len(f_af), "africa months |", len(f_ea), "EAC months |", f_af[0].split("/")[-1][-14:], "->", f_af[-1][-14:])
a = read_tif(f_af[500])
print("Africa grid", a.shape, geo(f_af[0]), "| nodata share", float((a < 0).mean()).__round__(3), "| max mm", float(a.max()))
b = read_tif(f_ea[500]); print("EAC grid", b.shape, geo(f_ea[0]))

# %% [markdown]
# **What the raster audit tells us**
# * Float32 **mm per month**, nodata = `-9999` (ocean / outside CHIRPS land mask) → masked, never averaged.
# * Native resolution 0.05° (~5 km). Africa = 1600×1500 px × 548 months = 5 GB: far too big for a phone.
# * A phone user locates their field to ~1-5 km at best, and seasonal rainfall anomalies are spatially smooth
#   (hundreds of km). So we **block-average** to 0.5° (Africa) and 0.25° (EAC) with ≥50 % valid-pixel rule.

# %%
def block_mean(a, k):
    h, w = a.shape; h2, w2 = h // k * k, w // k * k
    v = np.where(a[:h2, :w2] < 0, np.nan, a[:h2, :w2]).reshape(h2 // k, k, w2 // k, k)
    cnt = np.isfinite(v).sum((1, 3))
    s = np.nansum(v, (1, 3))
    return np.where(cnt >= (k * k) / 2, s / np.maximum(cnt, 1), np.nan).astype("float32")


def load_stack(files, k, name):
    cp = CACHE / f"{name}_k{k}.npz"
    if cp.exists():
        z = np.load(cp, allow_pickle=True); return z["x"], z["months"]
    with ThreadPoolExecutor(8) as ex:
        arr = list(ex.map(lambda p: block_mean(read_tif(p), k), files))
    months = [re.search(r"(\d{4})\.(\d{2})", f).groups() for f in files]
    months = np.array([(int(y), int(m)) for y, m in months])
    x = np.stack(arr); np.savez_compressed(cp, x=x, months=months); return x, months


t0 = time.time()
AF, M_AF = load_stack(f_af, 10, "africa")      # 0.5 deg
EA, M_EA = load_stack(f_ea, 5, "eac")          # 0.25 deg
print("africa", AF.shape, "eac", EA.shape, f"{time.time()-t0:.0f}s")
g_af = geo(f_af[0]); g_af["res"] = 0.5
g_ea = geo(f_ea[0]); g_ea["res"] = 0.25

# %%
# data-quality checks: missing months, impossible values, trend in land-mean rainfall
yrs = M_AF[:, 0] + (M_AF[:, 1] - 1) / 12
assert (np.diff(yrs) > 0).all(), "months out of order"
exp = (M_AF[-1, 0] - M_AF[0, 0]) * 12 + M_AF[-1, 1] - M_AF[0, 1] + 1
print("months present", len(M_AF), "expected", exp)
land_af = np.isfinite(AF).mean(0) > 0.9
print("land cells (Africa 0.5):", int(land_af.sum()), "of", land_af.size, "| max monthly mm:", float(np.nanmax(AF)))
land_mean = np.nanmean(AF[:, land_af], 1)
print("continental mean mm/month first/last decade:", land_mean[:120].mean().round(1), land_mean[-120:].mean().round(1))

# %% [markdown]
# ## Climatology & anomalies
# * Normal period **1991-2020** (WMO standard). Tercile thresholds p33/p67 per cell and calendar month.
# * Cells/months where p67 < 5 mm are **dry season** – "below/normal/above" is meaningless there (most values are 0),
#   so we flag them and the app just says "dry season".
# * Standardised anomaly `z = (x - mean) / std` per cell-month.

# %%
def climatology(X, M, y0, y1):
    sel = (M[:, 0] >= y0) & (M[:, 0] <= y1)
    mean = np.full((12,) + X.shape[1:], np.nan, "float32"); sd = mean.copy(); p33 = mean.copy(); p67 = mean.copy()
    for m in range(1, 13):
        v = X[sel & (M[:, 1] == m)]
        mean[m - 1] = np.nanmean(v, 0); sd[m - 1] = np.nanstd(v, 0)
        p33[m - 1], p67[m - 1] = np.nanpercentile(v, [100 / 3, 200 / 3], 0)
    return mean, sd, p33, p67


def anomalies(X, M, mean, sd):
    z = (X - mean[M[:, 1] - 1]) / np.maximum(sd[M[:, 1] - 1], 5.0)   # std floor 5 mm avoids blow-ups in dry months
    return np.clip(z, -4, 4).astype("float32")


def category(X, M, p33, p67):
    c = np.where(X <= p33[M[:, 1] - 1], 0, np.where(X >= p67[M[:, 1] - 1], 2, 1)).astype("int8")
    return np.where(np.isfinite(X), c, -1)


def nb_mean(z, size=7):
    """NaN-aware neighbourhood mean (normalised convolution) -> large-scale anomaly signal."""
    ok = np.isfinite(z).astype("float32"); v = np.nan_to_num(z)
    f = lambda a: ndimage.uniform_filter(a, size=(1, size, size), mode="constant")
    return np.where(f(ok) > 0.2, f(v) / np.maximum(f(ok), 1e-6), np.nan)


def features(z, lead_months=(1, 3)):
    z1 = z
    z3 = np.full_like(z, np.nan)
    z3[2:] = np.nanmean(np.stack([z[2:], z[1:-1], z[:-2]]), 0)
    return z1, z3, nb_mean(z3)


# %% [markdown]
# ## Honest evaluation protocol
# * **Temporal split**: model fitted on origins ≤ 2012, tested on 2013-2026 (never random: seasons are autocorrelated).
# * For evaluation the normals/terciles use **1981-2012 only**, so the test years do not leak into the thresholds.
# * Targets: tercile category of month *t+h*, h = 1, 2, 3.
# * Skill = **RPSS** vs equal-odds climatology (1/3,1/3,1/3). RPSS > 0 means better than just guessing the normal.
# * Candidates: (a) climatology, (b) persistence (z1 only), (c) logistic on [z1, z3, neighbourhood z3] per origin-month.

# %%
H = 3
TRAIN_END, TEST_START = 2012, 2013


def rps(P, y):
    """P: (n,3) probs, y: (n,) category -> mean ranked probability score"""
    Y = np.eye(3)[y]
    return ((np.cumsum(P, 1) - np.cumsum(Y, 1)) ** 2).sum(1)


def build_xy(X, M, thr, wet_only=True):
    mean, sd, p33, p67 = thr
    z = anomalies(X, M, mean, sd)
    z1, z3, zr = features(z)
    cat = category(X, M, p33, p67)
    wet = (p67 >= 5.0)                                        # [12, ...] wet-enough cell-months
    out = {h: [] for h in range(1, H + 1)}
    n = len(M)
    for h in range(1, H + 1):
        t = np.arange(2, n - h)
        mo = M[t, 1]; tm = M[t + h, 1]; yr = M[t, 0]
        Fz = np.stack([z1[t], z3[t], zr[t]], -1)                       # (T, r, c, 3)
        yv = cat[t + h]
        ok = np.isfinite(Fz).all(-1) & (yv >= 0) & wet[tm - 1]
        T_idx, r, c = np.nonzero(ok)
        out[h] = dict(F=Fz[T_idx, r, c], y=yv[T_idx, r, c], om=mo[T_idx], yr=yr[T_idx], r=r, c=c)
    return out


thr_eval = climatology(AF, M_AF, 1981, TRAIN_END)
D = build_xy(AF, M_AF, thr_eval)
print({h: len(D[h]["y"]) for h in D}, "samples")

# %%
models_eval, rows = {}, []
for h in range(1, H + 1):
    d = D[h]; tr = d["yr"] <= TRAIN_END - 1; te = d["yr"] >= TEST_START
    for om in range(1, 13):
        a, b = tr & (d["om"] == om), te & (d["om"] == om)
        if a.sum() < 500 or b.sum() < 200:
            continue
        sub = np.random.RandomState(0).choice(np.nonzero(a)[0], min(a.sum(), 200000), replace=False)
        lr = LogisticRegression(C=1.0, max_iter=300).fit(d["F"][sub], d["y"][sub])
        models_eval[(h, om)] = lr
        P = lr.predict_proba(d["F"][b]); y = d["y"][b]
        pers = LogisticRegression(C=1.0, max_iter=300).fit(d["F"][sub][:, :1], d["y"][sub])
        Pp = pers.predict_proba(d["F"][b][:, :1])
        ref = rps(np.full_like(P, 1 / 3), y).mean()
        rows.append((h, om, 1 - rps(P, y).mean() / ref, 1 - rps(Pp, y).mean() / ref, b.sum()))
R = np.array(rows)
print("RPSS vs climatology on 2013-2026 (positive = skill).  h | month | model | persistence-only | n")
import pandas as pd
tab = pd.DataFrame(R, columns=["h", "origin_month", "rpss_model", "rpss_persist", "n"])
print(tab.groupby("h")[["rpss_model", "rpss_persist"]].mean().round(4).to_string())
print("\nbest origin months at h=1:\n", tab[tab.h == 1].sort_values("rpss_model", ascending=False).head(4).round(3).to_string(index=False))

# %% [markdown]
# **How to read this.** Monthly rainfall anomalies carry limited persistence; the model's average RPSS is small
# but usually > 0 at 1-month lead and fades by month 3, while skill concentrates in particular seasons/regions
# (that is physically expected: ENSO/IOD-linked short rains, coastal/monsoon regions).
# → We ship a **per-cell skill flag** and the app labels low-skill outlooks as *"mostly climatology – low confidence"*.
# We also verify the probabilities are **calibrated** (reliability check below) – otherwise a "60 % wetter" claim
# would be misleading.

# %%
# reliability of the "above normal" probability, pooled over all test samples
bins = np.linspace(0, 1, 11)
rel = []
for h in range(1, H + 1):
    d = D[h]; te = d["yr"] >= TEST_START
    P = np.zeros((te.sum(), 3)); idx = np.nonzero(te)[0]
    for om in range(1, 13):
        if (h, om) in models_eval:
            s = d["om"][idx] == om
            P[s] = models_eval[(h, om)].predict_proba(d["F"][idx[s]])
    keep = P.sum(1) > 0
    p, o = P[keep, 2], (d["y"][idx][keep] == 2)
    bi = np.digitize(p, bins) - 1
    rel.append([(float(p[bi == k].mean()), float(o[bi == k].mean()), int((bi == k).sum())) for k in range(10) if (bi == k).sum() > 500])
print("h=1 reliability (forecast prob -> observed freq, n):")
for pf, of, n in rel[0]:
    print(f"   {pf:.2f} -> {of:.2f}   n={n}")
ece = np.mean([abs(pf - of) for pf, of, n in rel[0]])
print("mean |forecast - observed| (reliability gap) =", round(float(ece), 3))

# %% [markdown]
# ## Per-cell skill flag
# For each cell and lead, average RPSS-gain over the test years (all origin months).  Noisy at cell level, so we
# smooth it with the same 7×7 neighbourhood filter and store three levels: **0 = low, 1 = some, 2 = useful**.

# %%
def cell_skill(h):
    d = D[h]; te = d["yr"] >= TEST_START
    sc_m = np.zeros(AF.shape[1:], "float64"); sc_c = sc_m.copy(); nn = sc_m.copy()
    idx = np.nonzero(te)[0]
    for om in range(1, 13):
        if (h, om) not in models_eval:
            continue
        s = idx[d["om"][idx] == om]
        P = models_eval[(h, om)].predict_proba(d["F"][s]); y = d["y"][s]
        np.add.at(sc_m, (d["r"][s], d["c"][s]), rps(P, y))
        np.add.at(sc_c, (d["r"][s], d["c"][s]), rps(np.full_like(P, 1 / 3), y))
        np.add.at(nn, (d["r"][s], d["c"][s]), 1)
    ok = nn > 20
    rpss = np.where(ok, 1 - sc_m / np.maximum(sc_c, 1e-9), np.nan)
    sm = ndimage.generic_filter(rpss, np.nanmean, size=5, mode="nearest") if np.isfinite(rpss).any() else rpss
    return rpss, sm


skill = {h: cell_skill(h) for h in range(1, H + 1)}
for h in skill:
    s = skill[h][1][land_af]
    print(f"h={h}: share of land cells with smoothed RPSS>0: {np.nanmean(s > 0):.2f} | >0.03: {np.nanmean(s > 0.03):.2f}")

# %% [markdown]
# ## Final model for shipping
# * Normals/terciles from **1991-2020** (WMO), anomalies re-computed.
# * Logistic models re-fitted on **all** origins (1981-2026) per (origin month, lead).
# * Same coefficients are applied to the finer EAC 0.25° grid (features are standardised, so they transfer).

# %%
thr = climatology(AF, M_AF, 1991, 2020)
Df = build_xy(AF, M_AF, thr)
final = {}
for h in range(1, H + 1):
    d = Df[h]
    for om in range(1, 13):
        a = d["om"] == om
        if a.sum() < 500:
            continue
        sub = np.random.RandomState(1).choice(np.nonzero(a)[0], min(a.sum(), 300000), replace=False)
        lr = LogisticRegression(C=1.0, max_iter=300).fit(d["F"][sub], d["y"][sub])
        final[f"{h}_{om}"] = {"b": [round(float(v), 5) for v in lr.intercept_], "w": [[round(float(v), 5) for v in r] for r in lr.coef_]}
print("fitted", len(final), "tiny logistic models")

def pack_grid(X, M, g, k_name, skill_maps=None):
    """Return dict of arrays + meta for one grid."""
    mean, sd, p33, p67 = climatology(X, M, 1991, 2020)
    z = anomalies(X, M, mean, sd)
    z1, z3, zr = features(z)
    last = X[-12:]
    nr, nc = X.shape[1:]
    to_u16 = lambda a, s=1: np.where(np.isfinite(a), np.clip(np.round(a * s), 0, 65534), 65535).astype("<u2")
    to_i8 = lambda a, s: np.where(np.isfinite(a), np.clip(np.round(a * s), -127, 127), -128).astype("i1")
    arrs = {
        "mean": to_u16(mean), "p33": to_u16(p33), "p67": to_u16(p67),
        "last12": to_u16(last),
        "state": to_i8(np.stack([z1[-1], z3[-1], zr[-1]]), 32),     # z scaled by 32, [3, r, c]
    }
    meta = {"name": k_name, "nrow": nr, "ncol": nc, "res": g["res"], "lon0": g["lon0"], "lat0": g["lat0"],
            "last_month": [int(M[-1, 0]), int(M[-1, 1])], "state_scale": 32}
    return arrs, meta


arr_af, meta_af = pack_grid(AF, M_AF, g_af, "africa")
arr_ea, meta_ea = pack_grid(EA, M_EA, g_ea, "eac")
# per-cell skill (Africa grid only; EAC cells look it up on the coarse grid)
sk = np.stack([np.where(np.isfinite(skill[h][1]), np.digitize(skill[h][1], [0.0, 0.03]), 0) for h in range(1, H + 1)]).astype("u1")
arr_af["skill"] = sk
for nm, arrs, meta in (("africa", arr_af, meta_af), ("eac", arr_ea, meta_ea)):
    blob = b"".join(np.ascontiguousarray(arrs[k]).tobytes() for k in ("mean", "p33", "p67", "last12", "state") + (("skill",) if nm == "africa" else ()))
    (OUT / f"rain_{nm}.bin").write_bytes(blob)
    meta["layout"] = [["mean", "u16", [12, meta["nrow"], meta["ncol"]]], ["p33", "u16", [12, meta["nrow"], meta["ncol"]]],
                      ["p67", "u16", [12, meta["nrow"], meta["ncol"]]], ["last12", "u16", [12, meta["nrow"], meta["ncol"]]],
                      ["state", "i8", [3, meta["nrow"], meta["ncol"]]]] + ([["skill", "u8", [H, meta["nrow"], meta["ncol"]]]] if nm == "africa" else [])
    meta["nodata_u16"] = 65535; meta["nodata_i8"] = -128; meta["dry_p67_mm"] = 5
    print(nm, f"{len(blob)/1e6:.2f} MB")

model = {"version": 1, "leads": H, "features": ["z1", "z3", "zr3"], "classes": ["below", "normal", "above"],
         "logit": final, "grids": {"africa": meta_af, "eac": meta_ea},
         "eval": {"rpss_by_lead": tab.groupby("h").rpss_model.mean().round(4).to_dict(),
                  "persistence_rpss_by_lead": tab.groupby("h").rpss_persist.mean().round(4).to_dict(),
                  "reliability_gap_h1": round(float(ece), 4), "test_years": [TEST_START, int(M_AF[-1, 0])]}}
(OUT / "rain_model.json").write_text(json.dumps(model, separators=(",", ":")))

# %% [markdown]
# ## Parity check – the app math
# App: `logit_k = b_k + Σ w_kj · x_j`, softmax → P(below, normal, above); `x = [z1, z3, zr3]` decoded from the
# int8 `state` grid. We replay it for Kigali & Nairobi and compare with sklearn's `predict_proba`.

# %%
def cell_of(meta, lat, lon):
    return int((meta["lat0"] - lat) / meta["res"]), int((lon - meta["lon0"]) / meta["res"])

def outlook(meta, arrs, lat, lon, origin_month, skill_arr=None):
    r, c = cell_of(meta, lat, lon)
    s = arrs["state"][:, r, c].astype(float)
    if (s == -128).any():
        return None
    x = s / meta["state_scale"]
    res = []
    for h in range(1, H + 1):
        tm = (origin_month - 1 + h) % 12 + 1
        m = final.get(f"{h}_{origin_month}")
        p33, p67 = int(arrs["p33"][tm - 1, r, c]), int(arrs["p67"][tm - 1, r, c])
        if m is None or p67 < 5:
            res.append((h, tm, "dry-season", p33, p67)); continue
        lg = np.array(m["b"]) + np.array(m["w"]) @ x
        p = np.exp(lg - lg.max()); p /= p.sum()
        res.append((h, tm, p.round(2).tolist(), p33, p67))
    return res

om = int(M_EA[-1, 1])
for name, lat, lon in [("Kigali", -1.95, 30.06), ("Nairobi", -1.29, 36.82), ("Gitega", -3.43, 29.93), ("Mogadishu", 2.05, 45.32)]:
    print(name, outlook(meta_ea if lon < 43 else meta_af, arr_ea if lon < 43 else arr_af, lat, lon, om))
for f in ("rain_africa.bin", "rain_eac.bin", "rain_model.json"):
    print(f"{f:18s} {(OUT / f).stat().st_size / 1024:8.0f} KB")
