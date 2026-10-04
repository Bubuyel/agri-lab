#!/bin/bash
# final chain for the 16 shipped languages: UI packs (new strings only) -> advice -> Kirundi voice clips
cd /d/Hack-nation
export PYTHONUTF8=1 HF_HUB_DISABLE_PROGRESS_BARS=1 NLLB_THREADS=6 TTS_THREADS=6
python -u agri-ai/notebooks/src/07_ui_language_packs.py > agri-ai/ui_packs.log 2>&1
python -u agri-ai/notebooks/src/04_advice_translation.py > agri-ai/advice_run.log 2>&1
python -m pip install -q uroman > /dev/null 2>&1
python -u agri-ai/notebooks/src/09_voice_packs.py > agri-ai/voice_run.log 2>&1
touch agri-ai/final_done
