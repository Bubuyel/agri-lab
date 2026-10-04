# %% [markdown]
# # 01 · Crop + disease vision model (offline, tiny, robust)
#
# **Goal:** a phone camera photo of a leaf → *which crop is it?* → *is it healthy or which disease?*
# and **"this is not a plant – please retake"** when it is not. Must run **offline** on cheap phones.
#
# ## Design decisions (and why)
# | Question | Decision | Reason |
# |---|---|---|
# | YOLO or classification? | **Image classification** (MobileNetV3-Small, ImageNet-pretrained) | The data has *one label per image* (no boxes). YOLO needs boxes and is 3-10× heavier. A classifier is the right tool; the Coffee polygons are only used to *crop the leaf*. |
# | Crop first? | **Two heads** on one backbone: `crop` (15 crops + `not_plant`) and `condition` (crop___disease) | Crop is the key decision. At inference the disease is **restricted to the predicted crop** → fewer silly answers. |
# | "Not a plant" with no such label? | Build a **`not_plant` class** from CIFAR-100 (non-plant classes) + synthetic junk (blank/dark/noise/skin-tone), and **hold out unseen classes** to measure it honestly. Plus a calibrated confidence gate ("unsure → retake"). | Open-set rejection needs negatives; evaluating on *unseen* negatives avoids fooling ourselves. |
# | Lab images vs real fields? | PlantVillage is shot on plain backgrounds. We use the **segmented** images to cut the leaf out and paste it on random backgrounds; add blur / low light / JPEG / noise / grayscale augmentation. The **grayscale** folder is reproduced by `RandomGrayscale` (same pixels, no need to double the dataset). | Closes the lab→field gap and mimics bad cameras. |
# | Leakage? | Split **by leaf ID**, not by file (PlantVillage has many photos of the same leaf). | Random file splits inflate accuracy to ~99.9 % and say nothing about new leaves. |
# | Size | 160 px input, MobileNetV3-Small (~2.5 M params) → **int8 ONNX ≈ 2-3 MB**. | Runs in ~50-150 ms on low-end phones. |
#
# **Run:** Colab/Kaggle GPU (≈ 20 min) *or* CPU with `MAX_PER_CLASS=150 EPOCHS=4` for a quick demo.

# %%
import os, re, io, json, math, time, random, warnings, itertools
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from PIL import Image, ImageFilter, ImageEnhance
import torch, torch.nn as nn, torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
import torchvision
from torchvision.models import mobilenet_v3_small, MobileNet_V3_Small_Weights

warnings.filterwarnings("ignore")
ROOT = Path(os.environ.get("AGRI_ROOT", Path.cwd()))
DATA = Path(os.environ.get("CROP_DATA", ROOT / "Data-crop-diseases"))
OUT = Path(os.environ.get("OUT_DIR", ROOT / "agri-ai" / "artifacts"))
WORK = Path(os.environ.get("WORK_DIR", ROOT / "agri-ai" / "work"))
OUT.mkdir(parents=True, exist_ok=True); WORK.mkdir(parents=True, exist_ok=True)

IMG = 160
MAX_PER_CLASS = int(os.environ.get("MAX_PER_CLASS", 0)) or None      # None = use everything
EPOCHS = int(os.environ.get("EPOCHS", 12))
BATCH = int(os.environ.get("BATCH", 64))
SEED = 42
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
random.seed(SEED); np.random.seed(SEED); torch.manual_seed(SEED)
NW = 0 if os.name == "nt" else min(8, os.cpu_count() or 2)   # Windows cannot fork DataLoader workers (Colab/Linux can)
print(f"device={DEVICE} img={IMG} epochs={EPOCHS} max/class={MAX_PER_CLASS} workers={NW}")

# %% [markdown]
# ## 1 · Inventory the data
# * `plantvillage-dataset/{color,grayscale,segmented}` – 38 classes, 3 renderings of the same 54 k photos.
# * `Coffee` (RoCoLe, Robusta) – 1 560 field photos with polygon annotations: `healthy`, `red_spider_mite`,
#   `rust_level_1..4`, `unhealthy` (the leaf outline when diseased). The research PDF explains rust severity levels.
#   We map to **3 classes**: healthy / rust (any level) / red spider mite, and **crop each leaf** from its polygon.

# %%
PV = DATA / "plantvillage-dataset"
CROP_KEY = {"Apple": "apple", "Blueberry": "blueberry", "Cherry_(including_sour)": "cherry", "Corn_(maize)": "maize",
            "Grape": "grape", "Orange": "orange", "Peach": "peach", "Pepper,_bell": "pepper", "Potato": "potato",
            "Raspberry": "raspberry", "Soybean": "soybean", "Squash": "squash", "Strawberry": "strawberry",
            "Tomato": "tomato"}
slug = lambda s: re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")


def leaf_group(fname: str) -> str:
    """'<uuid>___GH_HL Leaf 259.1.JPG' -> 'GH_HL Leaf 259' (same physical leaf, different photo angle)."""
    s = fname.split("___", 1)[-1]
    s = os.path.splitext(s)[0]
    return re.sub(r"\.\d+$", "", s)


rows = []
for d in sorted((PV / "color").iterdir()):
    crop_raw, cond_raw = d.name.split("___")
    crop = CROP_KEY[crop_raw]
    files = sorted(os.listdir(d))
    for f in files:
        seg = PV / "segmented" / d.name / (os.path.splitext(f)[0] + "_final_masked.jpg")
        rows.append((str(d / f), crop, f"{crop}___{slug(cond_raw)}", "pv", leaf_group(f) + "|" + d.name, str(seg), None))
