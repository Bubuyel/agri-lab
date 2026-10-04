"""Mix voice-over + sound effects + ducked music, then mux with the silent video -> agri_lab_tech_walkthrough.mp4"""
import json, subprocess, sys
from pathlib import Path
import imageio_ffmpeg

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
plan = json.loads((HERE / "audio_plan2.json").read_text(encoding="utf-8"))
T = plan["total"]

inputs, chains, vo_labels, sfx_labels = [], [], [], []
def add(path):
    inputs.extend(["-i", str(HERE / path)]); return len(inputs) // 2 - 1

m = add(plan.get("music", "music.mp3"))
chains.append(f"[{m}:a]atrim=0:{T},afade=t=in:st=0:d=2,afade=t=out:st={T-3.5}:d=3.5,volume=0.5[mus]")
for i, (path, at) in enumerate(plan["voice"]):
    k = add(path); ms = int(at * 1000)
    chains.append(f"[{k}:a]adelay={ms}|{ms},volume=1.25[v{i}]"); vo_labels.append(f"[v{i}]")
chains.append("".join(vo_labels) + f"amix=inputs={len(vo_labels)}:normalize=0,asplit=2[vo][vosc]")
sfx_files = {}
for j, (name, at, vol) in enumerate(plan["sfx"]):
    k = sfx_files.get(name)
    k = add(f"sfx/{name}.mp3")          # one input per use (simple and robust)
    ms = int(max(0, at) * 1000)
    chains.append(f"[{k}:a]adelay={ms}|{ms},volume={vol * 0.9:.2f}[s{j}]"); sfx_labels.append(f"[s{j}]")
chains.append("".join(sfx_labels) + f"amix=inputs={len(sfx_labels)}:normalize=0[sfx]")
chains.append("[mus][vosc]sidechaincompress=threshold=0.02:ratio=9:attack=25:release=500[duck]")
chains.append(f"[duck][vo][sfx]amix=inputs=3:normalize=0,alimiter=limit=0.93,apad=whole_dur={T}[mix]")

audio = HERE / "audio_mix2.m4a"
cmd = [FF, "-y", *inputs, "-filter_complex", ";".join(chains), "-map", "[mix]", "-t", str(T), "-c:a", "aac", "-b:a", "256k", str(audio)]
r = subprocess.run(cmd, capture_output=True, text=True)
if r.returncode: print(r.stderr[-1500:]); sys.exit(1)
final = HERE / "agri_lab_tech_walkthrough.mp4"
r = subprocess.run([FF, "-y", "-i", str(HERE / "video2_silent.mp4"), "-i", str(audio), "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy", "-shortest", "-movflags", "+faststart", str(final)], capture_output=True, text=True)
if r.returncode: print(r.stderr[-1500:]); sys.exit(1)
print("wrote", final, round(final.stat().st_size / 1e6, 1), "MB")
