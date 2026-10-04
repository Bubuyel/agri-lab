"""Regenerate the .ipynb files from notebooks/src/*.py (the .py files are the source of truth).

Adds a Colab/Kaggle setup cell (mount Drive, pip install) in front of each notebook so the same code runs anywhere.
Usage: python scripts/build_notebooks.py
"""
from pathlib import Path

from py2nb import convert

ROOT = Path(__file__).resolve().parents[1]
SETUP = {
    "01_crop_disease_vision": "torch torchvision onnx onnxruntime pandas scikit-learn pillow matplotlib",
    "02_crop_price_forecast": "pandas numpy scikit-learn lightgbm matplotlib pycountry",
    "03_rainfall_outlook": "numpy scipy scikit-learn tifffile pandas",
    "04_advice_translation": "torch transformers sentencepiece sacrebleu accelerate",
    "05_daily_rain": "numpy scipy tifffile netCDF4",
    "06_land_soil_crops": "numpy rasterio scipy tifffile",
}
CELL = '''# %% [markdown]
# ### ▶ Setup (Colab / Kaggle). Skipped automatically on a laptop.
# Put the `Hack-nation` data folders in Google Drive (or upload them to Kaggle) and adjust `AGRI_ROOT` if needed.

# %%
import os, sys
if "google.colab" in sys.modules or os.path.exists("/kaggle"):
    os.system("pip -q install {pkgs}")
    if "google.colab" in sys.modules:
        from google.colab import drive
        drive.mount("/content/drive")
        os.environ.setdefault("AGRI_ROOT", "/content/drive/MyDrive/Hack-nation")
    else:
        os.environ.setdefault("AGRI_ROOT", "/kaggle/input/hack-nation")
        os.environ.setdefault("OUT_DIR", "/kaggle/working/artifacts")
        os.environ.setdefault("WORK_DIR", "/kaggle/working/work")
    print("AGRI_ROOT =", os.environ["AGRI_ROOT"])

'''

if __name__ == "__main__":
    (ROOT / "notebooks").mkdir(exist_ok=True)
    tmp = ROOT / "work"
    tmp.mkdir(exist_ok=True)
    for name, pkgs in SETUP.items():
        src = (ROOT / "notebooks" / "src" / f"{name}.py").read_text(encoding="utf-8")
        # insert the setup cell right after the intro markdown cell (before the first code cell)
        i = src.index("\n# %%\n") + 1
        merged = src[:i] + CELL.format(pkgs=pkgs) + src[i:]
        t = tmp / f"{name}.py"
        t.write_text(merged, encoding="utf-8")
        convert(str(t), str(ROOT / "notebooks" / f"{name}.ipynb"))