pv = pd.DataFrame(rows, columns=["path", "crop", "label", "src", "group", "seg", "bbox"])
print("PlantVillage:", len(pv), "images |", pv.label.nunique(), "classes | leaf groups:", pv.group.nunique())

# --- Coffee (RoCoLe) ---------------------------------------------------------------------------
COF = DATA / "Coffee" / "ds"
crow, skipped = [], 0
for jf in sorted((COF / "ann").glob("*.json")):
    a = json.load(open(jf)); objs = a["objects"]
    titles = {o["classTitle"] for o in objs}
    if any(t.startswith("rust") for t in titles): lab = "coffee___rust"
    elif "red_spider_mite" in titles: lab = "coffee___red_spider_mite"
    elif "healthy" in titles: lab = "coffee___healthy"
    else: skipped += 1; continue
    leaf = [o for o in objs if o["classTitle"] in ("healthy", "unhealthy")] or objs
    pts = np.concatenate([np.array(o["points"]["exterior"]) for o in leaf])
    x0, y0 = pts.min(0); x1, y1 = pts.max(0)
    crow.append((str(COF / "img" / jf.name[:-5]), "coffee", lab, "coffee", jf.stem, None, (x0, y0, x1, y1)))
cof = pd.DataFrame(crow, columns=pv.columns)
print("Coffee:", len(cof), "images (skipped", skipped, "without a usable label) →", cof.label.value_counts().to_dict())

# --- Extra open data (scripts/fetch_extra_data.py): plants we do NOT support + real-world photos of ones we do ---------------
# Without these the network has never seen a banana leaf, so it confidently calls it "red spider mite" (a real field bug).
# Recognised-but-unsupported crops become their own classes → the app can say "this looks like banana, not supported yet".
UNSUPPORTED = ["banana", "bean", "cassava", "other_plant"]
PLANTDOC = {  # PlantDoc class name (lower-case) → our label
    "apple scab leaf": "apple___apple_scab", "apple leaf": "apple___healthy", "apple rust leaf": "apple___cedar_apple_rust",
    "bell_pepper leaf": "pepper___healthy", "bell_pepper leaf spot": "pepper___bacterial_spot", "blueberry leaf": "blueberry___healthy",
    "cherry leaf": "cherry___healthy", "corn gray leaf spot": "maize___cercospora_leaf_spot_gray_leaf_spot", "corn leaf blight": "maize___northern_leaf_blight",
    "corn rust leaf": "maize___common_rust", "peach leaf": "peach___healthy", "potato leaf": "potato___healthy",
    "potato leaf early blight": "potato___early_blight", "potato leaf late blight": "potato___late_blight", "raspberry leaf": "raspberry___healthy",
    "soyabean leaf": "soybean___healthy", "squash powdery mildew leaf": "squash___powdery_mildew", "strawberry leaf": "strawberry___healthy",
    "tomato early blight leaf": "tomato___early_blight", "tomato septoria leaf spot": "tomato___septoria_leaf_spot", "tomato leaf": "tomato___healthy",
    "tomato leaf bacterial spot": "tomato___bacterial_spot", "tomato leaf late blight": "tomato___late_blight", "tomato leaf mosaic virus": "tomato___tomato_mosaic_virus",
    "tomato leaf yellow virus": "tomato___tomato_yellow_leaf_curl_virus", "tomato mold leaf": "tomato___leaf_mold",
    "tomato two spotted spider mites leaf": "tomato___spider_mites_two_spotted_spider_mite", "grape leaf": "grape___healthy", "grape leaf black rot": "grape___black_rot"}
EXTRA = Path(os.environ.get("EXTRA_DIR", ROOT / "agri-ai" / "work" / "extra"))
ex_rows = []
if (EXTRA / "manifest.csv").exists():
    man = pd.read_csv(EXTRA / "manifest.csv")
    for r in man.itertuples():
        if r.source == "plantdoc":
            lab = PLANTDOC.get(re.sub(r"\s+", " ", str(r.label).strip().lower()))
            if lab: ex_rows.append((r.path, lab.split("___")[0], lab, "plantdoc", "pd|" + Path(r.path).stem, None, None))
        else:
            ex_rows.append((r.path, r.crop, f"{r.crop}___unsupported", "extra", "ex|" + r.source + "|" + Path(r.path).stem, None, None))
else:
    print("NOTE: no extra data found - run scripts/fetch_extra_data.py to teach the model about banana, cassava, beans and other plants")
extra = pd.DataFrame(ex_rows, columns=pv.columns)
print("extra images:", extra.src.value_counts().to_dict(), "| unsupported crops:", extra[extra.src == "extra"].crop.value_counts().to_dict())

meta = pd.concat([pv, cof, extra], ignore_index=True)
if MAX_PER_CLASS:
    cap = lambda lab: MAX_PER_CLASS * (4 if lab.endswith("___unsupported") else 1)      # the "unsupported" buckets pool many plants
    lab_part = meta[meta.src != "plantdoc"].sample(frac=1, random_state=SEED)
    # real-world (PlantDoc) photos are always kept in full: they are the scarce, valuable field-domain data
    meta = pd.concat([pd.concat([g.head(cap(l)) for l, g in lab_part.groupby("label")]), meta[meta.src == "plantdoc"]])
meta = meta.reset_index(drop=True)

# %% [markdown]
# ## 2 · Leaf-grouped, class-stratified split (70 / 15 / 15)

