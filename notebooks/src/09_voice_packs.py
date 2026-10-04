# %% [markdown]
# # 09 · Offline voice packs ("listen" buttons for people who cannot read)
#
# Plant advice is a **closed set of sentences** (140 + disease/crop names), so we can **pre-generate the voice once** and ship it as small MP3 clips
# instead of running a speech model on cheap phones. Voice: Meta **MMS-TTS** (VITS, 1100+ languages, CC-BY-NC 4.0 — fine for a non-commercial pilot;
# check the licence before a commercial release). Output: `artifacts/audio/<lang>/<id>.mp3` + `index.json` (sentence → file), ~2 MB per language.
#
# **Which languages?** Only a few, to keep the app small: Swahili, Kinyarwanda, Kirundi, Somali, Amharic, Hausa, Yoruba (phones rarely have voices for these).
# Clips read exactly the text shown on the result screen. Every other language uses the phone's own speech engine; when the phone has no voice the
# Listen button is hidden. `VOICE_LANGS=xx` generates any other MMS language.
#
# In the app a clip is used when it exists; otherwise the phone's own speech engine reads the text if it has a voice for that language.

# %%
import os, io, re, json, time, hashlib, sys
from pathlib import Path
import numpy as np
import torch
import lameenc
from transformers import VitsModel, AutoTokenizer

ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
AUDIO = OUT / "audio"; AUDIO.mkdir(parents=True, exist_ok=True)
torch.set_num_threads(int(os.environ.get("TTS_THREADS", os.cpu_count() or 4)))

# our language code → MMS-TTS id (only languages that have an MMS voice)
MMS = {"en": "eng", "fr": "fra", "es": "spa", "pt": "por", "ar": "ara", "hi": "hin", "sw": "swh", "rw": "kin", "rn": "run", "so": "som", "yo": "yor", "ha": "hau", "am": "amh",
       "om": "orm", "ti": "tir", "lg": "lug", "sn": "sna", "ny": "nya", "mg": "mlg", "bn": "ben", "ur": "urd-script_arabic", "ta": "tam", "te": "tel", "mr": "mar", "gu": "guj",
       "my": "mya", "km": "khm", "lo": "lao", "th": "tha", "vi": "vie", "id": "ind", "tl": "tgl"}
# To keep the app small we ship clips only for Kirundi (phones have no built-in voice for it).
# Phones already speak en, fr, es, pt, ar, hi, zh etc. themselves. Add more with VOICE_LANGS=xx,yy (about 1-2 MB per language, downloaded on demand).
SHIPPED = []      # no downloadable voice packs shipped; phones use their own speech engine. Add codes (e.g. ["rn"]) or set VOICE_LANGS=rn to generate packs.
adv = json.load(open(OUT / "advice.json", encoding="utf-8"))
wanted = [x for x in os.environ.get("VOICE_LANGS", "").split(",") if x] or [lg for lg in SHIPPED if lg in adv["advice"]]
print("languages:", wanted)


def sentences(A):
    """Every text the result screen can read aloud, in one language."""
    out = []
    for lab, e in A["labels"].items():
        out += [e["name"]] + e["what"] + e["treat"] + e["prevent"]
    for v in A["_msg"].values(): out += v
    out += list(A["_crop"].values())
    seen, uniq = set(), []
    for s in out:
        s = s.strip()
        if s and s not in seen: seen.add(s); uniq.append(s)
    return uniq


def clean(s):                                            # TTS-friendly text
    s = re.sub(r"\([^)]*\)", "", s)                        # drop "(Late blight)" style English hints
    s = re.sub(r"[“”«»\"]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def mp3(wave, sr):
    pcm = (np.clip(wave, -1, 1) * 32767).astype("<i2")
    enc = lameenc.Encoder(); enc.set_bit_rate(32); enc.set_in_sample_rate(sr); enc.set_channels(1); enc.set_quality(2)
    return bytes(enc.encode(pcm.tobytes()) + enc.flush())


report = {}
for lg in wanted:
    d = AUDIO / lg; d.mkdir(exist_ok=True)
    idx_path = d / "index.json"
    idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
    todo = [s for s in sentences(adv["advice"][lg]) if s not in idx]
    print(f"{lg}: {len(todo)} clips to generate", flush=True)
    if not todo:
        continue
    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(f"facebook/mms-tts-{MMS[lg]}")
    if getattr(tok, "is_uroman", False):
        print(f"  {lg}: this voice needs the 'uroman' romaniser - skipping (pip install uroman to enable)"); continue
    model = VitsModel.from_pretrained(f"facebook/mms-tts-{MMS[lg]}").eval()
    bad = 0; secs = 0.0
    for i, s in enumerate(todo):
        txt = clean(s)
        if not txt: continue
        try:
            inp = tok(txt, return_tensors="pt")
            torch.manual_seed(0)
            with torch.no_grad():
                w = model(**inp).waveform[0].numpy()
            dur = len(w) / model.config.sampling_rate
            if not np.isfinite(w).all() or dur < 0.25 or dur > 40 or float(np.sqrt((w ** 2).mean())) < 0.005:
                bad += 1; continue
            fid = hashlib.sha1((lg + s).encode("utf-8")).hexdigest()[:12] + ".mp3"
            (d / fid).write_bytes(mp3(w, model.config.sampling_rate)); idx[s] = fid; secs += dur
        except Exception as e:
            bad += 1; print("  fail:", s[:40], type(e).__name__, str(e)[:60])
        if i % 40 == 0: print(f"  {lg} {i}/{len(todo)}  ({time.time()-t0:.0f}s)", flush=True)
    idx_path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
    size = sum(f.stat().st_size for f in d.glob("*.mp3")) / 1e6
    report[lg] = {"clips": len(idx), "failed": bad, "minutes": round(secs / 60, 1), "mb": round(size, 2)}
    print("  →", report[lg], flush=True)
    del model

(OUT / "voice_report.json").write_text(json.dumps(report, indent=1))
print(json.dumps(report))
