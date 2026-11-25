# Upload the breath voice clips to a MindFit admin API and assign each to its cue (Content > Breath voice).
# Usage: MINDFIT_ADMIN_TOKEN=<admin bearer> python3 push_breath_voice.py mindfit/breath_voice/breath_voice.json [api-base]
# api-base defaults to https://api.dev.mindfit.appsfy.ai; use https://api.mindfit.appsfy.ai for prod.
# Reads "cues" from the JSON and uploads clips/<cue>.m4a for each (made by cue_clips.py), then assigns it.
# Run after the backend with the breath voice table is deployed to that environment. Every clip must exist
# before anything is sent. Old clips stay in the media library; only the cue stops pointing at them.
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_API = "https://api.dev.mindfit.appsfy.ai"
MIME = "audio/mp4"


def duration_ms(clip):
    seconds = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)]))
    return int(round(seconds * 1000))


def push(src, api, token):
    """Uploads and assigns every cue's clip in order; returns [(cue, asset_id)]. Exits on the first refused call."""
    token = (token or "").strip()
    if not token:
        sys.exit("MINDFIT_ADMIN_TOKEN is not set (export an admin bearer token)")
    src = Path(src)
    names = json.loads(src.read_text()).get("cues") or sys.exit(f'{src} has no "cues"')
    clips = [src.parent / "clips" / f"{name}.m4a" for name in names]
    missing = [str(c) for c in clips if not c.is_file()]
    if missing:
        sys.exit(f"missing {', '.join(missing)} (python3 cue_clips.py {src})")
    admin = api.rstrip("/") + "/api/v1/admin"

    def call(method, path, body):
        req = urllib.request.Request(admin + path, method=method, data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            sys.exit(f"{method} {path} -> {e.code} {e.read().decode(errors='replace')[:400]}")

    assigned = []
    for name, clip in zip(names, clips):
        prepared = call("POST", "/media/uploads",
                        {"kind": "AUDIO", "mime_type": MIME, "size": clip.stat().st_size, "file_name": clip.name})
        asset_id = prepared["asset"]["id"]
        # Storage checks the signed headers only; the admin bearer must not go to it.
        put = urllib.request.Request(prepared["upload_url"], method="PUT", data=clip.read_bytes(),
                                     headers=prepared["upload_headers"])
        try:
            urllib.request.urlopen(put).read()
        except urllib.error.HTTPError as e:  # a first PUT is sometimes refused; rerunning makes a fresh upload
            sys.exit(f"upload of {clip.name} to storage -> {e.code} {e.read().decode(errors='replace')[:400]}")
        call("POST", f"/media/{asset_id}/confirm", {"duration_ms": duration_ms(clip)})
        call("PUT", f"/content/breath-voice/{name}", {"audio_asset_id": asset_id})
        assigned.append((name, asset_id))
        print(f"{name:<7} {clip.name} -> {asset_id}", flush=True)
    return assigned


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        sys.exit("usage: MINDFIT_ADMIN_TOKEN=<admin bearer> python3 push_breath_voice.py <name>.json [api-base]")
    push(sys.argv[1], sys.argv[2] if len(sys.argv) == 3 else DEFAULT_API, os.environ.get("MINDFIT_ADMIN_TOKEN"))