# %%
def group_split(df, fr=(0.70, 0.15, 0.15), seed=SEED):
    rng = np.random.RandomState(seed); split = pd.Series("train", index=df.index)
    for lab, g in df.groupby("label"):
        groups = g.group.unique(); rng.shuffle(groups)
        n = len(groups); a = max(1, int(round(n * fr[0]))); b = max(a + 1, int(round(n * (fr[0] + fr[1])))) if n > 2 else n
        gv, gt = set(groups[a:b]), set(groups[b:])
        split[g.index[g.group.isin(gv)]] = "val"; split[g.index[g.group.isin(gt)]] = "test"
    return split


meta["split"] = group_split(meta)
print(pd.crosstab(meta.src, meta.split))
assert not (set(meta[meta.split == "train"].group) & set(meta[meta.split == "test"].group)), "leaf leakage!"

# %% [markdown]
# ## 3 · `not_plant` negatives (with a **held-out unseen** set for honest open-set testing)
# CIFAR-100 minus every plant-like class. 15 further classes are *never* used for training and form the
# **OOD test**. We add synthetic junk (blank wall, dark lens, noise, skin tone, stripes).

# %%
from torchvision.datasets import CIFAR100
cifar_tr = CIFAR100(str(WORK / "cifar"), train=True, download=True)
cifar_te = CIFAR100(str(WORK / "cifar"), train=False, download=True)
PLANTY = {"apple", "orange", "pear", "sweet_pepper", "mushroom", "maple_tree", "oak_tree", "palm_tree", "pine_tree",
          "willow_tree", "sunflower", "rose", "poppy", "orchid", "tulip", "forest", "plain", "cloud"}
names = cifar_tr.classes
cand = [i for i, n in enumerate(names) if n not in PLANTY]
rs = np.random.RandomState(7); ood_cls = set(rs.choice(cand, 15, replace=False).tolist())
id_cls = [i for i in cand if i not in ood_cls]
print("OOD (never trained) classes:", sorted(names[i] for i in ood_cls))


def pick(ds, classes, n, seed):
    t = np.array(ds.targets); r = np.random.RandomState(seed)
    idx = np.concatenate([r.choice(np.nonzero(t == c)[0], min(n, (t == c).sum()), replace=False) for c in classes])
    return ds.data[idx]


def up(a):  # 32x32 -> IMG, bicubic
    return np.asarray(Image.fromarray(a).resize((IMG, IMG), Image.BICUBIC))


def synth(i):
    """Deterministic synthetic non-plant frame."""
    r = np.random.RandomState(10_000 + i); kind = i % 6
    yy, xx = np.mgrid[0:IMG, 0:IMG] / IMG
    if kind == 0:   img = np.ones((IMG, IMG, 3)) * r.uniform(0, 255, 3)                                  # flat colour (wall/sky)
    elif kind == 1: img = (xx[..., None] * r.uniform(0, 255, 3) + yy[..., None] * r.uniform(0, 255, 3)) / 2  # gradient
    elif kind == 2: img = np.ones((IMG, IMG, 3)) * r.uniform(0, 40)                                      # lens covered / night
    elif kind == 3: img = r.uniform(0, 255, (IMG, IMG, 3))                                               # sensor noise
    elif kind == 4: img = np.ones((IMG, IMG, 3)) * np.array([r.uniform(150, 235), r.uniform(100, 180), r.uniform(80, 150)])  # skin-ish
    else:           img = (np.sin((xx + yy) * r.uniform(10, 60))[..., None] * 100 + 128) * r.uniform(.5, 1, 3)  # stripes/fabric
    img = np.clip(img + r.normal(0, r.uniform(0, 12), img.shape), 0, 255).astype("uint8")
    return np.asarray(Image.fromarray(img).filter(ImageFilter.GaussianBlur(r.uniform(0, 3))))


