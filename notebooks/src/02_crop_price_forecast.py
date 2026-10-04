# %% [markdown]
# # 02 · Crop price forecasting (WFP food prices + FAOSTAT)
#
# **Goal:** a model small enough to ship *inside* a phone app (no internet) that tells a farmer
# what a crop is likely to sell for in the next 1-6 months, where nearby markets pay most, and
# what that is in their own currency.
#
# **Pipeline**
# 1. Audit the CSV schema/types (what is in each column, what is dirty).
# 2. Clean: fix mis-dated rows, normalise units to per-kg / per-litre, drop outliers.
# 3. Build **national monthly price series** per (country, commodity).
# 4. Backtest candidate models on a strict *time* split (never random splits for time series):
#    naive, seasonal, pooled Ridge, pooled LightGBM.
# 5. Pick the model by *accuracy per byte*, calibrate prediction intervals, export to JSON.
# 6. Export nearby-market price table + implied FX rates for offline conversion.
# 7. FAOSTAT: production-value and export-destination insights per country/crop.
#
# Runs on a laptop (CPU, ~5 min) or Colab. Outputs go to `artifacts/` and are copied to the app.

# %%
import os, re, glob, json, math, warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
pd.set_option("display.width", 200, "display.max_columns", 30)

# ---- paths (override with env vars on Colab / Kaggle) -------------------------------------------
ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
WFP_DIR = Path(os.environ.get("WFP_DIR", ROOT / "WFP Independent price"))
FAO_DIR = Path(os.environ.get("FAO_DIR", ROOT / "FAOSTAT_T-Z_E"))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
OUT.mkdir(parents=True, exist_ok=True)
SEED = 42
np.random.seed(SEED)
print("WFP:", WFP_DIR, WFP_DIR.exists(), "| FAO:", FAO_DIR, FAO_DIR.exists(), "| OUT:", OUT)

# %% [markdown]
# ## 1 · Read the CSV header, column types and quality
# One file per year + `commodities`, `currencies`, `markets` lookup tables.
# The `wfp_food_prices_global_1900.csv` file is suspicious (named 1900) – we check it explicitly.

# %%
files = sorted(glob.glob(str(WFP_DIR / "wfp_food_prices_global_*.csv")))
raw = pd.concat([pd.read_csv(f, low_memory=False) for f in files], ignore_index=True)
raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
print(raw.shape)
print(raw.dtypes.to_string())
print("\nnull share per column:\n", (raw.isna().mean().round(3)).to_string())
print("\ndate range:", raw.date.min(), "->", raw.date.max())
print("countries:", raw.countryiso3.nunique(), "| commodities:", raw.commodity.nunique(), "| markets:", raw.market_id.nunique())
print("\npricetype:\n", raw.pricetype.value_counts().to_string())
print("\npriceflag:\n", raw.priceflag.value_counts().to_string())
print("\nrows dated before 1995:", int((raw.date < "1995").sum()), "(by country:", raw[raw.date < "1995"].countryiso3.value_counts().head(4).to_dict(), ")")

# %% [markdown]
# **Findings that drive the design**
# * `price` is in **local currency**, `usdprice` in USD → we can model local price (what the farmer sees)
#   and *derive* an offline FX rate per currency as `price / usdprice`.
# * `unit` is messy (`KG`, `100 KG`, `L`, `Head`, `10 pcs`…) → normalise to **per kg / per litre** or drop.
# * `pricetype` is mostly Retail; `priceflag = aggregate` rows are interpolated/aggregated by WFP.
# * The `1900` file holds a few mis-dated rows → dropped (we keep ≥ 1995).

# %%
FOOD_CATS = {"cereals and tubers", "vegetables and fruits", "pulses and nuts", "oil and fats",
             "meat, fish and eggs", "milk and dairy", "miscellaneous food"}
UNIT_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)?\s*(kg|g|l|ml|pound|gallon)\s*$", re.I)
TO_BASE = {"kg": ("kg", 1.0), "g": ("kg", 0.001), "pound": ("kg", 0.45359237),
           "l": ("l", 1.0), "ml": ("l", 0.001), "gallon": ("l", 3.78541)}


