# Upload a finished daily prayer audio to a SleepFit admin API daily prayer (the prayer must already exist).
# Usage: SLEEPFIT_ADMIN_TOKEN=<admin bearer> python3 push_prayer.py sleepfit/daily_prayer/<name> <prayer-id> [api-base]
# api-base defaults to https://api.dev.sleepfit.appsfy.ai. Uses <name>_ambience.m4a when present, else <name>.m4a.
# Replaces only the prayer's audio; verse, reference, prayer text and status are sent back as they are.
# Old audio assets stay in the media library; only the prayer stops pointing at them.
import json, os, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

if len(sys.argv) not in (3, 4):
    sys.exit(__doc__)
folder, prayer_id = Path(sys.argv[1]), sys.argv[2]
api = (sys.argv[3] if len(sys.argv) == 4 else "https://api.dev.sleepfit.appsfy.ai").rstrip("/") + "/api/v1/admin"
token = os.environ.get("SLEEPFIT_ADMIN_TOKEN", "").strip()
if not token:
    sys.exit("SLEEPFIT_ADMIN_TOKEN is not set (export an admin bearer token)")
name = folder.resolve().name
m4a = folder / f"{name}_ambience.m4a"
if not m4a.is_file():
    m4a = folder / f"{name}.m4a"
if not m4a.is_file():
    sys.exit(f"no {name}_ambience.m4a or {name}.m4a in {folder} (python3 to_m4a.py {folder})")


def call(method, path, body=None):
    req = urllib.request.Request(api + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code} {e.read().decode()[:400]}")


duration = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(m4a)]))
cur = call("GET", f"/content/daily-prayers/{prayer_id}")
prepared = call("POST", "/media/uploads", {"kind": "AUDIO", "mime_type": "audio/mp4", "size": m4a.stat().st_size,
                                           "file_name": m4a.name})
asset_id = prepared["asset"]["id"]
put = urllib.request.Request(prepared["upload_url"], method="PUT", data=m4a.read_bytes(), headers=prepared["upload_headers"])
try:
    urllib.request.urlopen(put).read()
except urllib.error.HTTPError as e:  # S3 sometimes answers 400 on a first PUT; rerunning makes a fresh upload
    sys.exit(f"upload to storage -> {e.code} {e.read().decode()[:400]}")
call("POST", f"/media/{asset_id}/confirm", {"duration_ms": int(duration * 1000)})

# PUT replaces the whole prayer (omitted fields are cleared), so send the current values back.
res = call("PUT", f"/content/daily-prayers/{prayer_id}", {
    "verse_text": cur["verse_text"], "verse_reference": cur["verse_reference"], "prayer_text": cur["prayer_text"],
    "audio_asset_id": asset_id, "status": cur["status"]})
print(f'{res["verse_reference"]}: audio {res["audio"]["state"]} ({m4a.name}, {res["audio"]["duration_ms"] / 1000:.0f}s), position {res["position"]}')
