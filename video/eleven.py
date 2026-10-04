"""Tiny ElevenLabs helper (stdlib only). The API key is read from video/.env and never printed."""
import json, os, urllib.request, urllib.error
from pathlib import Path

HERE = Path(__file__).parent
for line in (HERE / ".env").read_text(encoding="utf-8").splitlines():
    if line.strip().startswith("ELEVENLABS_API_KEY"):
        KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
BASE = "https://api.elevenlabs.io"


def call(path, body=None, method=None, raw=False, timeout=300):
    req = urllib.request.Request(BASE + path, data=None if body is None else json.dumps(body).encode(), method=method or ("POST" if body is not None else "GET"),
                                 headers={"xi-api-key": KEY, "Content-Type": "application/json", "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = r.read()
            return data if raw else json.loads(data)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"HTTP {e.code} on {path}: {e.read()[:300].decode('utf-8', 'ignore')}")