def unit_factor(u: str):
    """'100 KG' -> ('kg', 100.0);  'Head' -> (None, None)."""
    m = UNIT_RE.match(str(u))
    if not m:
        return (None, None)
    qty = float(m.group(1) or 1.0)
    base, mult = TO_BASE[m.group(2).lower()]
    return base, qty * mult


uf = {u: unit_factor(u) for u in raw.unit.unique()}
df = raw.copy()
df["base"] = df.unit.map(lambda u: uf[u][0])
df["qty"] = df.unit.map(lambda u: uf[u][1])

n0 = len(df)
df = df[(df.date >= "1995-01-01") & df.category.isin(FOOD_CATS)]
df = df[df.base.notna() & (df.price > 0) & (df.usdprice > 0)]
df = df[df.commodity.str.lower() != "exchange rate"]
df["p_loc"] = df.price / df.qty          # local currency per kg|l
df["p_usd"] = df.usdprice / df.qty
print(f"kept {len(df):,} of {n0:,} rows after date/unit/food filters")

# per (market, commodity) outlier guard: reject points >4x or <0.25x of the rolling median of neighbours
df = df.sort_values(["market_id", "commodity_id", "base", "pricetype", "date"])
g = df.groupby(["market_id", "commodity_id", "base", "pricetype"], sort=False)["p_loc"]
med = g.transform(lambda s: s.rolling(7, center=True, min_periods=3).median())
ratio = (df.p_loc / med).fillna(1.0)
bad = (ratio > 4) | (ratio < 0.25)
print("outliers removed:", int(bad.sum()))
df = df[~bad].copy()
df["month"] = df.date.dt.to_period("M").dt.to_timestamp()

# %% [markdown]
# ## 2 · National monthly series
# We prefer **Retail** prices (what consumers/traders see); fall back to Wholesale only when no retail exists.
# A series = (country, commodity, base-unit) → monthly **median across markets**.

# %%
df["pt_rank"] = df.pricetype.map({"Retail": 0, "Wholesale": 1}).fillna(2)
best_pt = df.groupby(["countryiso3", "commodity", "base"]).pt_rank.transform("min")
df = df[df.pt_rank == best_pt]

series = (df.groupby(["countryiso3", "commodity", "base", "currency", "month"])
            .agg(p_loc=("p_loc", "median"), p_usd=("p_usd", "median"), n_mk=("market_id", "nunique"))
            .reset_index())
# a series should have ONE currency; keep the most recent one
last_cur = series.sort_values("month").groupby(["countryiso3", "commodity", "base"]).currency.last()
series = series.merge(last_cur.rename("cur_last").reset_index(), on=["countryiso3", "commodity", "base"])
series = series[series.currency == series.cur_last].drop(columns="cur_last")
DATA_END = series.month.max()
print("data ends:", DATA_END.date(), "| raw national series:", series.groupby(["countryiso3", "commodity", "base"]).ngroups)

# %%
MIN_OBS, MAX_STALE_M, MAX_GAP = 36, 9, 4


def to_monthly(s: pd.DataFrame) -> pd.DataFrame:
    """Reindex to a complete monthly grid and interpolate gaps <= MAX_GAP months (in log space)."""
    idx = pd.date_range(s.month.min(), s.month.max(), freq="MS")
    s = s.set_index("month").reindex(idx)
    s["observed"] = s.p_loc.notna()
    for c in ("p_loc", "p_usd"):
        s[c] = np.exp(np.log(s[c]).interpolate(limit=MAX_GAP, limit_area="inside"))
    return s


keep = {}
for key, s in series.groupby(["countryiso3", "commodity", "base"]):
    m = to_monthly(s)
    ok = m.p_loc.notna()
    if ok.sum() < MIN_OBS:
        continue
    if (DATA_END.to_period("M") - m.index[-1].to_period("M")).n > MAX_STALE_M:
        continue
    # trailing continuous stretch only (so lags are always valid)
    last_na = np.where(~ok.values)[0]
    start = (last_na[-1] + 1) if len(last_na) else 0
    m = m.iloc[start:]
    if len(m) >= MIN_OBS:
        m["currency"] = s.currency.iloc[-1]
        keep[key] = m
