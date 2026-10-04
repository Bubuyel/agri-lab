"""Sound effects + background music with ElevenLabs.  python make_sound.py"""
from eleven import call, HERE

(HERE / "sfx").mkdir(exist_ok=True)
SFX = {
    "whoosh":   ("Soft, airy, premium UI whoosh transition, very short, clean, no music", 1.0),
    "tap":      ("Single soft UI button tap click, minimal, clean, high quality", 0.5),
    "toggle":   ("Smooth switch toggle flip on, subtle plastic click, minimal UI", 0.6),
    "chime":    ("Gentle bright success chime, two soft rising notes, glassy, premium, short", 1.5),
    "shutter":  ("Soft smartphone camera shutter click, short and clean", 0.6),
    "logo":     ("Cinematic soft sub bass swell with airy shimmer rising into a gentle resolved chord, product logo reveal, 3 seconds", 3.0),
    "nosignal": ("Subtle low tone drop and faint static fade, signal lost, 2 seconds, understated", 2.0),
}
for name, (text, dur) in SFX.items():
    out = HERE / "sfx" / f"{name}.mp3"
    if out.exists(): continue
    out.write_bytes(call("/v1/sound-generation?output_format=mp3_44100_128", {"text": text, "duration_seconds": dur, "prompt_influence": 0.5}, raw=True))
    print("sfx", name, out.stat().st_size // 1024, "KB", flush=True)

music = HERE / "music.mp3"
if not music.exists():
    prompt = ("Minimal, warm, optimistic instrumental for a premium technology product launch film: soft felt piano and gentle pulsing synth pad, "
              "light airy percussion entering after 15 seconds, hopeful and human, gradually building to a gentle uplifting peak at 45 seconds then resolving softly. No vocals. Clean, spacious mix.")
    music.write_bytes(call("/v1/music?output_format=mp3_44100_128", {"prompt": prompt, "music_length_ms": 64000, "force_instrumental": True}, raw=True, timeout=600))
    print("music", music.stat().st_size // 1024, "KB")
