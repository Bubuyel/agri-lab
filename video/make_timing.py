"""Generate the final voice-over with character timestamps, derive the scene cues (timing.json) and the audio mix plan (audio_plan.json).
python make_timing.py [voice_name]"""
import base64, json, subprocess, sys
from eleven import call, HERE
from make_voice import SEGMENTS, VOICES

name = sys.argv[1] if len(sys.argv) > 1 else "george"
out = HERE / "voices" / f"{name}_final"; out.mkdir(parents=True, exist_ok=True)

align = {}
for seg, text in SEGMENTS.items():
    mp3 = out / f"{seg}.mp3"; js = out / f"{seg}.json"
    if not (mp3.exists() and js.exists()):
        r = call(f"/v1/text-to-speech/{VOICES[name]}/with-timestamps?output_format=mp3_44100_128",
                 {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}})
        mp3.write_bytes(base64.b64decode(r["audio_base64"])); js.write_text(json.dumps(r["alignment"]), encoding="utf-8")
    align[seg] = json.loads(js.read_text(encoding="utf-8"))

def when(seg, phrase):
    a = align[seg]; text = "".join(a["characters"]); i = text.find(phrase)
    assert i >= 0, phrase
    return a["character_start_times_seconds"][i]

def dur(seg):
    return align[seg]["character_end_times_seconds"][-1]

V1, V2 = 5.2, 21.0
d1, d2, d3 = dur("1_problem"), dur("2_product"), dur("3_tagline")
end = V2 + d2 + 0.9
tag = end + 2.0
cues = {
    "logoOut": 5.0, "p_in": 4.9, "nosig": 6.4,
    "no_expert": V1 + when("1_problem", "no expert") - 0.1,
    "four": V1 + when("1_problem", "Is this plant sick?"), "f2": V1 + when("1_problem", "What will it sell for?"),
    "f3": V1 + when("1_problem", "Will it rain?"), "f4": V1 + when("1_problem", "What should I plant?"),
    "wrong": V1 + when("1_problem", "A wrong guess"), "p_out": V1 + d1 + 0.5,
    "meet": V2 - 0.4, "scan": V2 + when("2_product", "Point the camera") - 0.3, "lang": V2 + when("2_product", "you get the result"), "price": V2 + when("2_product", "See the price") - 0.3,
    "rain": V2 + when("2_product", "Know the chance") - 0.3, "land": V2 + when("2_product", "Learn what") - 0.3,
    "models": V2 + when("2_product", "Four small") - 0.3, "nonet": V2 + when("2_product", "No internet.") - 0.2,
    "end": end, "tag": tag, "total": round(tag + 7.2, 2),
}
(HERE / "timing.json").write_text(json.dumps({k: round(v, 2) for k, v in cues.items()}, indent=1), encoding="utf-8")

plan = {
    "voice": [[f"voices/{name}_final/1_problem.mp3", V1], [f"voices/{name}_final/2_product.mp3", V2], [f"voices/{name}_final/3_tagline.mp3", tag - 0.1]],
    "sfx": [["logo", 0.2, 0.9], ["nosignal", V1 + when("1_problem", "no expert") - 0.4, 0.5], ["whoosh", cues["four"] - 0.1, 0.35], ["whoosh", cues["wrong"] - 0.1, 0.3],
            ["toggle", cues["meet"] + 0.45, 0.9], ["whoosh", cues["meet"] + 0.2, 0.45],
            ["chime", cues["scan"] + 1.4, 0.8], ["tap", cues["scan"] + 2.05, 0.6], ["shutter", cues["scan"] + 2.2, 0.9], ["whoosh", cues["scan"] + 2.5, 0.3], ["chime", cues["scan"] + 3.4, 0.55], ["tap", cues["lang"] - 0.15, 0.35], ["tap", cues["lang"] + 0.55, 0.35], ["tap", cues["lang"] + 1.25, 0.35], ["tap", cues["lang"] + 1.95, 0.35],
            ["whoosh", cues["price"] - 0.05, 0.4], ["whoosh", cues["rain"] - 0.05, 0.4], ["whoosh", cues["land"] - 0.05, 0.4], ["whoosh", cues["models"], 0.5],
            ["tap", cues["models"] + 0.6, 0.35], ["tap", cues["models"] + 1.05, 0.35], ["tap", cues["models"] + 1.5, 0.35], ["tap", cues["models"] + 1.95, 0.35],
            ["tap", cues["nonet"] + 0.2, 0.5], ["tap", cues["nonet"] + 1.3, 0.5], ["chime", cues["nonet"] + 2.3, 0.7],
            ["logo", cues["end"] + 0.1, 1.0]],
    "total": cues["total"],
}
(HERE / "audio_plan.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
print(json.dumps({k: round(v, 2) for k, v in cues.items()}))