print(f"usable series (>= {MIN_OBS} continuous months, fresh within {MAX_STALE_M} m): {len(keep)}")
print(pd.Series([k[0] for k in keep]).value_counts().head(12).to_dict())

# %% [markdown]
# ## 3 · Quick EDA – seasonality and volatility
# Seasonality strength ≈ share of variance explained by calendar month after removing a 12-month trend.
# This tells us whether a *seasonal component* is worth shipping.

# %%
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rows = []
for (c, com, b), m in keep.items():
    y = np.log(m.p_loc)
    r = y - y.rolling(12).mean()
    r = r.dropna()
    if len(r) < 36:
        continue
    seas = r.groupby(r.index.month).transform("mean")
    rows.append((c, com, 1 - ((r - seas) ** 2).sum() / (r ** 2).sum(), y.diff().std()))
eda = pd.DataFrame(rows, columns=["country", "commodity", "seas_strength", "monthly_vol"])
print(eda.describe().round(3).to_string())
top = eda.sort_values("seas_strength", ascending=False).head(5)
print("\nmost seasonal series:\n", top.round(2).to_string(index=False))
fig, ax = plt.subplots(1, 2, figsize=(11, 3.2))
for (c, com, b) in [("RWA", "Maize", "kg"), ("KEN", "Maize (white)", "kg")]:
    if (c, com, b) in keep:
        keep[(c, com, b)].p_usd.plot(ax=ax[0], label=f"{c} {com}")
ax[0].set_title("USD per kg"); ax[0].legend()
eda.seas_strength.hist(bins=30, ax=ax[1]); ax[1].set_title("Seasonality strength (all series)")
plt.tight_layout(); plt.savefig(OUT / "price_eda.png", dpi=110); plt.close()

# %% [markdown]
# ## 4 · Feature engineering for a *pooled* model
# One model for all series (data-efficient and tiny). Target: **log price change** `y[t+h] - y[t]`, h = 1..6.
# All features use only data available at origin *t* (no leakage):
#
# | feature | meaning |
# |---|---|
# | `m1, m3, m6, m12` | log momentum over 1/3/6/12 months |
# | `dev12` | current log price minus its trailing 12-month mean (mean reversion) |
# | `vol12` | std of monthly log changes over trailing 12 months |
# | `sd_h` | seasonal index of target month − seasonal index of current month (expanding, leak-free) |

# %%
H = 6
BASE_FEATS = ["m1", "m3", "m6", "m12", "dev12"]


def build(m: pd.DataFrame, key) -> pd.DataFrame:
    y = np.log(m.p_loc.astype(float))
    f = pd.DataFrame(index=y.index)
    f["y"] = y
    for k in (1, 3, 6, 12):
        f[f"m{k}"] = y - y.shift(k)
    f["dev12"] = y - y.rolling(12).mean()
    f["vol12"] = y.diff().rolling(12).std()
    # leak-free expanding seasonal profile of detrended log price
    r = y - y.rolling(12).mean()
    prof = np.full((len(y), 12), np.nan)
    sums, cnts = np.zeros(12), np.zeros(12)
    mon = y.index.month.values - 1
    rv = r.values
    for i in range(len(y)):
        if not np.isnan(rv[i]):
            sums[mon[i]] += rv[i]; cnts[mon[i]] += 1
        with np.errstate(invalid="ignore", divide="ignore"):
            prof[i] = np.where(cnts > 0, sums / cnts, np.nan)
    prof = pd.DataFrame(prof, index=y.index)
    cur = np.array([prof.iloc[i, mon[i]] for i in range(len(y))])
    for h in range(1, H + 1):
        tgt_m = (mon + h) % 12
        tgt = np.array([prof.iloc[i, tgt_m[i]] for i in range(len(y))])
        f[f"sd{h}"] = np.nan_to_num(tgt - cur)
        f[f"t{h}"] = y.shift(-h) - y
    f["country"], f["commodity"] = key[0], key[1]
    f["origin"] = f.index
    return f.dropna(subset=BASE_FEATS + ["vol12"])


