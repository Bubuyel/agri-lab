# %% [markdown]
# # 04 · Disease advice in local languages (FLORES-200 / NLLB-200)
#
# **Requirement:** after the vision model names the crop + disease, the app explains *what it is* and *how to cure it*
# in **Kinyarwanda, Kirundi, Swahili, English, French, Somali, Yoruba** – offline, on cheap phones.
#
# ## Design decision: "generate once, ship the text" instead of running an LLM on the phone
# * The vision model has a **closed set of 42 outputs**. The only text ever needed is 41 diseases + a few messages.
# * NLLB-200-distilled-600M (the FLORES-200 translation model) is ~2.4 GB fp32 / ~600 MB int8 – too big and too slow for
#   low-end phones, and a free-running generative model can **hallucinate pesticide advice**, which is dangerous.
# * So we write a short **expert English knowledge base** (reviewed by an agronomist), have NLLB translate it **here, at build time**
#   (this *is* the "fine-tuned for these diseases only" step: the model is constrained to this domain), measure translation
#   quality by back-translation, let **native speakers override** weak sentences, and ship a ~150 KB JSON.
# * Result: 0 MB model on the phone, instant, deterministic, safe, and every sentence can be audited.
#
# **Lesson from the first run (kept on purpose):** raw NLLB output was *dangerously wrong on domain terms* – "Late blight"
# became "early pain" (Swahili) and "late epidemic" (French). Therefore:
# 1. **disease names are never machine-translated** – they come from a hand-written glossary (`scripts/build_overrides.py`),
#    and KB sentences say "This is a fungus." instead of repeating the name;
# 2. **French and Swahili are human-written** overrides (still deserve a native proof-read);
# 3. **Kinyarwanda, Kirundi, Somali, Yoruba use NLLB** and are labelled *machine translated* in the app until native speakers add overrides.
#
# Optional phase 2 (documented at the end): LoRA-fine-tune NLLB on the human-corrected pairs to translate *new* text.

# %%
import os, json, re, sys, time
from pathlib import Path
ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
OUT.mkdir(parents=True, exist_ok=True)
OVERRIDES = OUT / "translation_overrides.json"       # {lang: {english sentence: corrected translation}}  (native-speaker edits)
# FLORES-200 language codes used by NLLB-200
_LJ = OUT / "languages.json"      # exported by `node app/scripts/export-i18n.mjs`
if _LJ.exists():
    _L = json.loads(_LJ.read_text(encoding="utf-8"))
    LANGS = {l["code"]: l["nllb"] for l in _L}
    LANG_NAMES = {l["code"]: l["native"] for l in _L}
else:                              # fallback: the original 7 languages
    LANGS = {"en": "eng_Latn", "fr": "fra_Latn", "sw": "swh_Latn", "rw": "kin_Latn", "rn": "run_Latn", "so": "som_Latn", "yo": "yor_Latn"}
    LANG_NAMES = {"en": "English", "fr": "Français", "sw": "Kiswahili", "rw": "Kinyarwanda", "rn": "Ikirundi", "so": "Soomaali", "yo": "Yorùbá"}
MODEL_ID = os.environ.get("NLLB_ID", "facebook/nllb-200-distilled-600M")

# %% [markdown]
# ## 1 · English knowledge base (source of truth)
# One entry per class id from `labels.json`. Each field is a list of **short sentences** (NLLB translates short
# sentences far more reliably than paragraphs). Wording rules: plain words, imperative verbs, no brand names,
# *"follow the label"* for any chemical, always cheapest/safest first.

# %%
HEALTHY = dict(what=["The leaf looks healthy.", "No disease was seen."], treat=["No treatment is needed."],
               prevent=["Check your plants every week.", "Water at the base of the plant.", "Keep weeds away."])