NEG_N = max(40, int(0.12 * (meta.split == "train").sum() / max(1, len(id_cls))) )   # per class → ≈12 % of train
neg = {"train": pick(cifar_tr, id_cls, NEG_N, 1)}
tmp = pick(cifar_te, id_cls, max(10, NEG_N // 4), 2)
neg["val"], neg["test"] = tmp[: len(tmp) // 2], tmp[len(tmp) // 2:]
ood_imgs = pick(cifar_te, sorted(ood_cls), 60, 3)
n_syn = {"train": 400, "val": 80, "test": 80}
NEG_ROWS, NEG_ARR = [], []
for sp in ("train", "val", "test"):
    for a in neg[sp]: NEG_ARR.append(up(a)); NEG_ROWS.append((sp, "cifar"))
    for j in range(n_syn[sp]): NEG_ARR.append(synth({"train": 0, "val": 5000, "test": 9000}[sp] + j)); NEG_ROWS.append((sp, "synthetic"))
OOD_ARR = np.stack([up(a) for a in ood_imgs]); OOD_ARR = np.concatenate([OOD_ARR, np.stack([synth(20000 + j) for j in range(200)])])
NEG_ARR = np.stack(NEG_ARR); print("not_plant:", pd.Series([r[0] for r in NEG_ROWS]).value_counts().to_dict(), "| OOD test:", len(OOD_ARR))

# %% [markdown]
# ## 4 · Pre-cache everything at 160 px (fast training) incl. leaf masks for background replacement

# %%
LABELS = sorted(meta.label.unique()) + ["not_plant"]
CROPS = sorted(meta.crop.unique()) + ["not_plant"]
l2i = {l: i for i, l in enumerate(LABELS)}; c2i = {c: i for i, c in enumerate(CROPS)}
lab2crop = np.array([c2i[l.split("___")[0]] if l != "not_plant" else c2i["not_plant"] for l in LABELS])
print(len(CROPS), "crop outputs |", len(LABELS), "condition outputs")


def load_one(r):
    im = Image.open(r.path); im.draft("RGB", (IMG * 4, IMG * 4)); im = im.convert("RGB")
    if r.bbox is not None:                       # coffee: square crop around the leaf polygon, +10 %
        w, h = im.size; sx = w / (Image.open(r.path).size[0]); x0, y0, x1, y1 = [v * sx for v in r.bbox]
        cx, cy, s = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, y1 - y0) * 1.1
        s = min(s, min(w, h)); cx = min(max(cx, s / 2), w - s / 2); cy = min(max(cy, s / 2), h - s / 2)
        im = im.crop((int(cx - s / 2), int(cy - s / 2), int(cx + s / 2), int(cy + s / 2)))
    x = np.asarray(im.resize((IMG, IMG), Image.BICUBIC))
    m = np.zeros((IMG, IMG), "uint8")
    if r.seg and os.path.exists(r.seg):          # PlantVillage leaf mask from the segmented rendering
        sg = np.asarray(Image.open(r.seg).convert("L").resize((IMG, IMG), Image.BILINEAR))
        m = (sg > 12).astype("uint8") * 255
    return x, m


def build_cache(df, name):
    p = WORK / f"{name}_{IMG}_{len(df)}.npz"
    if p.exists():
        z = np.load(p); return z["x"], z["m"]
    t0 = time.time()
    with ThreadPoolExecutor(max(NW, 8)) as ex:
        out = list(ex.map(load_one, df.itertuples()))
    x = np.stack([o[0] for o in out]); m = np.stack([o[1] for o in out])
    np.savez(p, x=x, m=m); print(f"cached {name}: {x.shape} in {time.time()-t0:.0f}s"); return x, m


X, MASK = build_cache(meta, "main")
neg_df = pd.DataFrame(NEG_ROWS, columns=["split", "kind"])
X = np.concatenate([X, NEG_ARR]); MASK = np.concatenate([MASK, np.zeros((len(NEG_ARR), IMG, IMG), "uint8")])
all_meta = pd.concat([meta[["label", "crop", "split", "src"]],
                      pd.DataFrame({"label": "not_plant", "crop": "not_plant", "split": neg_df.split, "src": neg_df.kind})], ignore_index=True)
Y_LAB = all_meta.label.map(l2i).values; Y_CROP = all_meta.crop.map(c2i).values
BG_BANK = NEG_ARR[[i for i, r in enumerate(NEG_ROWS) if r[0] == "train"]]       # only TRAIN negatives are used as backgrounds
print("total images:", len(X), "| train/val/test:", all_meta.split.value_counts().to_dict())

# %% [markdown]
# ## 5 · Augmentation = the "bad phone in a real field" simulator
# Train: random background swap, rotation/zoom/flip, exposure (dark → blown-out), colour cast, blur, motion blur,
# sensor noise, JPEG artefacts, low-resolution up-scaling, grayscale. **Hue is barely touched** (colour carries the disease signal).
# `mode="fieldsim"` applies a *fixed-seed strong* version to val/test → a second, tougher test set.

# %%
MEAN = np.array([0.485, 0.456, 0.406], "float32"); STD = np.array([0.229, 0.224, 0.225], "float32")


def jpeg(im, q):
    b = io.BytesIO(); im.save(b, "JPEG", quality=int(q)); b.seek(0); return Image.open(b).convert("RGB")


def motion_blur(im, k, ang):
    kern = np.zeros((k, k), "float32"); kern[k // 2, :] = 1
    kim = Image.fromarray((kern * 255).astype("uint8")).rotate(ang, resample=Image.BILINEAR)
    kk = np.asarray(kim, "float32"); kk /= max(kk.sum(), 1)
    a = np.asarray(im, "float32"); pad = k // 2
    ap = np.pad(a, ((pad, pad), (pad, pad), (0, 0)), mode="reflect")
    out = np.zeros_like(a)
    for i in range(k):
        for j in range(k):
            if kk[i, j] > 0: out += kk[i, j] * ap[i:i + a.shape[0], j:j + a.shape[1]]
    return Image.fromarray(out.clip(0, 255).astype("uint8"))


def augment(x, m, y_is_plant, rng, mode="train"):
    s = 1.0 if mode == "fieldsim" else 0.0                       # fieldsim: apply every degradation with high prob
    pr = (lambda p: rng.rand() < (max(p, 0.8) if s else p))
    im = Image.fromarray(x)
    if y_is_plant and m.any() and pr(0.7):                       # background swap using the segmented leaf mask
        bg = Image.fromarray(BG_BANK[rng.randint(len(BG_BANK))]).resize((IMG, IMG))
        bg = ImageEnhance.Color(bg).enhance(rng.uniform(0.3, 1.5))
        tint = np.array([rng.uniform(.5, 1.1), rng.uniform(.5, 1.1), rng.uniform(.4, 1.0)], "float32")
        bg = Image.fromarray((np.asarray(bg, "float32") * tint).clip(0, 255).astype("uint8"))
        mk = Image.fromarray(m).filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 2.0)))
        im = Image.composite(im, bg, mk)
    # geometry
    ang = rng.uniform(0, 360); sc = rng.uniform(0.65, 1.0)
    w = int(IMG * sc); x0 = rng.randint(0, IMG - w + 1); y0 = rng.randint(0, IMG - w + 1)
    im = im.rotate(ang, resample=Image.BILINEAR, fillcolor=(int(rng.randint(256)),) * 3).crop((x0, y0, x0 + w, y0 + w)).resize((IMG, IMG), Image.BILINEAR)
    if rng.rand() < .5: im = im.transpose(Image.FLIP_LEFT_RIGHT)
    # exposure / colour
    g = rng.uniform(0.35, 0.8) if pr(0.25) else (rng.uniform(1.3, 1.9) if pr(0.12) else 1.0)       # dark / overexposed
    a = (np.asarray(im, "float32") / 255) ** g
    a = a * rng.uniform(0.8, 1.2, 3)                                                                # white-balance cast
    im = Image.fromarray((a.clip(0, 1) * 255).astype("uint8"))
    im = ImageEnhance.Contrast(im).enhance(rng.uniform(0.6, 1.3)); im = ImageEnhance.Color(im).enhance(rng.uniform(0.6, 1.3))
    if pr(0.08): im = im.convert("L").convert("RGB")                                                # cheap grayscale cameras
    # camera degradation
    if pr(0.35): im = im.filter(ImageFilter.GaussianBlur(rng.uniform(0.6, 2.5)))
    if pr(0.12): im = motion_blur(im, int(rng.choice([5, 7, 9])), rng.uniform(0, 180))
    if pr(0.30):                                                                                    # low-res sensor
        f = rng.uniform(0.3, 0.7); im = im.resize((int(IMG * f), int(IMG * f)), Image.BILINEAR).resize((IMG, IMG), Image.BILINEAR)
    if pr(0.30):
        a = np.asarray(im, "float32"); a += rng.normal(0, rng.uniform(3, 18), a.shape); im = Image.fromarray(a.clip(0, 255).astype("uint8"))
    if pr(0.40): im = jpeg(im, rng.uniform(15, 80))
    return np.asarray(im)