panel = pd.concat([build(m, k) for k, m in keep.items()], ignore_index=True)
print("panel rows:", len(panel), "| series:", len(keep))

# time split: train origins <= TRAIN_END, test origins afterwards (targets observed only)
TEST_START = pd.Timestamp("2023-07-01")
VAL_START = pd.Timestamp("2022-01-01")
tr = panel[panel.origin < VAL_START]
va = panel[(panel.origin >= VAL_START) & (panel.origin < TEST_START)]
te = panel[panel.origin >= TEST_START]
print(f"train {len(tr):,} | val {len(va):,} | test {len(te):,}")

# %% [markdown]
# ## 5 · Candidate models and honest backtest
# Metric: MAE of the **log** forecast ≈ average percentage error (0.10 ≈ 10 %).
# The bar to beat is **naive** ("price next month = price today"). Candidates:
# `seasonal` (calendar effect only), `ridge` (linear, ~50 numbers), `gbdt` (small LightGBM, 150 trees × 8 leaves).
# Protocol: fit on *train*, tune/calibrate on *val*, report on *test* (2023-07 →) which is never touched before.

# %%
from sklearn.linear_model import Ridge
import lightgbm as lgb

FEATS = BASE_FEATS + ["vol12"]
def feats(d, h): return d[FEATS + [f"sd{h}"]].values
LGB = dict(n_estimators=150, learning_rate=0.05, num_leaves=8, min_child_samples=100, subsample=0.8, subsample_freq=1,
           colsample_bytree=0.9, reg_lambda=5.0, objective="huber", alpha=0.3, random_state=SEED, verbose=-1)

res, preds = [], {n: {} for n in ("naive", "seasonal", "ridge", "gbdt")}
m_tr = {"ridge": {}, "gbdt": {}}          # fitted on train only -> used to calibrate intervals on val
m_tv = {"ridge": {}, "gbdt": {}}          # fitted on train+val -> evaluated on test
for h in range(1, H + 1):
    tr_h, va_h, te_h = (d.dropna(subset=[f"t{h}"]) for d in (tr, va, te))
    ytr, yva, yte = tr_h[f"t{h}"].values, va_h[f"t{h}"].values, te_h[f"t{h}"].values
    Xtr, Xva, Xte = feats(tr_h, h), feats(va_h, h), feats(te_h, h)
    alpha = min((10.0, 1.0, 100.0, 1000.0), key=lambda a: np.abs(Ridge(alpha=a).fit(Xtr, ytr).predict(Xva) - yva).mean())
    m_tr["ridge"][h] = Ridge(alpha=alpha).fit(Xtr, ytr)
    m_tr["gbdt"][h] = lgb.LGBMRegressor(**LGB).fit(Xtr, ytr)
    Xall, yall = np.vstack([Xtr, Xva]), np.concatenate([ytr, yva])
    m_tv["ridge"][h] = Ridge(alpha=alpha).fit(Xall, yall)
    m_tv["gbdt"][h] = lgb.LGBMRegressor(**LGB).fit(Xall, yall)
    P = {"naive": np.zeros_like(yte), "seasonal": te_h[f"sd{h}"].values,
         "ridge": m_tv["ridge"][h].predict(Xte), "gbdt": m_tv["gbdt"][h].predict(Xte)}
    for n, p in P.items():
        preds[n][h] = (te_h.index, p, yte)
        res.append((h, n, np.abs(p - yte).mean()))

bt = pd.DataFrame(res, columns=["h", "model", "MAE_log"])
tab = bt.pivot(index="h", columns="model", values="MAE_log")[["naive", "seasonal", "ridge", "gbdt"]]
print("MAE of log-price forecast by horizon (lower is better)\n", tab.round(4).to_string())
imp = (1 - tab[["seasonal", "ridge", "gbdt"]].div(tab["naive"], axis=0)) * 100
print("\nimprovement vs naive (%)\n", imp.round(1).to_string())

