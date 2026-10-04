"""Tech walkthrough voice-over (Elie's own cloned voice), one take per beat with character timestamps -> voices/elie_tech/*.mp3 + timing2.json
python make_voice2.py [speed]"""
import base64, json, subprocess, sys
import imageio_ffmpeg
FF = imageio_ffmpeg.get_ffmpeg_exe()
TEMPO = 1.1                                  # extra 10% speed on top of ElevenLabs' own speed setting (pitch preserved)
from eleven import call, HERE

VOICE = "je7tdigpfJV4m1tsxQJk"          # "Elie": the user's own cloned voice
SPEED = float(sys.argv[1]) if len(sys.argv) > 1 else 1.2
BEATS = {
    "b1": "Four AI models. Zero internet. Here's how I built it, in under a minute.",
    "b2": "Data: PlantVillage and PlantDoc for leaves, WFP for prices, CHIRPS for rain, iSDA for soil. All open.",
    "b3": "Leaf model: MobileNetV3, under one million parameters, trained on a laptop CPU. Pure suffering. Random backgrounds so it can't cheat, and a not-a-plant class, so bananas stop being spider mites.",
    "b4": "Shrinking: ONNX, four megabytes. Int8 quantization? Accuracy: point nine percent. A random number generator. Shipped float32. Four milliseconds.",
    "b5": "Prices: LightGBM as JSON trees, run in TypeScript. Rain: a Markov chain. Soil: map layers. No servers. None.",
    "b5b": "Live camera? Same model, four milliseconds a frame, so the shutter only unlocks when it sees a plant. Sixteen languages, translated once with NLLB, at build time.",
    "b6": "It all runs in the browser, WebAssembly, cached by a service worker. Airplane mode? Works. Real-world accuracy: seventy-two percent. Honest AI.",
    "b7": "Smaller than a cat photo. Ship it.",
}
out = HERE / "voices" / "elie_tech"; out.mkdir(parents=True, exist_ok=True)
info = {}
for k, text in BEATS.items():
    mp3, js = out / f"{k}.mp3", out / f"{k}.json"
    if not ((out / f"{k}_raw.mp3").exists() or (mp3.exists() and js.exists())):
        r = call(f"/v1/text-to-speech/{VOICE}/with-timestamps?output_format=mp3_44100_128",
                 {"text": text, "model_id": "eleven_multilingual_v2",
                  "voice_settings": {"stability": 0.4, "similarity_boost": 0.85, "style": 0.45, "use_speaker_boost": True, "speed": SPEED}})
        mp3.write_bytes(base64.b64decode(r["audio_base64"])); js.write_text(json.dumps(r["alignment"]), encoding="utf-8")
    raw_mp3, raw_js = out / f"{k}_raw.mp3", out / f"{k}_raw.json"
    if not raw_mp3.exists():                      # first run: keep the untouched ElevenLabs take, then make the faster one
        mp3.rename(raw_mp3); js.rename(raw_js)
    if TEMPO != 1.0 and (not mp3.exists() or mp3.stat().st_mtime < raw_mp3.stat().st_mtime):
        subprocess.run([FF, "-y", "-i", str(raw_mp3), "-filter:a", f"atempo={TEMPO}", "-b:a", "128k", str(mp3)], check=True, capture_output=True)
        al = json.loads(raw_js.read_text(encoding="utf-8"))
        for key in ("character_start_times_seconds", "character_end_times_seconds"): al[key] = [x / TEMPO for x in al[key]]
        js.write_text(json.dumps(al), encoding="utf-8")
    a = json.loads(js.read_text(encoding="utf-8"))
    info[k] = {"dur": a["character_end_times_seconds"][-1], "text": text}
t = 0.6
for k, v in info.items():                     # lay the beats end to end with a short breath between them
    v["start"] = round(t, 2); t += v["dur"] + 0.1
total = round(t + 1.2, 2)
(HERE / "timing2.json").write_text(json.dumps({"beats": info, "total": total}, indent=1), encoding="utf-8")
print({k: (v["start"], round(v["dur"], 1)) for k, v in info.items()}, "total", total)
