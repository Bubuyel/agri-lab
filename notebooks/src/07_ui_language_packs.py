# %% [markdown]
# # 07 · Interface language packs for 30+ more languages (NLLB-200 / FLORES-200)
#
# The app UI exists in English plus hand-written languages (fr, sw, es, pt, hi, ar and drafts for rw/rn/so/yo).
# For every other language in `languages.json` this notebook produces `artifacts/lang/<code>.json` (≈ 15-25 KB each, shipped with the app → works offline).
#
# **Safety rules** (learned from the advice translation, see notebook 04): machine translation can be wrong, so each string is checked and falls back to English when
# 1. a `{placeholder}` was lost or changed, 2. symbols such as ⋮ ≡ ▸ were dropped, 3. the length ratio is absurd, or 4. the **round-trip chrF** (translate back to English) is very low.
# Hand-written strings always win over machine text. Languages carry a *beta* tag in the app until a native speaker reviews them.

# %%
import os, re, json, time, sys
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
try:
    from sacrebleu.metrics import CHRF
except ImportError:
    os.system(f"{sys.executable} -m pip -q install sacrebleu"); from sacrebleu.metrics import CHRF

ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts")); (OUT / "lang").mkdir(parents=True, exist_ok=True)
MODEL_ID = os.environ.get("NLLB_ID", "facebook/nllb-200-distilled-600M")
ONLY = [x for x in os.environ.get("ONLY_LANGS", "").split(",") if x]
THREADS = int(os.environ.get("NLLB_THREADS", os.cpu_count() or 4))

LANGS = json.load(open(OUT / "languages.json", encoding="utf-8"))
UI_EN = json.load(open(OUT / "ui_en.json", encoding="utf-8"))
HAND = json.load(open(OUT / "ui_hand.json", encoding="utf-8"))
todo_langs = [l for l in LANGS if l["code"] != "en" and (not ONLY or l["code"] in ONLY)]
print(len(UI_EN), "UI strings |", len(todo_langs), "languages")

dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(MODEL_ID, src_lang="eng_Latn")
nllb = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev).eval()
torch.set_num_threads(THREADS)

@torch.no_grad()
def translate(texts, src, tgt, bs=32, beams=2):
    tok.src_lang = src; out = []
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))           # similar lengths per batch → less padding
    res = [None] * len(texts)
    for i in range(0, len(order), bs):
        idx = order[i:i + bs]
        b = tok([texts[j] for j in idx], return_tensors="pt", padding=True).to(dev)
        g = nllb.generate(**b, forced_bos_token_id=tok.convert_tokens_to_ids(tgt), num_beams=beams, max_new_tokens=96, no_repeat_ngram_size=3)
        for j, t in zip(idx, tok.batch_decode(g, skip_special_tokens=True)): res[j] = t
    return res

# %% [markdown]
# ## Translate, validate, assemble packs

# %%
chrf = CHRF()
PH = re.compile(r"\{(\w+)\}")
SYM = "⋮≡▸→←·"
BRAND = "Agri Lab"
STRICT, LOOSE = 28, 18          # round-trip chrF: strings under STRICT get n-best candidates; the best one must still reach LOOSE
CACHE = OUT / "nllb_ui_cache.json"
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
report = {}
t0 = time.time()
for L in todo_langs:
    code, nl = L["code"], L["nllb"]
    keys = [k for k in UI_EN if k not in HAND.get(code, [])]
    c = cache.setdefault(code, {})
    need = [k for k in keys if k not in c]
    if need:
        src = [UI_EN[k].replace(BRAND, "AgriLab") for k in need]
        fw = translate(src, "eng_Latn", nl)
        bw = translate(fw, nl, "eng_Latn", beams=1)                      # greedy back-translation → quality screen
        for k, f, b in zip(need, fw, bw):
            c[k] = {"t": f, "bt": b}
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    def sc(bt, en): return chrf.sentence_score(bt, [en.replace(BRAND, "AgriLab")]).score
    def sane(en, t): return (set(PH.findall(en)) == set(PH.findall(t)) and all((ch in t) for ch in SYM if ch in en) and 0.25 <= (len(t) + 1) / (len(en) + 1) <= 4.5
                             and t.strip() and (BRAND in t or BRAND not in en))
    # second chance: strings below the strict bar get several candidates (n-best); we keep the one whose back-translation is closest to the English
    weak = [k for k in keys if "alts" not in c[k] and sc(c[k]["bt"], UI_EN[k]) < STRICT]
    if weak:
        src = [UI_EN[k].replace(BRAND, "AgriLab") for k in weak]
        tok.src_lang = "eng_Latn"
        for i in range(0, len(weak), 8):
            ks, ss = weak[i:i + 8], src[i:i + 8]
            with torch.no_grad():
                b = tok(ss, return_tensors="pt", padding=True).to(dev)
                g = nllb.generate(**b, forced_bos_token_id=tok.convert_tokens_to_ids(nl), num_beams=6, num_return_sequences=4, max_new_tokens=96, no_repeat_ngram_size=3)
            cand = tok.batch_decode(g, skip_special_tokens=True)
            flat = [x for x in cand]
            back = translate(flat, nl, "eng_Latn", beams=1)
            for j, k in enumerate(ks):
                c[k]["alts"] = [{"t": flat[4 * j + m], "bt": back[4 * j + m]} for m in range(4)]
        CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    ui, fallback = {}, 0
    for k in keys:
        en = UI_EN[k]; r = c[k]
        cands = [r] + r.get("alts", [])
        best = max(cands, key=lambda x: (sane(en, x["t"].replace("AgriLab", BRAND).replace("Agrilab", BRAND)), sc(x["bt"], en)))
        t = best["t"].replace("AgriLab", BRAND).replace("Agrilab", BRAND)
        if sane(en, t) and sc(best["bt"], en) >= LOOSE: ui[k] = t
        else: fallback += 1
    n = len(keys); report[code] = {"strings": n, "machine": len(ui), "english_fallback": fallback, "chrF_round_trip": round(sum(chrf.sentence_score(c[k]["bt"], [UI_EN[k].replace(BRAND, "AgriLab")]).score for k in keys) / max(1, n), 1)}
    (OUT / "lang" / f"{code}.json").write_text(json.dumps({"code": code, "machine": True, "ui": ui, "meta": report[code]}, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{code}: {report[code]}  ({time.time()-t0:.0f}s)", flush=True)

(OUT / "lang_report.json").write_text(json.dumps(report, indent=1))
print("packs:", len(report), "| total size KB:", sum(f.stat().st_size for f in (OUT / "lang").glob("*.json")) // 1024)