# %%
# decision rule: ship the simple ridge unless the tree model is >3 % better on average. Trees are still tiny and
# the app evaluates them with 10 lines of JavaScript (verified for exact parity below).
gap = 1 - tab["gbdt"].mean() / tab["ridge"].mean()
CHOSEN = "gbdt" if gap > 0.03 else "ridge"
print(f"GBDT vs Ridge average gain = {gap*100:.1f} %  ->  shipping '{CHOSEN}'")

# %% [markdown]
# ## 6 · Calibrated prediction intervals
# Farmers need a *range*, not a point. The residual is scaled by each series' own volatility (`vol12`); pooled empirical
# quantiles per horizon are taken from the **validation** set (model fitted on train only), then coverage is checked on
# the untouched **test** set.

# %%
Q = (0.10, 0.50, 0.90)
zq, cover = {}, []
for h in range(1, H + 1):
    va_h = va.dropna(subset=[f"t{h}"])
    z = (va_h[f"t{h}"].values - m_tr[CHOSEN][h].predict(feats(va_h, h))) / np.maximum(va_h["vol12"].values, 0.01)
    zq[h] = [float(np.quantile(z, q)) for q in Q]
    idx, p, y = preds[CHOSEN][h]
    v = np.maximum(te.loc[idx, "vol12"].values, 0.01)
    cover.append((h, float(((y >= p + zq[h][0] * v) & (y <= p + zq[h][2] * v)).mean())))
print("80 % interval coverage on TEST (target 0.80):", [(h, round(c, 3)) for h, c in cover])

EAC = ["BDI", "RWA", "KEN", "TZA", "UGA", "SOM", "COD", "SSD", "ETH"]
rows = []
for h in (1, 3, 6):
    idx, p, y = preds[CHOSEN][h]
    sel = te.loc[idx, "country"].isin(EAC).values
    rows.append((h, np.abs(p - y)[sel].mean(), np.abs(y)[sel].mean(), int(sel.sum())))
print(f"\nEAC+ slice ({CHOSEN}) h | model MAE | naive MAE | n\n", pd.DataFrame(rows).round(4).to_string(index=False, header=False))

# %% [markdown]
# ## 7 · Fit on ALL data and export the app model
# Per series the app only needs the latest features, 12 seasonal offsets and 24 months of history for the chart.
# The model itself is the ridge coefficients **or** the flattened trees (`nodes = [feature, threshold, left, right]`,
# leaves are `[-1, value, 0, 0]`).

# %%
full = panel
final = {}
for h in range(1, H + 1):
    d = full.dropna(subset=[f"t{h}"])
    if CHOSEN == "gbdt":
        final[h] = lgb.LGBMRegressor(**LGB).fit(feats(d, h), d[f"t{h}"].values)
    else:
        final[h] = Ridge(alpha=m_tv["ridge"][h].alpha).fit(feats(d, h), d[f"t{h}"].values)


def flatten_tree(t):
    nodes = []
    def rec(n):
        i = len(nodes); nodes.append(None)
        if "leaf_value" in n:
            nodes[i] = [-1, round(n["leaf_value"], 6), 0, 0]
        else:
            assert n["decision_type"] == "<="
            l = rec(n["left_child"]); r = rec(n["right_child"])
            nodes[i] = [n["split_feature"], float(f"{n['threshold']:.9g}"), l, r]
        return i
    rec(t["tree_structure"]); return nodes


def eval_flat(trees, x):
    tot = 0.0
    for nodes in trees:
        i = 0
        while nodes[i][0] >= 0:
            f, thr, l, r = nodes[i]; i = l if x[f] <= thr else r
        tot += nodes[i][1]
    return tot


if CHOSEN == "gbdt":
    model_core = {"type": "gbdt", "trees": {str(h): [flatten_tree(t) for t in final[h].booster_.dump_model()["tree_info"]] for h in range(1, H + 1)}}
    # parity: our flattened evaluator must equal LightGBM.predict
    # (compared on features rounded to 4 decimals - exactly what the app receives in price_series.json)
    h = 3; d = full.dropna(subset=[f"t{h}"]).sample(2000, random_state=1)
    Xr = np.round(feats(d, h).astype(float), 4)
    ref = final[h].predict(Xr)
    mine = np.array([eval_flat(model_core["trees"][str(h)], x) for x in Xr])
    print("tree-export parity (max abs diff vs lightgbm, log units):", float(np.abs(ref - mine).max()))
    assert np.abs(ref - mine).max() < 2e-3
