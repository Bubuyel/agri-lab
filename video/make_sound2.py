from eleven import call, HERE
(HERE / "sfx").mkdir(exist_ok=True)
SFX = {
    "fail":   ("Comedic record scratch followed by a short low error buzzer, cartoonish fail sound, 1.5 seconds", 1.6),
    "type":   ("Fast mechanical keyboard typing burst, crisp key clicks, 2 seconds", 2.0),
    "stamp":  ("Heavy rubber stamp thud on paper, short and punchy", 0.8),
    "pop":    ("Soft cartoon bubble pop, light and short", 0.5),
    "ding":   ("Bright short notification ding, clean, single note", 0.8),
}
for name, (text, dur) in SFX.items():
    out = HERE / "sfx" / f"{name}.mp3"
    if out.exists(): continue
    out.write_bytes(call("/v1/sound-generation?output_format=mp3_44100_128", {"text": text, "duration_seconds": dur, "prompt_influence": 0.55}, raw=True))
    print("sfx", name, out.stat().st_size // 1024, "KB", flush=True)
music = HERE / "music2.mp3"
if not music.exists():
    prompt = ("Upbeat, playful, driving electronic instrumental for a fast-paced tech explainer video: punchy synth bass, crisp lo-fi drums, bouncy plucks, "
              "light humorous energy, steady groove, subtle build, clean ending. No vocals.")
    music.write_bytes(call("/v1/music?output_format=mp3_44100_128", {"prompt": prompt, "music_length_ms": 58000, "force_instrumental": True}, raw=True, timeout=600))
    print("music2", music.stat().st_size // 1024, "KB")