def to_tensor(a):
    return torch.from_numpy(((a.astype("float32") / 255 - MEAN) / STD).transpose(2, 0, 1).copy())


class DS(Dataset):
    def __init__(self, idx, mode):
        self.idx, self.mode = np.asarray(idx), mode
    def __len__(self): return len(self.idx)
    def __getitem__(self, i):
        j = self.idx[i]
        if self.mode == "clean":
            a = X[j]
        else:
            rng = np.random.RandomState(j * 7 + 13) if self.mode == "fieldsim" else np.random.RandomState()
            a = augment(X[j], MASK[j], Y_LAB[j] != l2i["not_plant"], rng, self.mode)
        return to_tensor(a), int(Y_CROP[j]), int(Y_LAB[j])


idx = {s: np.nonzero(all_meta.split.values == s)[0] for s in ("train", "val", "test")}
# class-balanced sampling (sqrt inverse frequency) so rare classes (e.g. potato healthy: 152) are seen enough
cnt = np.bincount(Y_LAB[idx["train"]], minlength=len(LABELS)); wcls = 1 / np.sqrt(np.maximum(cnt, 1))
sampler = WeightedRandomSampler(wcls[Y_LAB[idx["train"]]], num_samples=min(len(idx["train"]), 30000), replacement=True)
dl_train = DataLoader(DS(idx["train"], "train"), BATCH, sampler=sampler, num_workers=NW, drop_last=True, persistent_workers=NW > 0)
mk = lambda s, mode: DataLoader(DS(idx[s], mode), 128, shuffle=False, num_workers=NW)
dl = {"val": mk("val", "clean"), "val_fs": mk("val", "fieldsim"), "test": mk("test", "clean"), "test_fs": mk("test", "fieldsim")}