else:
    model_core = {"type": "ridge", "ridge": {str(h): {"b": round(float(final[h].intercept_), 5), "w": [round(float(w), 5) for w in final[h].coef_]} for h in range(1, H + 1)}}

latest = panel.sort_values("origin").groupby(["country", "commodity"]).tail(1).set_index(["country", "commodity"])
fx_recent = df[df.month >= DATA_END - pd.DateOffset(months=3)].assign(fx=lambda x: x.price / x.usdprice)
fx = fx_recent.groupby("currency").fx.median().round(4)
names_cur = pd.read_csv(WFP_DIR / "wfp_currencies_global.csv").set_index("code").name.to_dict()

series_out = []
for (c, com, b), m in keep.items():
    if (c, com) not in latest.index:
        continue
    L = latest.loc[(c, com)]
    y = np.log(m.p_loc.astype(float))
    r = (y - y.rolling(12).mean()).dropna()
    seas = r.groupby(r.index.month).mean().reindex(range(1, 13)).fillna(0).round(4).tolist()
    hist = m.p_loc.tail(24)
    series_out.append({
        "c": c, "com": com, "u": b, "cur": m.currency.iloc[-1],
        "last": m.index[-1].strftime("%Y-%m"),
        "p": round(float(m.p_loc.iloc[-1]), 4), "pu": round(float(m.p_usd.iloc[-1]), 4),
        "f": [round(float(L[k]), 4) for k in FEATS],
        "sd": [round(float(L[f"sd{h}"]), 4) for h in range(1, H + 1)],
        "s": seas,
        "h": [round(float(v), 4) for v in hist.values], "h0": hist.index[0].strftime("%Y-%m"),
        "mape": None,
    })

# per-series backtest error (h=3) so the app can show an honest "usual error" badge
idx3, p3, y3 = preds[CHOSEN][3]
err = pd.DataFrame({"country": te.loc[idx3, "country"].values, "commodity": te.loc[idx3, "commodity"].values,
                    "e": np.abs(p3 - y3)}).groupby(["country", "commodity"]).e.mean()
for s in series_out:
    e = err.get((s["c"], s["com"]))
    s["mape"] = None if e is None or np.isnan(e) else round(float(e), 3)

model_json = {
    "version": 2, "data_end": DATA_END.strftime("%Y-%m"), "horizons": H, "features": FEATS + ["sd_h"], **model_core,
    "interval_q": {str(h): [round(z, 4) for z in zq[h]] for h in range(1, H + 1)},
    "backtest": {"MAE_log": {n: tab[n].round(4).to_dict() for n in tab.columns}, "coverage80": dict(cover)},
}
(OUT / "price_model.json").write_text(json.dumps(model_json, separators=(",", ":")))
(OUT / "price_series.json").write_text(json.dumps(series_out, separators=(",", ":")))
print("series shipped:", len(series_out), "| EAC+ series:", sum(s["c"] in EAC for s in series_out))
print(pd.Series([s["c"] for s in series_out if s["c"] in EAC]).value_counts().to_dict())

# %% [markdown]
# ## 8 · Offline "where can I sell?" – markets + implied FX
# `markets.json` = every market with coordinates, plus its **latest price per commodity** (last 9 months).
# The app sorts by distance from the user's GPS / chosen district and ranks by price → "best nearby place to sell".

# %%
mk_meta = pd.read_csv(WFP_DIR / "wfp_markets_global.csv").drop_duplicates("market_id").set_index("market_id")
recent = df[(df.month >= DATA_END - pd.DateOffset(months=9)) & (df.pricetype.isin(["Retail", "Wholesale"]))]
recent = recent.sort_values("month").groupby(["market_id", "commodity", "base"]).tail(1)
com_used = sorted({s["com"] for s in series_out})
recent = recent[recent.commodity.isin(com_used) & recent.market_id.isin(mk_meta.index) & recent.latitude.notna()]
cidx = {c: i for i, c in enumerate(com_used)}

