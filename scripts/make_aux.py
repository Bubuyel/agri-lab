"""Small build helpers that are not part of model training.

* countries.json  - ISO3 -> English country name for every country in markets.json
* app icons       - simple generated PNG icons (192/512 + maskable) so the PWA is installable
* app/tests/fixtures.json - reference outputs from the Python side, used by the TypeScript unit tests to prove the
                    app math (price forecast, rain outlook) equals the notebooks' math.

Usage: python scripts/make_aux.py
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
APP = ROOT / "app"


def countries():
    import pycountry
    m = json.load(open(ART / "markets.json"))
    iso = sorted({x["c"] for x in m["markets"]} | {s["c"] for s in json.load(open(ART / "price_series.json"))})
    names = {}
    for c in iso:
        p = pycountry.countries.get(alpha_3=c)
        names[c] = getattr(p, "common_name", None) or (p.name if p else c)
    (ART / "countries.json").write_text(json.dumps(names, ensure_ascii=False, separators=(",", ":")))
    print("countries.json:", len(names))


def icons():
    out = APP / "public" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for size, name, pad in ((192, "icon-192.png", 0.0), (512, "icon-512.png", 0.0), (512, "maskable-512.png", 0.14)):
        im = Image.new("RGB", (size, size), "#1b7f3b")
        d = ImageDraw.Draw(im)
        inset = size * pad
        if pad == 0:
            d.rounded_rectangle((0, 0, size, size), radius=size * 0.22, fill="#1b7f3b")
        cx, cy, r = size / 2, size / 2, size * (0.5 - pad) * 0.62
        # leaf: two arcs
        pts = []
        for t in np.linspace(0, math.pi, 40):
            pts.append((cx - r * 0.75 * math.sin(t) * 0.9 + 0 * inset, cy - r + (2 * r) * (t / math.pi)))
        leaf = [(cx, cy - r)]
        for t in np.linspace(0, math.pi, 50):
            leaf.append((cx + r * 0.7 * math.sin(t), cy - r + 2 * r * t / math.pi))
        for t in np.linspace(math.pi, 0, 50):
            leaf.append((cx - r * 0.7 * math.sin(t), cy - r + 2 * r * t / math.pi))
        d.polygon(leaf, fill="#ffffff")
        d.line((cx, cy - r * 0.8, cx, cy + r * 1.05), fill="#1b7f3b", width=max(3, size // 40))
        im.save(out / name)
    (APP / "public" / "manifest.webmanifest").write_text(json.dumps({
        "name": "AgriAI", "short_name": "AgriAI", "description": "Offline plant doctor, crop prices and rain outlook",
        "start_url": "./", "scope": "./", "display": "standalone", "orientation": "portrait",
        "background_color": "#1b7f3b", "theme_color": "#1b7f3b",
        "icons": [{"src": "icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
                  {"src": "icons/maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, indent=1))
    print("icons + manifest written")


def eval_flat(trees, x):
    tot = 0.0
    for nodes in trees:
        i = 0
        while nodes[i][0] >= 0:
            f, thr, l, r = nodes[i]
            i = l if x[f] <= thr else r
        tot += nodes[i][1]
    return tot


def fixtures():
    """Reference numbers computed with the *notebook* formulas."""
    mj = json.load(open(ART / "price_model.json"))
    series = json.load(open(ART / "price_series.json"))
    picks = [s for s in series if s["c"] in ("RWA", "KEN", "UGA", "BDI", "TZA")][:12] or series[:12]
    price = []
    for s in picks:
        fc = []
        for h in range(1, mj["horizons"] + 1):
            x = s["f"] + [s["sd"][h - 1]]
            if mj["type"] == "gbdt":
                d = eval_flat(mj["trees"][str(h)], x)
            else:
                d = mj["ridge"][str(h)]["b"] + sum(w * v for w, v in zip(mj["ridge"][str(h)]["w"], x))
            lo, _, hi = (d + z * max(s["f"][5], 0.01) for z in mj["interval_q"][str(h)])
            fc.append([s["p"] * math.exp(d), s["p"] * math.exp(lo), s["p"] * math.exp(hi)])
        price.append({"series": s, "forecast": fc})
    out = {"price": price}

    # rain: replay python outlook for a few places
    rm = json.load(open(ART / "rain_model.json"))
    rain = []
    for name, lat, lon in [("Kigali", -1.95, 30.06), ("Nairobi", -1.29, 36.82), ("Gitega", -3.43, 29.93),
                           ("Kampala", 0.35, 32.58), ("Dodoma", -6.17, 35.74), ("Mogadishu", 2.05, 45.32), ("Kano", 12.0, 8.52)]:
        rain.append({"name": name, "lat": lat, "lon": lon, "expect": rain_ref(rm, lat, lon)})
    out["rain"] = rain
    (APP / "tests").mkdir(exist_ok=True)
    (APP / "tests" / "fixtures.json").write_text(json.dumps(out))
    print("fixtures:", len(price), "price series,", len(rain), "rain places")


def rain_ref(rm, lat, lon):
    def load(nm):
        meta = rm["grids"][nm]
        buf = (ART / f"rain_{nm}.bin").read_bytes()
        arrs, off = {}, 0
        for name, typ, shape in meta["layout"]:
            n = int(np.prod(shape)); dt = {"u16": "<u2", "i8": "i1", "u8": "u1"}[typ]
            a = np.frombuffer(buf, dtype=dt, count=n, offset=off).reshape(shape)
            off += n * np.dtype(dt).itemsize
            arrs[name] = a
        return meta, arrs
    for nm in ("eac", "africa"):
        meta, a = load(nm)
        r, c = int((meta["lat0"] - lat) / meta["res"]), int((lon - meta["lon0"]) / meta["res"])
        if 0 <= r < meta["nrow"] and 0 <= c < meta["ncol"] and a["state"][0, r, c] != -128:
            x = a["state"][:, r, c].astype(float) / meta["state_scale"]
            om = meta["last_month"][1]
            res = []
            for h in range(1, rm["leads"] + 1):
                tm = (om - 1 + h) % 12 + 1
                p67 = int(a["p67"][tm - 1, r, c]); p33 = int(a["p33"][tm - 1, r, c])
                m = rm["logit"].get(f"{h}_{om}")
                if m is None or p67 < meta["dry_p67_mm"]:
                    res.append({"month": tm, "dry": True, "p33": p33, "p67": p67}); continue
                lg = np.array(m["b"]) + np.array(m["w"]) @ x
                p = np.exp(lg - lg.max()); p /= p.sum()
                res.append({"month": tm, "dry": False, "probs": p.tolist(), "p33": p33, "p67": p67})
            return {"grid": nm, "months": res}
    return None


# ───────────── reference implementation of the land model (the notebook's maths, plain Python) ─────────────
def _clip(x, a=0.0, b=1.0): return min(b, max(a, x))

def _trap(x, q):
    a, b, c, d = q
    half = (c - b) / 2 + 1e-9; mid = (b + c) / 2
    if b <= x <= c: return _clip(0.85 + 0.15 * (1 - abs(x - mid) / half))
    if x < b: return _clip(0.85 * (x - a) / (b - a))
    return _clip(0.85 * (d - x) / (d - c))

def _suit(c, s):
    tex = c["tex"]; clay, sand = s["clay"], s["sand"]
    tf = (0.7 if clay > 45 else 0.9 if clay > 35 else 1.0) if tex == "light" else (0.7 if sand > 70 else 0.9 if sand > 60 else 1.0) if tex == "heavy" else (0.75 if (clay > 60 or sand > 80) else 1.0)
    ff = 0.8 + 0.2 * ((_clip(s["oc"] / 20) + _clip(s["n"] / 2) + _clip(s["cec"] / 20)) / 3)
    season = _clip((s["wet"] + (3 if c["perennial"] else 0.5)) / c["cycle"]) if c["cycle"] > 2 else 1.0
    prod = _trap(s["tmean"], c["T"]) * _trap(s["rain"], c["R"]) * _trap(s["ph"], c["pH"]) * _clip((s["tmin"] - (c["kill"] - 3)) / 3) * season
    return _clip(prod) ** (1 / 3) * tf * ff * c["w"]

def _rot(prev, c):
    if prev is None or prev["perennial"] or c["perennial"]: return 1.0
    if prev["id"] == c["id"]: return 0.45
    if prev["fam"] == c["fam"]:
        return 0.4 if c["fam"] in ("solanaceae", "brassica") else 0.65 if c["fam"] == "legume" else 0.8 if c["fam"] == "cereal" else 0.55
    if c["fam"] == "legume" and prev["fam"] in ("cereal", "root", "solanaceae", "brassica", "alliaceae", "asteraceae"): return 1.25
    if c["fam"] == "cereal" and prev["fam"] == "legume": return 1.2
    if c["fam"] == "root" and prev["fam"] == "legume": return 1.1
    return 1.0

def land_fixtures():
    lm = json.load(open(ART / "land_model.json")); src = json.load(open(ART / "land_fixtures_src.json"))
    crops = lm["crops"]; out = []
    for f in src:
        s = {}
        for lay, q in zip(lm["layers"], f["q"]):
            v = q * lay["scale"] + lay["offset"]; s[lay["key"]] = math.expm1(v) if lay["log"] else v
        row = {"place": f["place"], "lat": f["lat"], "lon": f["lon"], "grid": f["grid"], "soil": s, "shares": {}}
        for prev_id in (None, "maize", "bean"):
            prev = next((c for c in crops if c["id"] == prev_id), None)
            sc = [_suit(c, s) * _rot(prev, c) for c in crops]
            pw = [x ** lm["share_power"] if x >= lm["share_floor"] else 0.0 for x in sc]
            for i in sorted(range(len(pw)), key=lambda i: -pw[i])[lm["share_top"]:]: pw[i] = 0.0
            tot = sum(pw); row["shares"][str(prev_id)] = [100 * x / tot if tot else 0.0 for x in pw]
        out.append(row)
    (APP / "tests" / "land_fixtures.json").write_text(json.dumps(out))
    print("land fixtures:", len(out))

def daily_fixtures():
    meta = json.load(open(ART / "rain_daily.json")); buf = (ART / "rain_daily.bin").read_bytes()
    nr, nc = meta["nrow"], meta["ncol"]; N = nr * nc
    a = np.frombuffer(buf, dtype="u1"); p = a[: 48 * N].reshape(12, 4, nr, nc); clim = a[48 * N: 60 * N].reshape(12, nr, nc)
    res = []
    for name, lat, lon in [("Kigali", -1.95, 30.06), ("Nairobi", -1.29, 36.82), ("Kano", 12.0, 8.52), ("Dodoma", -6.17, 35.74)]:
        r, c = int((meta["lat0"] - lat) / meta["res"]), int((lon - meta["lon0"]) / meta["res"])
        for month in (1, 4, 7, 10):
            for yw, tw in ((False, False), (False, True), (True, True)):
                if clim[month - 1, r, c] == 255: continue
                P = [p[month - 1, s, r, c] / 255 for s in range(4)]
                dist = [0, 0, 0, 0]; dist[(2 if yw else 0) + (1 if tw else 0)] = 1; chance = []
                for _ in range(7):
                    nxt = [0, 0, 0, 0]
                    for s_ in range(4):
                        t_ = s_ % 2; nxt[t_ * 2 + 1] += dist[s_] * P[s_]; nxt[t_ * 2] += dist[s_] * (1 - P[s_])
                    dist = nxt; chance.append(dist[1] + dist[3])
                res.append({"name": name, "lat": lat, "lon": lon, "month": month, "y": yw, "t": tw, "chance": chance, "monthChance": clim[month - 1, r, c] / 255})
    (APP / "tests" / "daily_fixtures.json").write_text(json.dumps(res))
    print("daily fixtures:", len(res))


def nlu_feature_fixtures():
    """Reference n-gram hashing (identical to notebook 08) for multi-script test strings → TypeScript parity test."""
    import re
    import unicodedata
    NB = 1 << 14

    def norm(t):
        t = unicodedata.normalize("NFD", t.lower()); t = re.sub("([a-z])[" + chr(0x300) + "-" + chr(0x36f) + "]+", lambda m: m.group(1), t); return unicodedata.normalize("NFC", t)

    def tokens(t):
        out, cur = [], []
        for ch in t:
            if unicodedata.category(ch)[0] in "ZPSC":
                if cur: out.append("".join(cur)); cur = []
            else: cur.append(ch)
        if cur: out.append("".join(cur))
        return out

    def fnv(t):
        h = 2166136261
        for b in t.encode("utf-8"): h ^= b; h = (h * 16777619) & 0xFFFFFFFF
        return h

    def feats(t):
        ids = set()
        for w in tokens(norm(t)):
            ids.add(fnv("w:" + w) % NB); cp = list("<" + w + ">")
            for n in (2, 3, 4):
                for i in range(len(cp) - n + 1): ids.add(fnv("c:" + "".join(cp[i:i + n])) % NB)
        return sorted(ids)

    texts = ["How do I treat tomato late blight?", "Combien coûtera le maïs le mois prochain ?", "¿Lloverá esta semana?", "Quanto vai custar o milho?", "टमाटर के पछेता झुलसा का इलाज कैसे करूँ?",
             "كيف أعالج اللفحة المتأخرة في الطماطم؟", "Nitatibuje baka la nyanya?", "አማርኛ ጥያቄ ይህ ነው", "Wie viel kostet Mais", "我的玉米生病了怎么办", "ฝนจะตกไหม", "Ndi liti pamene mvula idzagwa?", "HELLO!!", "  ", "Gitega  -  rain?"]
    fx = [{"text": t, "feats": feats(t), "norm": norm(t), "tokens": tokens(norm(t))} for t in texts]
    (APP / "tests" / "nlu_feature_fixtures.json").write_text(json.dumps(fx, ensure_ascii=False))
    print("nlu feature fixtures:", len(fx))


if __name__ == "__main__":
    import sys
    what = sys.argv[1:] or ["countries", "icons", "fixtures"]
    if "countries" in what: countries()
    if "icons" in what: icons()
    if "fixtures" in what: fixtures()
    if "land" in what: land_fixtures()
    if "daily" in what: daily_fixtures()
    if "nlu" in what: nlu_feature_fixtures()