FUNGICIDE = "If the spots keep spreading, spray a fungicide that is approved for this crop. Follow the label."
KB = {
 "apple___apple_scab": dict(what=["This is a fungus.", "It makes dark olive-green to black rough spots on leaves and fruit."],
    treat=["Pick up and burn fallen leaves and spotted leaves.", FUNGICIDE, "Do not spray in the hot midday sun."],
    prevent=["Prune the tree so air can pass through.", "Plant scab-resistant varieties."]),
 "apple___black_rot": dict(what=["This is a fungus.", "It makes brown leaf spots with a purple edge and rots the fruit."],
    treat=["Cut out dead branches and burn them.", "Remove rotten and dried fruit from the tree and the ground.", FUNGICIDE],
    prevent=["Avoid wounding the tree.", "Prune so air can pass through."]),
 "apple___cedar_apple_rust": dict(what=["This is a fungus.", "It makes bright yellow-orange spots on the leaves."],
    treat=["Remove the spotted leaves.", FUNGICIDE],
    prevent=["Remove juniper or cedar trees growing nearby.", "Plant resistant apple varieties."]),
 "apple___healthy": HEALTHY, "blueberry___healthy": HEALTHY, "cherry___healthy": HEALTHY, "grape___healthy": HEALTHY,
 "peach___healthy": HEALTHY, "pepper___healthy": HEALTHY, "potato___healthy": HEALTHY, "raspberry___healthy": HEALTHY,
 "soybean___healthy": HEALTHY, "strawberry___healthy": HEALTHY, "tomato___healthy": HEALTHY, "maize___healthy": HEALTHY,
 "coffee___healthy": HEALTHY,
 "cherry___powdery_mildew": dict(what=["This is a fungus.", "It makes a white powder on the leaves."],
    treat=["Cut off and burn the badly affected shoots.", "Spray sulphur as the label says."],
    prevent=["Prune so air can pass through.", "Do not use too much nitrogen fertilizer."]),
 "maize___cercospora_leaf_spot_gray_leaf_spot": dict(what=["This is a fungus.", "It makes long gray-brown rectangular spots on the leaves."],
    treat=["Remove or bury the old maize stalks after harvest.", FUNGICIDE],
    prevent=["Do not plant maize in the same field every year.", "Use resistant seed.", "Do not plant too close together."]),
 "maize___common_rust": dict(what=["This is a fungus.", "It makes small round red-brown bumps on both sides of the leaf."],
    treat=["Light rust usually does not need treatment.", "If rust is heavy before the tassel appears, spray a fungicide. Follow the label."],
    prevent=["Plant resistant seed.", "Plant early in the season."]),
 "maize___northern_leaf_blight": dict(what=["This is a fungus.", "It makes long gray-green spots shaped like cigars."],
    treat=["Remove or bury old maize stalks after harvest.", FUNGICIDE],
    prevent=["Rotate maize with beans or other crops.", "Use resistant seed."]),
 "grape___black_rot": dict(what=["This is a fungus.", "It makes brown round spots with black dots, and the grapes dry up black."],
    treat=["Remove dried grapes and spotted leaves and burn them.", FUNGICIDE],
    prevent=["Prune so air and sun reach the leaves.", "Keep the vineyard clean."]),
 "grape___esca_black_measles": dict(what=["This is a fungus that lives in the wood of the vine.", "The leaves get yellow and red stripes between the veins."],
    treat=["There is no cure.", "Cut out the dead wood in dry weather and burn it.", "Cover big cuts with a wound paste."],
    prevent=["Prune only in dry weather.", "Use clean tools."]),
 "grape___leaf_blight_isariopsis_leaf_spot": dict(what=["This is a fungus.", "It makes dark brown spots with straight edges on the leaves."],
    treat=["Remove spotted leaves.", "Spray a copper fungicide as the label says."],
    prevent=["Prune so air can pass through.", "Keep the ground clean under the vines."]),
 "orange___haunglongbing_citrus_greening": dict(what=["This is a serious disease spread by a small insect.", "The leaves get yellow patches and the fruit stays small, bitter and lopsided."],
    treat=["There is no cure.", "Remove and burn the sick tree. Tell your agriculture officer.", "Control the small jumping insects on your citrus trees."],
    prevent=["Plant only clean, certified seedlings.", "Watch your trees for the small insects."]),
 "peach___bacterial_spot": dict(what=["This disease is caused by bacteria.", "It makes small dark spots on the leaves and fruit, and holes in the leaves."],
    treat=["Remove the worst leaves and fruit.", "Spray a copper product as the label says."],
    prevent=["Plant resistant varieties.", "Do not water over the leaves.", "Prune so air can pass through."]),
 "pepper___bacterial_spot": dict(what=["This disease is caused by bacteria.", "It makes small dark wet-looking spots on the leaves and fruit."],
    treat=["Remove and burn badly sick plants.", "Spray a copper product as the label says.", "Do not touch the plants when they are wet."],
    prevent=["Use clean seed.", "Do not plant peppers in the same place for two or three years.", "Water at the base of the plant."]),
 "potato___early_blight": dict(what=["This is a fungus.", "It makes brown spots with rings, like a target, first on the old lower leaves."],
    treat=["Remove the spotted lower leaves.", FUNGICIDE],
    prevent=["Rotate potatoes with other crops.", "Feed the plants well.", "Cover the soil with mulch."]),
 "potato___late_blight": dict(what=["This is a very fast and dangerous fungus.", "It makes dark wet patches on the leaves and white mold under the leaf when it is damp. It can destroy the field in a few days."],
    treat=["Act today.", "Pull out and destroy the sick plants. Do not leave them in the field.", "Spray a fungicide approved for potatoes. Follow the label.", "Do not store tubers that look sick."],
    prevent=["Plant certified clean seed potatoes.", "Plant resistant varieties.", "Heap soil on the rows to cover the tubers.", "Do not plant potatoes in the same field every year."]),
 "squash___powdery_mildew": dict(what=["This is a fungus.", "It makes a white powder on the leaves."],
    treat=["Remove the worst leaves.", "Spray sulphur or neem oil as the label says."],
    prevent=["Give the plants space.", "Plant in full sun.", "Use resistant varieties."]),
 "strawberry___leaf_scorch": dict(what=["This is a fungus.", "It makes small purple spots that join together and the leaf edges look burnt."],
    treat=["Remove the spotted leaves.", FUNGICIDE],
    prevent=["Do not plant too close together.", "Water at the base of the plant.", "Replace old plants."]),
 "tomato___bacterial_spot": dict(what=["This disease is caused by bacteria.", "It makes small dark spots with a yellow ring on the leaves and rough spots on the fruit."],
    treat=["Remove the sick leaves.", "Spray a copper product as the label says.", "Do not touch the plants when they are wet."],
    prevent=["Use clean seed.", "Do not plant tomatoes in the same place for two or three years.", "Water at the base of the plant."]),
 "tomato___early_blight": dict(what=["This is a fungus.", "It makes brown spots with rings, like a target, first on the old lower leaves."],
    treat=["Remove the spotted lower leaves.", FUNGICIDE],
    prevent=["Rotate tomatoes with other crops.", "Cover the soil with mulch.", "Water at the base of the plant."]),
 "tomato___late_blight": dict(what=["This is a very fast and dangerous fungus.", "It makes big dark wet patches on the leaves and white mold in damp weather."],
    treat=["Act today.", "Pull out and destroy the sick plants.", "Spray a fungicide approved for tomatoes. Follow the label."],
    prevent=["Plant resistant varieties.", "Do not water over the leaves.", "Do not plant tomatoes or potatoes in the same place every year."]),
 "tomato___leaf_mold": dict(what=["This is a fungus that likes damp, closed places.", "It makes pale yellow spots on top of the leaf and olive-brown mold under the leaf."],
    treat=["Remove the sick leaves.", "Open the greenhouse or space the plants so air can pass.", FUNGICIDE],
    prevent=["Stake the plants.", "Keep the leaves dry."]),
 "tomato___septoria_leaf_spot": dict(what=["This is a fungus.", "It makes many small round spots with a gray center on the lower leaves."],
    treat=["Remove the spotted leaves.", FUNGICIDE],
    prevent=["Cover the soil with mulch.", "Water at the base of the plant.", "Rotate tomatoes with other crops."]),
 "tomato___spider_mites_two_spotted_spider_mite": dict(what=["These are tiny insects under the leaf.", "The leaves get small yellow dots and fine webs."],
    treat=["Spray water under the leaves.", "Spray soap water or neem oil on the underside of the leaves.", "Use a miticide only if it is really needed. Follow the label."],
    prevent=["Do not let plants suffer from dust or dry soil.", "Do not kill the helpful insects."]),
 "tomato___target_spot": dict(what=["This is a fungus.", "It makes brown spots with rings on the leaves and sometimes on the fruit."],
    treat=["Remove the spotted leaves.", FUNGICIDE],
    prevent=["Space the plants.", "Water at the base of the plant.", "Rotate tomatoes with other crops."]),
 "tomato___tomato_yellow_leaf_curl_virus": dict(what=["This is a virus spread by whiteflies.", "The leaves curl up, turn yellow and stay small, and the plant stops growing."],
    treat=["There is no cure.", "Pull out and destroy sick plants early.", "Control whiteflies with yellow sticky traps or neem oil."],
    prevent=["Use resistant varieties.", "Cover seedbeds with a net.", "Keep weeds away."]),
 "tomato___tomato_mosaic_virus": dict(what=["This is a virus.", "The leaves show light and dark green patches and look twisted."],
    treat=["There is no cure.", "Pull out and burn sick plants.", "Wash your hands and tools with soap after touching sick plants."],
    prevent=["Use clean seed.", "Use resistant varieties.", "Wash your hands before touching the plants."]),
 "coffee___rust": dict(what=["This is a fungus.", "It makes yellow-orange powder spots under the leaf, and then the leaves fall."],
    treat=["Remove and bury the badly sick leaves.", "Spray a copper fungicide as the label says."],
    prevent=["Prune the coffee and the shade trees so air can pass through.", "Feed the trees well.", "Plant resistant varieties."]),
 "coffee___red_spider_mite": dict(what=["These are tiny insects under the leaf.", "The leaves turn bronze or reddish, mostly in dry and dusty weather."],
    treat=["Spray water under the leaves.", "Spray soap water or neem oil on the underside of the leaves.", "Use a miticide only if it is really needed. Follow the label."],
    prevent=["Keep dust away from the trees.", "Do not kill the helpful insects."]),
}
MESSAGES = {
 "not_plant": ["This does not look like a plant leaf.", "Please take the photo again."],
 "tips": ["Hold the phone close to one leaf.", "Use daylight.", "Keep the leaf in the center."],
 "unsure": ["I am not sure.", "Please take the photo again in good light with one leaf in the center."],
 "see_expert": ["If the problem gets worse, ask your agriculture officer or agro-dealer for help."],
 "disclaimer": ["This is a guide only."],
}
# crop names (hand-written; NLLB is unreliable for single nouns).  rn/rw/so/yo entries marked None fall back to English.
CROP_NAMES = {
 "maize":     dict(en="Maize", fr="Maïs", sw="Mahindi", rw="Ibigori", rn="Ibigori", so="Galley", yo="Àgbàdo"),
 "tomato":    dict(en="Tomato", fr="Tomate", sw="Nyanya", rw="Inyanya", rn="Inyanya", so="Yaanyo", yo="Tòmátì"),
 "potato":    dict(en="Potato", fr="Pomme de terre", sw="Viazi", rw="Ibirayi", rn="Ibirayi", so="Baradho", yo="Ọdùnkún"),
 "coffee":    dict(en="Coffee", fr="Café", sw="Kahawa", rw="Ikawa", rn="Ikawa", so="Bun", yo="Kọfí"),
 "pepper":    dict(en="Pepper", fr="Poivron", sw="Pilipili hoho", rw="Urusenda", rn="Urusenda", so="Barbare", yo="Ata"),
 "soybean":   dict(en="Soybean", fr="Soja", sw="Soya", rw="Soya", rn="Soya", so="Soya", yo="Soyà"),
 "apple":     dict(en="Apple", fr="Pomme", sw="Tufaha", rw="Pome", rn="Pome", so="Tufaax", yo="Ápù"),
 "orange":    dict(en="Orange", fr="Oranger", sw="Chungwa", rw="Icunga", rn="Icunga", so="Liin macaan", yo="Ọsàn"),
 "grape":     dict(en="Grape", fr="Raisin", sw="Zabibu", rw="Imizabibu", rn="Imizabibu", so="Canab", yo="Èso àjàrà"),
 "peach":     dict(en="Peach", fr="Pêche", sw="Pichi", rw="Pesheri", rn="Pesheri", so="Khooke", yo="Pìṣì"),
 "cherry":    dict(en="Cherry", fr="Cerise", sw="Cheri", rw="Cheri", rn="Cheri", so="Cherry", yo="Ṣẹ́rì"),
 "squash":    dict(en="Squash", fr="Courge", sw="Boga", rw="Ibihaza", rn="Ibihaza", so="Qaraha", yo="Elegede"),
 "strawberry":dict(en="Strawberry", fr="Fraise", sw="Stroberi", rw="Strawberi", rn="Strawberi", so="Strawberry", yo="Sitiroberi"),
 "blueberry": dict(en="Blueberry", fr="Myrtille", sw="Blueberi", rw="Blueberi", rn="Blueberi", so="Blueberry", yo="Blueberry"),
 "raspberry": dict(en="Raspberry", fr="Framboise", sw="Raspberi", rw="Raspberi", rn="Raspberi", so="Raspberry", yo="Raspberry"),
}
CROP_NAMES.update({
 "banana": dict(en="Banana", fr="Banane", sw="Ndizi", rw="Ibitoki", rn="Ibitoke", so="Muuz", yo="Ọ̀gẹ̀dẹ̀"),
 "cassava": dict(en="Cassava", fr="Manioc", sw="Muhogo", rw="Imyumbati", rn="Imyumbati", so="Rooti", yo="Ẹ̀gẹ́"),
 "bean": dict(en="Beans", fr="Haricots", sw="Maharage", rw="Ibishyimbo", rn="Ibiharage", so="Digir", yo="Ẹ̀wà"),
 "other_plant": dict(en="Another plant", fr="Une autre plante", sw="Mmea mwingine", rw="Ikindi gihingwa", rn="Ikindi gihingwa", so="Dhir kale", yo="Ọ̀gbìn mìíràn"),
})
# Human-written overrides: French + Swahili sentences and the disease-NAME glossary come from scripts/build_overrides.py.
# Disease names are NEVER machine translated (NLLB turned "Late blight" into "early pain" in Swahili).
over = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
def human(lg): return over.get(lg, {})
def pretty(label):
    c, d = label.split("___"); return d.replace("_", " ").strip().capitalize()
