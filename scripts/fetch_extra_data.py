"""Download extra open datasets used to teach the vision model what it does NOT know, and to close the lab→field gap.

  banana   : Project-AgML/banana_leaf_disease_classification + banana_leaf_nutrient_classification (CC-BY 4.0)
  bean     : AI-Lab-Makerere/beans (field photos, Uganda)
  cassava  : dpdl-benchmark/cassava (Kaggle cassava leaf disease; one shard sampled)
  other    : avaishnav/Indian-plant-leaves-species (many tree/shrub species, sampled)
  plantdoc : Project-AgML/plant_doc_classification (real-world photos of crops we DO support → mapped to our labels)

Everything is resized (long side 320 px) into  <OUT>/extra/<source>/<label>/*.jpg  and described in  <OUT>/extra/manifest.csv
(columns: path, source, crop, label). Run:  python scripts/fetch_extra_data.py
"""
import io
import os
import re
import random
from pathlib import Path

import pandas as pd
from huggingface_hub import HfApi, hf_hub_download, snapshot_download
from PIL import Image

ROOT = Path(os.environ.get("AGRI_ROOT", Path(__file__).resolve().parents[2]))
OUT = Path(os.environ.get("EXTRA_DIR", ROOT / "agri-ai" / "work" / "extra"))
CACHE = OUT / "_hf"
OUT.mkdir(parents=True, exist_ok=True)
api = HfApi()
rows = []
random.seed(0)
MAN = OUT / "manifest.csv"
if MAN.exists():                                   # idempotent: keep what was already downloaded
    rows = [tuple(r) for r in pd.read_csv(MAN).itertuples(index=False)]
have = lambda src: any(r[1] == src for r in rows)


def labels_from_readme(repo, key="label"):
    """Class names from the dataset card YAML (class_label names: 0: foo)."""
    p = hf_hub_download(repo, "README.md", repo_type="dataset", local_dir=CACHE / repo.replace("/", "_"))
    txt = Path(p).read_text(encoding="utf-8")
    m = re.search(rf"- name: {key}\s+dtype:\s+class_label:\s+names:\s+((?:\s+'?\d+'?: .*\n)+)", txt)
    names = {}
    if m:
        for ln in m.group(1).splitlines():
            mm = re.match(r"\s+'?(\d+)'?: (.*)", ln)
            if mm:
                names[int(mm.group(1))] = mm.group(2).strip().strip("'\"")
    return names


def save(img_bytes, source, crop, label, idx):
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:
        return
    im.thumbnail((320, 320))
    safe = re.sub(r"[^A-Za-z0-9_]+", "_", label).strip("_")[:40] or "x"
    d = OUT / source / safe
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{idx:05d}.jpg"
    im.save(f, quality=90)
    rows.append((str(f), source, crop, label))


def parquet_source(repo, files, source, crop, label_fn, max_n=None, img_col="image", lab_col="label", names=None):
    n = 0
    for fn in files:
        p = hf_hub_download(repo, fn, repo_type="dataset", local_dir=CACHE / repo.replace("/", "_"))
        df = pd.read_parquet(p)
        if max_n:
            df = df.sample(min(len(df), max_n - n), random_state=0) if len(df) > max_n - n else df
        for i, r in enumerate(df.itertuples(index=False)):
            lab = getattr(r, lab_col) if lab_col in df.columns else "x"
            name = (names or {}).get(lab, str(lab))
            save(getattr(r, img_col)["bytes"], source, crop, label_fn(name), n)
            n += 1
        print(f"  {repo}:{fn} → {n} images", flush=True)
        if max_n and n >= max_n:
            break


