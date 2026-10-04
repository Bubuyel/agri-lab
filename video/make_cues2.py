"""Add phrase-level cue times (seconds, absolute) from the voice alignment to timing2.json and write the audio plan for the walkthrough."""
import json
from pathlib import Path
HERE = Path(__file__).parent
T = json.loads((HERE / "timing2.json").read_text(encoding="utf-8"))
def al(b): return json.loads((HERE / "voices" / "elie_tech" / f"{b}.json").read_text(encoding="utf-8"))
def when(b, phrase):
    a = al(b); text = "".join(a["characters"]); i = text.find(phrase)
    assert i >= 0, (b, phrase)
    return round(T["beats"][b]["start"] + a["character_start_times_seconds"][i], 2)
P = {
 "b2": ["PlantVillage", "PlantDoc", "WFP", "CHIRPS", "iSDA", "All open"],
 "b3": ["Leaf model", "laptop CPU", "Pure suffering", "Random backgrounds", "not-a-plant"],
 "b4": ["ONNX", "Int8", "point nine", "random number", "Shipped float32", "Four milliseconds"],
 "b5": ["Prices", "Rain", "Soil", "No servers"],
 "b5b": ["Live camera", "four milliseconds", "Sixteen languages"],
 "b6": ["browser", "service worker", "Airplane", "Real-world", "Honest AI"],
 "b7": ["Smaller", "Ship it"],
}
cues = {b: {p: when(b, p) for p in ps} for b, ps in P.items()}
T["cues"] = cues
(HERE / "timing2.json").write_text(json.dumps(T, indent=1), encoding="utf-8")
S = {b: v["start"] for b, v in T["beats"].items()}
sfx = [["whoosh", 0.3, 0.4]]
for b in ("b2", "b3", "b4", "b5", "b5b", "b6", "b7"): sfx.append(["whoosh", S[b] - 0.15, 0.35])
for p in ("PlantVillage", "PlantDoc", "WFP", "CHIRPS", "iSDA"): sfx.append(["pop", cues["b2"][p] - 0.05, 0.5])
sfx += [["type", S["b2"] + 0.4, 0.35], ["stamp", cues["b2"]["All open"] + 0.1, 0.8],
        ["type", cues["b3"]["Random backgrounds"] - 0.2, 0.35], ["pop", cues["b3"]["laptop CPU"], 0.5], ["pop", cues["b3"]["not-a-plant"] + 0.3, 0.5],
        ["type", S["b4"] + 0.3, 0.3], ["fail", cues["b4"]["point nine"] + 0.35, 0.8], ["stamp", cues["b4"]["random number"] + 0.4, 0.9], ["ding", cues["b4"]["Four milliseconds"] + 0.2, 0.6],
        ["pop", cues["b5b"]["Live camera"] + 0.4, 0.5], ["ding", cues["b5b"]["four milliseconds"] + 0.9, 0.6], ["pop", cues["b5b"]["Sixteen languages"] + 0.2, 0.5], ["pop", cues["b5"]["Prices"], 0.5], ["pop", cues["b5"]["Rain"], 0.5], ["pop", cues["b5"]["Soil"], 0.5], ["stamp", cues["b5"]["No servers"] + 0.2, 0.7],
        ["type", cues["b6"]["service worker"] - 0.2, 0.3], ["toggle", cues["b6"]["Airplane"], 0.9], ["ding", cues["b6"]["Real-world"] + 1.3, 0.6],
        ["logo", cues["b7"]["Ship it"] - 0.2, 0.9]]
plan = {"voice": [[f"voices/elie_tech/{b}.mp3", v["start"]] for b, v in T["beats"].items()], "sfx": sfx, "total": T["total"], "music": "music2.mp3"}
(HERE / "audio_plan2.json").write_text(json.dumps(plan, indent=1), encoding="utf-8")
print(json.dumps(cues))