def disease_name(lg, label):
    key = "healthy" if label.endswith("healthy") else label
    N = over.get("_names", {})
    return N.get(lg, {}).get(key) or N.get("en", {}).get(key) or pretty(label)

# every class the vision model can output must have advice (guards against label-name drift)
_lab = OUT / "labels.json"
if _lab.exists():
    _need = {l for l in json.load(open(_lab))["labels"] if l != "not_plant" and not l.endswith("___unsupported")}
    assert _need == set(KB), f"KB mismatch: missing={_need - set(KB)} extra={set(KB) - _need}"
print("KB entries:", len(KB), "| messages:", len(MESSAGES))
sentences = sorted({s for e in KB.values() for k in ("what", "treat", "prevent") for s in e[k]} | {s for v in MESSAGES.values() for s in v})
print("unique sentences:", len(sentences), "| words:", sum(len(s.split()) for s in sentences))
print("human-written coverage:", {lg: f"{sum(s in human(lg) for s in sentences)}/{len(sentences)}" for lg in LANGS if lg != "en"})

# %% [markdown]
# ## 2 · Translate with NLLB-200 (FLORES-200 language codes)
# `facebook/nllb-200-distilled-600M` covers all 7 target languages. Beam search 4, sentence by sentence.
# *(First run downloads ≈ 2.4 GB. On CPU ≈ 20-30 min for all languages; a free Colab GPU ≈ 2 min.)*