# ── banana ─────────────────────────────────────────────────────────────────────────────────────────────────────
print("banana disease")
nm = labels_from_readme("Project-AgML/banana_leaf_disease_classification")
if not have("banana"): parquet_source("Project-AgML/banana_leaf_disease_classification", ["data/train-00000-of-00001.parquet"], "banana", "banana", lambda n: f"banana_{n}", names=nm)
print("banana nutrient (raw)")
nm = labels_from_readme("Project-AgML/banana_leaf_nutrient_classification")
if not have("banana2"): parquet_source("Project-AgML/banana_leaf_nutrient_classification", ["raw/train-00000-of-00001.parquet"], "banana2", "banana", lambda n: f"banana_{n}", max_n=900, names=nm)

# ── beans ──────────────────────────────────────────────────────────────────────────────────────────────────────
print("beans")
if not have("bean"): parquet_source("AI-Lab-Makerere/beans", ["data/train-00000-of-00001.parquet", "data/test-00000-of-00001.parquet"], "bean", "bean", lambda n: f"bean_{n}", lab_col="labels",
               names={0: "angular_leaf_spot", 1: "bean_rust", 2: "healthy"})

# ── cassava (sample from the first train shard only: the full set is 6 GB) ───────────────────────────────────────
print("cassava")
files = sorted(s.rfilename for s in api.dataset_info("dpdl-benchmark/cassava").siblings if s.rfilename.startswith("data/train-"))
if not have("cassava"): parquet_source("dpdl-benchmark/cassava", files[:1], "cassava", "cassava", lambda n: f"cassava_{n}", max_n=900, names=labels_from_readme("dpdl-benchmark/cassava"))

# ── other plants (species diversity) ───────────────────────────────────────────────────────────────────────────
print("other plants")
if have("other"): sib = []
else: sib = [s.rfilename for s in api.dataset_info("avaishnav/Indian-plant-leaves-species").siblings if re.search(r"\.(jpe?g|png)$", s.rfilename, re.I)]
by = {}
for f in sib:
    by.setdefault(f.split("/")[0], []).append(f)
species = sorted(by)
pick = [f for sp in species[:: max(1, len(species) // 28)] for f in random.sample(by[sp], min(14, len(by[sp])))]
if sib: snapshot_download("avaishnav/Indian-plant-leaves-species", repo_type="dataset", allow_patterns=pick, local_dir=CACHE / "indian")
for i, f in enumerate(pick):
    p = CACHE / "indian" / f
    if p.exists():
        save(p.read_bytes(), "other", "other_plant", "other_" + f.split("/")[0], i)
print("  species:", len({f.split('/')[0] for f in pick}), "images:", len(pick), flush=True)

# ── PlantDoc: real-world photos of crops we support ──────────────────────────────────────────────────────────────
print("plantdoc")
nm = labels_from_readme("Project-AgML/plant_doc_classification")
print("  classes:", nm)
if not have("plantdoc"): parquet_source("Project-AgML/plant_doc_classification", ["data/train-00000-of-00002.parquet", "data/train-00001-of-00002.parquet"], "plantdoc", "?", lambda n: n, names=nm)

# ── more crops grown in Africa / Asia that are NOT supported → "other_plant" ──────────────────────────────────────────────
for repo, src in [("Project-AgML/rice_leaf_disease_classification", "o_rice"), ("Project-AgML/mango_leaf_disease_classification", "o_mango"),
                  ("Project-AgML/sugarcane_leaf_disease_classification", "o_sugarcane"), ("Project-AgML/cotton_leaf_disease_classification", "o_cotton"),
                  ("Project-AgML/tea_leaf_disease_classification", "o_tea")]:
    if have(src):
        continue
    try:
        info = api.dataset_info(repo)
        pq = sorted(x.rfilename for x in info.siblings if x.rfilename.endswith(".parquet"))
        print(src, pq[:1], flush=True)
        parquet_source(repo, pq[:1], src, "other_plant", lambda n, src=src: f"other_{src}", max_n=250)
    except Exception as e:
        print("skip", repo, type(e).__name__, str(e)[:80])

pd.DataFrame(rows, columns=["path", "source", "crop", "label"]).to_csv(MAN, index=False)
print("done:", len(rows), "images →", OUT)
