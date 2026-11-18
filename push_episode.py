# Upload a finished podcast episode (m4a + transcript timings) to a SleepFit admin API and attach it to an episode.
# Usage: SLEEPFIT_ADMIN_TOKEN=<admin bearer> python3 push_episode.py podcast/<name> <episode-id> [api-base]
# api-base defaults to https://api.dev.sleepfit.appsfy.ai. The episode itself (chapter, number, title, status) must already
# exist; this replaces its audio, duration and transcript. Reads from the folder: <name>.m4a, <name>_timings.csv and
# transcript.txt (the CSV text must match transcript.txt line by line; make the CSV with whisper_timings.py).
# Old audio assets stay in the media library; only the episode stops pointing at them.
import csv, json, math, os, subprocess, sys, urllib.error, urllib.request
from pathlib import Path

if len(sys.argv) not in (3, 4):
    sys.exit(__doc__)
folder, episode_id = Path(sys.argv[1]), sys.argv[2]
api = (sys.argv[3] if len(sys.argv) == 4 else "https://api.dev.sleepfit.appsfy.ai").rstrip("/") + "/api/v1/admin"
token = os.environ.get("SLEEPFIT_ADMIN_TOKEN", "").strip()
if not token:
    sys.exit("SLEEPFIT_ADMIN_TOKEN is not set (export an admin bearer token)")
name = folder.resolve().name
m4a = folder / f"{name}.m4a"


def call(method, path, body=None):
    req = urllib.request.Request(api + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {path} -> {e.code} {e.read().decode()[:400]}")


rows = list(csv.DictReader(open(folder / f"{name}_timings.csv", encoding="utf-8")))
lines = [l.strip() for l in open(folder / "transcript.txt", encoding="utf-8") if l.strip()]
if [r["text"] for r in rows] != lines:
    sys.exit("timings CSV text differs from transcript.txt; regenerate the CSV with whisper_timings.py")
# Whole seconds, rounded down so a line never shows late; the API wants them non-decreasing, text 1-500 chars.
transcript = [{"start_seconds": int(float(r["start_seconds"])), "text": r["text"]} for r in rows]
if any(b["start_seconds"] < a["start_seconds"] for a, b in zip(transcript, transcript[1:])):
    sys.exit("start_seconds go backwards")
if any(not 1 <= len(t["text"]) <= 500 for t in transcript):
    sys.exit("a transcript line is empty or longer than 500 characters")

duration = float(subprocess.check_output(
    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(m4a)]))
prepared = call("POST", "/media/uploads", {"kind": "AUDIO", "mime_type": "audio/mp4", "size": m4a.stat().st_size,
                                           "file_name": m4a.name})
asset_id = prepared["asset"]["id"]
# S3 occasionally answers 400 on a first PUT; a fresh upload then succeeds, so rerun the script if it stops here.
put = urllib.request.Request(prepared["upload_url"], method="PUT", data=m4a.read_bytes(), headers=prepared["upload_headers"])
try:
    urllib.request.urlopen(put).read()
except urllib.error.HTTPError as e:
    sys.exit(f"upload to storage -> {e.code} {e.read().decode()[:400]}")
call("POST", f"/media/{asset_id}/confirm", {"duration_ms": int(duration * 1000)})

cur = call("GET", f"/content/podcast-episodes/{episode_id}")
res = call("PUT", f"/content/podcast-episodes/{episode_id}", {
    "chapter_id": cur["chapter_id"], "episode_number": cur["episode_number"], "title": cur["title"],
    "duration_seconds": math.ceil(duration), "audio_asset_id": asset_id, "transcript": transcript,
    "status": cur["status"]})
print(f'{res["title"]}: {res["duration_seconds"]}s, audio {res["audio"]["state"]}, {len(res["transcript"])} lines')