markets = {}
for r in recent.itertuples():
    e = markets.setdefault(int(r.market_id), {
        "id": int(r.market_id), "n": r.market, "c": r.countryiso3, "a": (r.admin1 if isinstance(r.admin1, str) else ""),
        "la": round(float(r.latitude), 3), "lo": round(float(r.longitude), 3), "cur": r.currency, "p": []})
    e["p"].append([cidx[r.commodity], r.base, round(float(r.p_loc), 3), round(float(r.p_usd), 4), r.month.strftime("%Y-%m")])
(OUT / "markets.json").write_text(json.dumps(
    {"commodities": com_used, "markets": list(markets.values())}, separators=(",", ":")))

fx_json = {k: {"usd_per": round(1 / v, 8), "per_usd": float(v), "name": names_cur.get(k, k)}
           for k, v in fx.items() if v > 0 and np.isfinite(v)}
fx_json["USD"] = {"usd_per": 1.0, "per_usd": 1.0, "name": "US Dollar"}
(OUT / "fx.json").write_text(json.dumps({"as_of": DATA_END.strftime("%Y-%m"), "rates": fx_json}, separators=(",", ":")))
print(f"markets: {len(markets)} | currencies: {len(fx_json)}")
for f in ("price_model.json", "price_series.json", "markets.json", "fx.json"):
    print(f"{f:20s} {(OUT / f).stat().st_size / 1024:8.0f} KB")

# %% [markdown]
# ## 9 · Sanity check: replay the exact app math on one series
# The app evaluates the exported JSON in TypeScript; this block is the reference implementation the JS unit-tests
# compare against (`app/tests/fixtures.json` is generated from the same function).

# %%
mj = json.load(open(OUT / "price_model.json"))
s = next((x for x in series_out if x["c"] == "RWA" and x["com"].startswith("Maize")), series_out[0])


def forecast(s, mj):
    out = []
    for h in range(1, mj["horizons"] + 1):
        x = s["f"] + [s["sd"][h - 1]]
        d = eval_flat(mj["trees"][str(h)], x) if mj["type"] == "gbdt" else \
            mj["ridge"][str(h)]["b"] + sum(w * v for w, v in zip(mj["ridge"][str(h)]["w"], x))
        lo, _, hi = (d + z * max(s["f"][5], 0.01) for z in mj["interval_q"][str(h)])
        out.append((h, s["p"] * math.exp(d), s["p"] * math.exp(lo), s["p"] * math.exp(hi)))
    return out


print(s["c"], s["com"], s["cur"], "last", s["last"], "price", s["p"])
for h, p, lo, hi in forecast(s, mj):
    print(f"  +{h} mo: {p:10.2f}  (80 %: {lo:9.2f} - {hi:9.2f})")

# %% [markdown]
# ## 10 · FAOSTAT – what else can the farmer learn?
# * **Value of Production** → how big is each crop in the country and is it growing (price pressure / opportunity).
# * **Detailed Trade Matrix** (2.4 GB!) → which countries *buy* each crop from the farmer's country (export destinations).
# * Others (Trade Indices, Value shares, Census) are macro-level; we looked at them but they do not help a farmer
#   decide *this week* – see `docs/DATA_ANALYSIS.md`.
#
# The big file is streamed in chunks and only African reporters + export elements are kept.

# %%
try:
    import pycountry
except ImportError:
    os.system("pip -q install pycountry"); import pycountry

AREA = pd.read_csv(FAO_DIR / "Value_of_Production_E_All_Data_(Normalized)" / "Value_of_Production_E_AreaCodes.csv")
AREA["m49"] = AREA["M49 Code"].astype(str).str.replace("'", "").astype(int, errors="ignore")
iso = {}
for a in pycountry.countries:
    iso[int(a.numeric)] = a.alpha_3
AREA["iso3"] = pd.to_numeric(AREA["M49 Code"].astype(str).str.replace("'", ""), errors="coerce").map(iso)
AREA = AREA.dropna(subset=["iso3"])
area_iso = AREA.set_index("Area Code").iso3.to_dict()
area_name = AREA.set_index("Area Code").Area.to_dict()

