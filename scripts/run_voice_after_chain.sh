#!/bin/bash
# waits until the translation chain has finished notebook 04 (it then creates assistant_run.log), then generates every voice pack
cd /d/Hack-nation
export PYTHONUTF8=1 HF_HUB_DISABLE_PROGRESS_BARS=1 TTS_THREADS=${TTS_THREADS:-4}
while [ ! -f agri-ai/assistant_run.log ]; do sleep 60; done
python -m pip install -q uroman 2>/dev/null
python -u agri-ai/notebooks/src/09_voice_packs.py > agri-ai/voice_run.log 2>&1
