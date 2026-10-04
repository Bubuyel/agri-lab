"""Developer helper: write an English-only advice.json (all languages = English) so the app can be tested
before the NLLB translation notebook has finished. The real file is produced by notebooks/src/04_advice_translation.py."""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "notebooks" / "src" / "04_advice_translation.py").read_text(encoding="utf-8")
head = src[: src.index("# %% [markdown]\n# ## 2 · Translate")]
os.environ["AGRI_ROOT"] = str(ROOT.parent)
ns: dict = {"__name__": "stub"}
exec(compile(head, "04_head", "exec"), ns)
KB, MESSAGES, CROP_NAMES, LANGS, pretty = ns["KB"], ns["MESSAGES"], ns["CROP_NAMES"], ns["LANGS"], ns["pretty"]

def lang_block(lg):
    return {"_msg": MESSAGES, "_crop": {c: n.get(lg) or n["en"] for c, n in CROP_NAMES.items()},
            "labels": {l: {"name": "Healthy" if l.endswith("healthy") else pretty(l), **{k: e[k] for k in ("what", "treat", "prevent")}} for l, e in KB.items()}}

bundle = {"version": 0, "languages": {"en": "English", "fr": "Français", "sw": "Kiswahili", "rw": "Kinyarwanda", "rn": "Ikirundi", "so": "Soomaali", "yo": "Yorùbá"},
          "reviewed": {k: k == "en" for k in LANGS}, "quality_chrF": {}, "advice": {lg: lang_block(lg) for lg in LANGS}}
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "app" / "public" / "data" / "advice.json"
out.write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print("stub advice ->", out, out.stat().st_size // 1024, "KB")