# %%
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
dev = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(MODEL_ID, src_lang="eng_Latn")
nllb = AutoModelForSeq2SeqLM.from_pretrained(MODEL_ID, torch_dtype=torch.float16 if dev == "cuda" else torch.float32).to(dev).eval()
torch.set_num_threads(os.cpu_count() or 4)


@torch.no_grad()
def translate(texts, src, tgt, bs=24, beams=2):
    tok.src_lang = LANGS[src]; out = []
    for i in range(0, len(texts), bs):
        b = tok(texts[i:i + bs], return_tensors="pt", padding=True).to(dev)
        g = nllb.generate(**b, forced_bos_token_id=tok.convert_tokens_to_ids(LANGS[tgt]), num_beams=beams,
                          max_new_tokens=128, no_repeat_ngram_size=3)
        out += tok.batch_decode(g, skip_special_tokens=True)
    return out


CACHE = OUT / "nllb_cache.json"
cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
t0 = time.time()
for lg in LANGS:
    if lg == "en": continue
    todo = [s for s in sentences if s not in cache.get(lg, {}) and s not in human(lg)]
    if todo:
        cache.setdefault(lg, {}).update(dict(zip(todo, translate(todo, "en", lg))))
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"{lg}: {len([x for x in sentences if x not in human(lg)])} machine-translated, {len([x for x in sentences if x in human(lg)])} human ({time.time()-t0:.0f}s)")

