"""Generate the voice-over for the approved script with several candidate voices.  python make_voice.py [voice_name ...]"""
import sys
from pathlib import Path
from eleven import call, HERE

SEGMENTS = {
    "1_problem": "Across the developing world, farmers decide everything alone, with no internet and no expert. Is this plant sick? What will it sell for? Will it rain? What should I plant? A wrong guess costs a whole season.",
    "2_product": "Meet Agri Lab. Point the camera at a leaf. It recognises the plant and the disease, and you get the result in your local language. See the price forecast, the best month to sell and the nearest markets. "
                 "Know the chance of rain for the days ahead. Learn what your soil needs and what to plant. Four small AI models, a few megabytes in total, working entirely on your phone. No internet. No account. Nothing leaves your phone.",
    "3_tagline": "Agri Lab. Expert help, in every farmer's pocket.",
}
VOICES = {"george": "JBFqnCBsd6RMkjVDRZzb", "sarah": "EXAVITQu4vr4xnSDxMaL", "brian": "nPczCjzI2devNBz1zQrb"}

if __name__ == '__main__':
    want = sys.argv[1:] or list(VOICES)
    for name in want:
        d = HERE / "voices" / name
        d.mkdir(parents=True, exist_ok=True)
        for seg, text in SEGMENTS.items():
            out = d / f"{seg}.mp3"
            if out.exists():
                continue
            audio = call(f"/v1/text-to-speech/{VOICES[name]}?output_format=mp3_44100_128",
                         {"text": text, "model_id": "eleven_multilingual_v2", "voice_settings": {"stability": 0.55, "similarity_boost": 0.8, "style": 0.25, "use_speaker_boost": True}}, raw=True)
            out.write_bytes(audio)
            print(name, seg, len(audio) // 1024, "KB", flush=True)