WFP2FAO = {  # WFP commodity (prefix) -> FAOSTAT item name
    "Maize": "Maize (corn)", "Beans": "Beans, dry", "Cassava": "Cassava, fresh", "Rice": "Rice",
    "Sorghum": "Sorghum", "Millet": "Millet", "Wheat": "Wheat", "Potatoes": "Potatoes", "Sweet potatoes": "Sweet potatoes",
    "Tomatoes": "Tomatoes", "Onions": "Onions and shallots, dry (excluding dehydrated)", "Bananas": "Bananas",
    "Cabbage": "Cabbages", "Groundnuts": "Groundnuts, excluding shelled", "Coffee": "Coffee, green", "Soybeans": "Soya beans",
}
vop_path = FAO_DIR / "Value_of_Production_E_All_Data_(Normalized)" / "Value_of_Production_E_All_Data_(Normalized).csv"
vop = pd.read_csv(vop_path, usecols=["Area Code", "Item", "Element", "Year", "Value"], low_memory=False)
vop = vop[vop.Element.str.contains("constant 2014-2016 thousand US\\$") & vop.Item.isin(set(WFP2FAO.values()))]
vop["iso3"] = vop["Area Code"].map(area_iso)
vop = vop.dropna(subset=["iso3"])
last_y = int(vop.Year.max())
piv = vop.pivot_table(index=["iso3", "Item"], columns="Year", values="Value")
ins = {}
for (c, item), r in piv.iterrows():
    r = r.dropna()
    if len(r) < 6:
        continue
    a, b = r.loc[last_y - 4:last_y].mean(), r.loc[last_y - 9:last_y - 5].mean()
    if not np.isfinite(a):
        continue
    b = b if np.isfinite(b) else 0
    ins.setdefault(c, {})[item] = {"prod_kusd": round(float(a)), "growth5y_pct": round(float((a / b - 1) * 100), 1) if b else None}
print("production insights for", len(ins), "countries; latest year", last_y)

# %%
tm_path = FAO_DIR / "Trade_DetailedTradeMatrix_E_All_Data_(Normalized)" / "Trade_DetailedTradeMatrix_E_All_Data_(Normalized).csv"
want_items = set(WFP2FAO.values())
# FAO trade items use ';' or ',' variants → match on the first word to be safe
want_first = {w.split(" (")[0].split(",")[0].lower() for w in want_items}
tm_rows = []
for ch in pd.read_csv(tm_path, usecols=["Reporter Country Code", "Partner Countries", "Item", "Element", "Year", "Value"],
                      chunksize=2_000_000, low_memory=False):
    ch = ch[(ch.Element == "Export quantity") & (ch.Year >= last_y - 3)]
    if ch.empty:
        continue
    ch = ch[ch.Item.str.split(",").str[0].str.split(";").str[0].str.lower().isin(want_first)]
    ch["iso3"] = ch["Reporter Country Code"].map(area_iso)
    ch = ch.dropna(subset=["iso3"])
    tm_rows.append(ch.groupby(["iso3", "Item", "Partner Countries"], as_index=False).Value.sum())
tm = pd.concat(tm_rows).groupby(["iso3", "Item", "Partner Countries"], as_index=False).Value.sum()
tm = tm[tm.Value > 0].sort_values("Value", ascending=False)
dest = {}
for (c, item), g in tm.groupby(["iso3", "Item"]):
    tot = g.Value.sum()
    dest.setdefault(c, {})[item] = [[r["Partner Countries"], round(100 * r.Value / tot, 1)] for _, r in g.head(4).iterrows()]
fao_out = {"as_of_year": last_y, "production": ins, "export_destinations": dest, "item_map": WFP2FAO}
(OUT / "faostat_insights.json").write_text(json.dumps(fao_out, separators=(",", ":")))
print("export destinations for", len(dest), "countries |", (OUT / "faostat_insights.json").stat().st_size // 1024, "KB")
print(json.dumps({k: v for k, v in list(dest.get("RWA", {}).items())[:2]}, indent=1))