# %% [markdown]
# ## 3 · Measure translation quality (no reference needed): **round-trip chrF**
# Translate each result back to English and compare with the original. Low scores = likely meaning drift →
# flagged for **native-speaker review**. This is a screening tool, not a guarantee.

# %%
try:
    from sacrebleu.metrics import CHRF
except ImportError:
    os.system(f"{sys.executable} -m pip -q install sacrebleu"); from sacrebleu.metrics import CHRF
chrf = CHRF()
BT = OUT / "nllb_backtrans.json"
bt = json.loads(BT.read_text(encoding="utf-8")) if BT.exists() else {}
quality, flagged = {}, {}
for lg in LANGS:
    if lg == "en": continue
    mt = [x for x in sentences if x not in human(lg)]
    if not mt:
        continue
    bt.setdefault(lg, {})
    todo = [x for x in mt if x not in bt[lg]]
    if todo:
        bt[lg].update(dict(zip(todo, translate([cache[lg][x] for x in todo], lg, "en", beams=1))))   # greedy: screening only
        BT.write_text(json.dumps(bt, ensure_ascii=False), encoding="utf-8")
    sc = {x: chrf.sentence_score(bt[lg][x], [x]).score for x in mt}
    quality[lg] = sum(sc.values()) / len(sc)
    flagged[lg] = sorted([x for x, v in sc.items() if v < 40], key=lambda x: sc[x])
