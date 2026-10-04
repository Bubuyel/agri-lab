#!/bin/bash
# translation chain: UI packs (07) -> advice for all languages (04). The voice generator (09) waits for lang_chain_done.
cd /d/Hack-nation
export PYTHONUTF8=1 HF_HUB_DISABLE_PROGRESS_BARS=1 NLLB_THREADS=${NLLB_THREADS:-3}
python -u agri-ai/notebooks/src/07_ui_language_packs.py > agri-ai/ui_packs.log 2>&1
python -u agri-ai/notebooks/src/04_advice_translation.py > agri-ai/advice_run.log 2>&1
touch agri-ai/assistant_run.log