# visual sanity check of what the network sees
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ds_vis = DS(idx["train"][:: max(1, len(idx["train"]) // 16)][:16], "train")
fig, ax = plt.subplots(2, 8, figsize=(16, 4.4))
for k, a_ in enumerate(ax.ravel()):
    t, yc, yl = ds_vis[k]; a_.imshow((t.numpy().transpose(1, 2, 0) * STD + MEAN).clip(0, 1)); a_.set_title(LABELS[yl][:18], fontsize=7); a_.axis("off")
plt.tight_layout(); plt.savefig(OUT / "vision_aug_samples.png", dpi=90); plt.close()

# %% [markdown]
# ## 6 · Model: MobileNetV3-Small + two heads

# %%
class Net(nn.Module):
    def __init__(self, n_crop, n_lab, pretrained=True):
        super().__init__()
        try:
            bb = mobilenet_v3_small(weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None)
        except Exception as e:
            print("pretrained weights unavailable → random init (", e, ")"); bb = mobilenet_v3_small(weights=None)
        self.features, self.pool = bb.features, nn.AdaptiveAvgPool2d(1)
        d = 576
        self.drop = nn.Dropout(0.2)
        self.crop_head, self.lab_head = nn.Linear(d, n_crop), nn.Linear(d, n_lab)

    def forward(self, x):
        f = self.drop(self.pool(self.features(x)).flatten(1))
        return self.crop_head(f), self.lab_head(f)


model = Net(len(CROPS), len(LABELS)).to(DEVICE)
print(f"params: {sum(p.numel() for p in model.parameters())/1e6:.2f} M")
LAB2CROP = torch.tensor(lab2crop, device=DEVICE)


def constrained_labels(crop_logits, lab_logits):
    """Restrict the disease decision to classes of the predicted crop."""
    pc = crop_logits.argmax(1)
    allowed = (LAB2CROP[None, :] == pc[:, None])
    return lab_logits.masked_fill(~allowed, -1e4).argmax(1)


@torch.no_grad()
def predict(m, loader):
    m.eval(); C, L, yc, yl = [], [], [], []
    for xb, c, l in loader:
        a, b = m(xb.to(DEVICE)); C.append(a.cpu()); L.append(b.cpu()); yc.append(c); yl.append(l)
    return torch.cat(C), torch.cat(L), torch.cat(yc), torch.cat(yl)


from sklearn.metrics import f1_score
def quick_eval(m, loader):
    C, L, yc, yl = predict(m, loader)
    pl = constrained_labels(C.to(DEVICE), L.to(DEVICE)).cpu()
    return dict(crop_acc=(C.argmax(1) == yc).float().mean().item(), cond_acc=(pl == yl).float().mean().item(),
                cond_f1=f1_score(yl, pl, average="macro"))

# %% [markdown]
# ## 7 · Train (AdamW + OneCycle, label smoothing, AMP). Model selection on **val field-sim macro-F1**.

# %%
opt = torch.optim.AdamW([{"params": model.features.parameters(), "lr": 1e-3}, {"params": list(model.crop_head.parameters()) + list(model.lab_head.parameters()), "lr": 3e-3}], weight_decay=1e-4)
steps = EPOCHS * len(dl_train)
sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[2e-3, 6e-3], total_steps=steps, pct_start=0.2)
scaler = torch.amp.GradScaler(enabled=DEVICE == "cuda")
best, best_state, hist = -1, None, []
for ep in range(EPOCHS):
    model.train(); t0 = time.time(); tl = 0; n = 0
    for xb, yc, yl in dl_train:
        xb, yc, yl = xb.to(DEVICE), yc.to(DEVICE), yl.to(DEVICE)
        with torch.autocast(DEVICE, enabled=DEVICE == "cuda"):
            a, b = model(xb)
            loss = F.cross_entropy(a, yc, label_smoothing=0.05) + F.cross_entropy(b, yl, label_smoothing=0.1)
        opt.zero_grad(set_to_none=True); scaler.scale(loss).backward(); scaler.step(opt); scaler.update(); sched.step()
        tl += loss.item() * len(xb); n += len(xb)
    v, vf = quick_eval(model, dl["val"]), quick_eval(model, dl["val_fs"])
    hist.append(dict(epoch=ep + 1, loss=tl / n, **{f"val_{k}": x for k, x in v.items()}, **{f"valfs_{k}": x for k, x in vf.items()}))
    print(f"ep{ep+1:02d} loss {tl/n:.3f} | val crop {v['crop_acc']:.3f} cond {v['cond_acc']:.3f} | field-sim crop {vf['crop_acc']:.3f} cond {vf['cond_acc']:.3f} F1 {vf['cond_f1']:.3f} | {time.time()-t0:.0f}s")
    if vf["cond_f1"] > best:
        best = vf["cond_f1"]; best_state = {k: v_.detach().cpu().clone() for k, v_ in model.state_dict().items()}
model.load_state_dict(best_state); pd.DataFrame(hist).to_csv(OUT / "vision_training_history.csv", index=False)

# %% [markdown]
# ## 8 · Evaluation on the untouched TEST split
# Reported on **clean** and **field-sim** images, per class, with calibration and the open-set (non-plant) test.

# %%
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score
res = {}
for nm in ("test", "test_fs"):
    C, L, yc, yl = predict(model, dl[nm])
    pl = constrained_labels(C.to(DEVICE), L.to(DEVICE)).cpu()
    res[nm] = dict(crop_acc=float((C.argmax(1) == yc).float().mean()), cond_acc=float((pl == yl).float().mean()),
                   cond_macro_f1=float(f1_score(yl, pl, average="macro")))
    print(nm, {k: round(v, 4) for k, v in res[nm].items()})
    if nm == "test_fs":
        rep = classification_report(yl, pl, labels=range(len(LABELS)), target_names=LABELS, output_dict=True, zero_division=0)
        pd.DataFrame(rep).T.to_csv(OUT / "vision_per_class_report.csv")
        worst = sorted(((v["f1-score"], k) for k, v in rep.items() if k in LABELS and v["support"] > 0))[:6]
        print("weakest classes (F1):", [(k, round(f, 2)) for f, k in worst])
        cm = confusion_matrix(yl, pl, labels=range(len(LABELS))); np.fill_diagonal(cm, 0)
        top = np.dstack(np.unravel_index(np.argsort(-cm.ravel())[:5], cm.shape))[0]
        print("top confusions:", [(LABELS[a], LABELS[b], int(cm[a, b])) for a, b in top])
        C_fs, L_fs, yc_fs, yl_fs = C, L, yc, yl

# --- calibration (temperature scaling on VAL field-sim) + thresholds ------------------------------
Cv, Lv, ycv, ylv = predict(model, dl["val_fs"])
Tc = torch.nn.Parameter(torch.ones(1)); optT = torch.optim.LBFGS([Tc], lr=0.1, max_iter=60)
def _nll():
    optT.zero_grad(); l = F.cross_entropy(Cv / Tc, ycv); l.backward(); return l
optT.step(_nll); T = float(Tc.detach().clamp(0.5, 5)); print("crop temperature:", round(T, 3))


def ece(p, y, bins=10):
    conf, pred = p.max(1); acc = (pred == y).float(); e = 0
    for lo in np.linspace(0, 1, bins, endpoint=False):
        s = (conf > lo) & (conf <= lo + 1 / bins)
        if s.any(): e += s.float().mean() * abs(acc[s].mean() - conf[s].mean())
    return float(e)

print("ECE crop head  before/after T:", round(ece(F.softmax(C_fs, 1), yc_fs), 4), round(ece(F.softmax(C_fs / T, 1), yc_fs), 4))

# open-set: how well do we reject *unseen* non-plants?  (OOD never seen in training)
class OODDS(Dataset):
    def __len__(self): return len(OOD_ARR)
    def __getitem__(self, i):
        a = augment(OOD_ARR[i], np.zeros((IMG, IMG), "uint8"), False, np.random.RandomState(i), "fieldsim"); return to_tensor(a), 0, 0
Co, Lo, _, _ = predict(model, DataLoader(OODDS(), 128))
NP = c2i["not_plant"]
score = lambda C_: F.softmax(C_ / T, 1)
p_np_in, p_np_ood = score(C_fs)[:, NP], score(Co)[:, NP]
UNS = torch.tensor([c2i[c] for c in UNSUPPORTED if c in c2i])
is_uns = torch.isin(yc_fs, UNS)
is_plant_in = (yc_fs != NP) & ~is_uns           # real plants of SUPPORTED crops (the ones we must answer)
auroc = roc_auc_score(np.r_[np.zeros(is_plant_in.sum()), np.ones(len(p_np_ood))], np.r_[p_np_in[is_plant_in], p_np_ood])
print(f"not-plant detection AUROC (real plants vs UNSEEN non-plants, field-sim): {auroc:.3f}")

# decision rule: reject if P(not_plant) >= TH_NP  OR  max crop prob < TH_CONF  ("unsure, retake")
def decide(Cc, th_np, th_conf):
    p = score(Cc); return (p[:, NP] >= th_np) | (p.max(1).values < th_conf)

MAX_RETAKE = 0.15            # at most 15 % of real-plant photos may be answered with "unsure, retake"
best_rule, rules = None, []
for th_conf in np.arange(0.30, 0.96, 0.05):
    rej = decide(C_fs[is_plant_in], 0.5, th_conf)
    rej_in = rej.float().mean().item()
    kept = ~rej
    acc_acc = ((C_fs[is_plant_in].argmax(1) == yc_fs[is_plant_in]) & kept).float().sum().item() / max(1, kept.sum().item())
    rej_ood = decide(Co, 0.5, th_conf).float().mean().item()
    rules.append((float(th_conf), rej_in, rej_ood, acc_acc))
ok = [r for r in rules if r[1] <= MAX_RETAKE]
best_rule = max(ok, key=lambda r: r[2]) if ok else min(rules, key=lambda r: r[1])   # weak model: least annoying gate
TH_CONF = best_rule[0]
# open-set report: a photo of an UNSUPPORTED plant must never be answered with a disease of a supported crop
if is_uns.any():
    pcrop = score(C_fs).argmax(1)
    flagged = torch.isin(pcrop, torch.cat([UNS, torch.tensor([NP])])) | (score(C_fs).max(1).values < TH_CONF)
    wrong = ~flagged
    per = {UNSUPPORTED[i]: round(float(flagged[yc_fs == c2i[UNSUPPORTED[i]]].float().mean()), 3) for i in range(len(UNSUPPORTED)) if UNSUPPORTED[i] in c2i and (yc_fs == c2i[UNSUPPORTED[i]]).any()}
    OPEN_SET = {"unsupported_plants_flagged": round(float(flagged[is_uns].float().mean()), 4), "per_crop": per,
                "wrongly_answered_as_supported": round(float(wrong[is_uns].float().mean()), 4)}
    print("open-set (unsupported plants → \"not yet supported\"/unsure):", OPEN_SET)
else:
    OPEN_SET = {}
print(f"chosen confidence gate {TH_CONF:.2f}: rejects {best_rule[1]*100:.1f}% of real plants (they are asked to retake), "
      f"catches {best_rule[2]*100:.1f}% of unseen non-plants; accuracy on accepted plants {best_rule[3]*100:.1f}%")

# %% [markdown]
# ## 9 · Robustness sweep – how bad can the photo be?
# Accuracy of crop & condition while *one* degradation increases (applied on top of the clean test set).

# %%
def sweep(kind, levels, n=600):
    ids = np.random.RandomState(0).choice(idx["test"], min(n, len(idx["test"])), replace=False); out = []
    for lv in levels:
        xs = []
        for j in ids:
            im = Image.fromarray(X[j])
            if kind == "blur": im = im.filter(ImageFilter.GaussianBlur(lv))
            elif kind == "brightness": im = Image.fromarray(((np.asarray(im, "float32") / 255) ** (1 / lv) * 255).clip(0, 255).astype("uint8"))
            elif kind == "jpeg": im = jpeg(im, lv)
            elif kind == "noise": a = np.asarray(im, "float32") + np.random.RandomState(1).normal(0, lv, (IMG, IMG, 3)); im = Image.fromarray(a.clip(0, 255).astype("uint8"))
            xs.append(to_tensor(np.asarray(im)))
        xb = torch.stack(xs).to(DEVICE); model.eval()
        with torch.no_grad(): a, b = model(xb)
        pl = constrained_labels(a, b).cpu()
        out.append((lv, float((a.argmax(1).cpu() == torch.tensor(Y_CROP[ids])).float().mean()), float((pl == torch.tensor(Y_LAB[ids])).float().mean())))
    return out

rob = {"blur_sigma": sweep("blur", [0, 1, 2, 3, 4]), "brightness_gamma": sweep("brightness", [0.3, 0.5, 1, 2, 3]),
       "jpeg_quality": sweep("jpeg", [90, 50, 25, 10]), "noise_std": sweep("noise", [0, 10, 25, 40])}
for k, v in rob.items(): print(f"{k:18s}", " ".join(f"{lv}:{c:.2f}/{d:.2f}" for lv, c, d in v), "   (level: crop/condition acc)")

# %% [markdown]
# ## 10 · Export for the app
# 1. `crop_disease_fp32.onnx`  2. **`crop_disease_int8.onnx`** (static int8 quantisation, calibrated on val images)
# 3. best-effort **`.tflite`** (for a future Flutter / native build) 4. `labels.json` = labels + thresholds + preprocessing contract.
#
# **Preprocessing contract (the app must match):** centre-square crop → resize **160×160** (bilinear) → RGB/255 →
# `(x − mean)/std` with ImageNet mean/std → NCHW float32. Outputs: `crop_logits[16]`, `lab_logits[42]`.

# %%
import onnx, onnxruntime as ort
model.eval().cpu()
dummy = torch.randn(1, 3, IMG, IMG)
fp32 = OUT / "crop_disease_fp32.onnx"
torch.onnx.export(model, dummy, str(fp32), input_names=["image"], output_names=["crop_logits", "lab_logits"],
                  dynamic_axes={"image": {0: "n"}, "crop_logits": {0: "n"}, "lab_logits": {0: "n"}}, opset_version=17, dynamo=False)
onnx.checker.check_model(onnx.load(str(fp32)))
sess = ort.InferenceSession(str(fp32), providers=["CPUExecutionProvider"])
with torch.no_grad(): ref = model(dummy)
o = sess.run(None, {"image": dummy.numpy()})
print("onnx vs torch max diff:", float(np.abs(o[0] - ref[0].numpy()).max()), float(np.abs(o[1] - ref[1].numpy()).max()))

# %%
from onnxruntime.quantization import quantize_static, CalibrationDataReader, QuantType, QuantFormat
cal_ids = np.random.RandomState(3).choice(idx["val"], min(300, len(idx["val"])), replace=False)
class Reader(CalibrationDataReader):
    def __init__(self):
        rng = np.random.RandomState(5)
        self.it = iter([{"image": to_tensor(X[j] if k % 2 == 0 else augment(X[j], MASK[j], Y_LAB[j] != l2i["not_plant"], rng, "fieldsim")).numpy()[None]} for k, j in enumerate(cal_ids)])
    def get_next(self): return next(self.it, None)

int8 = OUT / "crop_disease_int8.onnx"
quantize_static(str(fp32), str(int8), Reader(), quant_format=QuantFormat.QDQ, per_channel=True,
                activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8)

def onnx_eval(path, loader_name="test_fs", limit=800):
    s = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"]); ci, li, yc_, yl_ = [], [], [], []
    ids = idx["test"][:limit]; ds = DS(ids, "fieldsim" if loader_name == "test_fs" else "clean")
    for i in range(len(ds)):
        t, c, l = ds[i]; a, b = s.run(None, {"image": t.numpy()[None]}); ci.append(a[0]); li.append(b[0]); yc_.append(c); yl_.append(l)
    C_, L_ = torch.tensor(np.array(ci)), torch.tensor(np.array(li))
    pl = constrained_labels(C_.to(DEVICE), L_.to(DEVICE)).cpu()
    return float((C_.argmax(1) == torch.tensor(yc_)).float().mean()), float((pl == torch.tensor(yl_)).float().mean())

a32, a8 = onnx_eval(fp32), onnx_eval(int8)
print(f"field-sim test (crop/cond)  fp32: {a32[0]:.3f}/{a32[1]:.3f}   int8: {a8[0]:.3f}/{a8[1]:.3f}")
sz = lambda p: p.stat().st_size / 1e6
print(f"size  fp32 {sz(fp32):.2f} MB | int8 {sz(int8):.2f} MB")
USE_INT8 = (a32[1] - a8[1]) <= 0.02
FINAL = int8 if USE_INT8 else fp32
print("shipping:", FINAL.name)
s = ort.InferenceSession(str(FINAL), providers=["CPUExecutionProvider"], sess_options=(lambda o: (setattr(o, "intra_op_num_threads", 1), o)[1])(ort.SessionOptions()))
t0 = time.time()
for _ in range(30): s.run(None, {"image": dummy.numpy()})
print(f"CPU latency (1 thread): {(time.time()-t0)/30*1000:.0f} ms / image")

# %%
# best-effort TFLite (Linux/Colab only). Failure here does NOT block the app (it uses ONNX).
try:
    import ai_edge_torch
    edge = ai_edge_torch.convert(model.eval(), (dummy,))
    edge.export(str(OUT / "crop_disease_fp32.tflite")); print("tflite written", sz(OUT / "crop_disease_fp32.tflite"), "MB")
except Exception as e:
    print("TFLite export skipped (pip install ai-edge-torch on Colab to enable):", type(e).__name__)

# %%
labels = {
    "version": 2, "input_size": IMG, "mean": MEAN.tolist(), "std": STD.tolist(), "layout": "NCHW",
    "model_file": FINAL.name, "outputs": ["crop_logits", "lab_logits"],
    "crops": CROPS, "labels": LABELS, "label_to_crop": lab2crop.tolist(), "not_plant_crop_index": int(NP),
    "not_plant_label_index": int(l2i["not_plant"]), "unsupported_crops": [c for c in UNSUPPORTED if c in c2i],
    "temperature": round(T, 4), "thresholds": {"not_plant_p": 0.5, "min_confidence": round(TH_CONF, 2)},
    "metrics": {"clean": res["test"], "field_sim": res["test_fs"], "ood_auroc": round(float(auroc), 4),
                "open_set": OPEN_SET, "robustness": rob, "size_mb": round(sz(FINAL), 2), "int8_vs_fp32_cond_acc": [a32[1], a8[1]]},
    "notes": "Trained on PlantVillage (lab) + RoCoLe coffee (field) + PlantDoc (field); banana/bean/cassava/other plants are recognised as unsupported. Expect lower accuracy on real farm photos than on the test split."}
(OUT / "labels.json").write_text(json.dumps(labels, indent=1))
for f in sorted(OUT.glob("crop_disease*")) + [OUT / "labels.json"]:
    print(f"{f.name:32s}{f.stat().st_size/1e6:7.2f} MB")