print("mean round-trip chrF per language:", {k: round(v, 1) for k, v in quality.items()})
print("sentences flagged for review:", {k: len(v) for k, v in flagged.items()})

# %% [markdown]
# ## 4 · Apply native-speaker overrides, assemble the app bundle
# Put corrected sentences in `artifacts/translation_overrides.json` as `{"rw": {"<english sentence>": "<good Kinyarwanda>"}}`
# and re-run: overrides always win. The app shows a small *"machine translated"* note for languages without review.

# %%
def tr(lg, s): return s if lg == "en" else human(lg).get(s) or cache[lg][s]

advice = {}
for lg in LANGS:
    A = {"_msg": {k: [tr(lg, s) for s in v] for k, v in MESSAGES.items()}, "_crop": {c: over.get("_crops", {}).get(lg, {}).get(c) or n.get(lg) or n["en"] for c, n in CROP_NAMES.items()}, "labels": {}}
    for label, e in KB.items():
        A["labels"][label] = {"name": disease_name(lg, label), "what": [tr(lg, s) for s in e["what"]],
                              "treat": [tr(lg, s) for s in e["treat"]], "prevent": [tr(lg, s) for s in e["prevent"]]}
    advice[lg] = A
coverage = {lg: sum(s in human(lg) for s in sentences) / len(sentences) for lg in LANGS if lg != "en"}
bundle = {"version": 2, "languages": LANG_NAMES,
          "reviewed": {lg: lg == "en" or coverage[lg] >= 0.9 for lg in LANGS}, "quality_chrF": {k: round(v, 1) for k, v in quality.items()}, "advice": advice}
(OUT / "advice.json").write_text(json.dumps(bundle, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
(OUT / "review_sheet.json").write_text(json.dumps({lg: {x: cache[lg][x] for x in flagged[lg]} for lg in flagged}, ensure_ascii=False, indent=1), encoding="utf-8")
print("advice.json:", round((OUT / "advice.json").stat().st_size / 1024), "KB |", "review_sheet.json lists sentences to proof-read")
for lg in ("sw", "rw"):
    print(f"\nSample ({lg}, tomato late blight):", json.dumps(advice[lg]["labels"]["tomato___late_blight"], ensure_ascii=False)[:420])

# %% [markdown]
# ## 5 · (Optional, phase 2) Fine-tune NLLB on the corrected pairs
# Once native speakers have corrected ≥ 300 sentences per language you can LoRA-fine-tune the 600 M model:
#
# ```python
# from peft import LoraConfig, get_peft_model
# cfg = LoraConfig(r=16, lora_alpha=32, target_modules=["q_proj", "v_proj"], task_type="SEQ_2_SEQ_LM")
# peft_model = get_peft_model(nllb, cfg)       # ~2 % trainable params
# # train on (english → corrected translation) pairs for 3-5 epochs with Seq2SeqTrainer, lr 2e-4
# ```
# This lets you translate **new** advice (new crops/diseases) in-house.  Even then, keep shipping *pre-generated*
# text to phones: an int8 NLLB-600M (~600 MB) is too heavy for the target devices.  A distilled 60-100 M
# student (or MMS-TTS for audio read-out of the advice for low-literacy users) is the natural next step.
