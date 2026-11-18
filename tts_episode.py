# Render a styled episode JSON ({voice, parts:[{style,text}], ambience?}) to MP3 with Gemini TTS.
# Usage: python3 tts_episode.py podcast/<episode>/<episode>.json  (settings from the shell or .env next to this script)
# Outputs land next to the JSON: <name>.mp3 (voice only) and, if "ambience" is set, <name>_ambience.mp3.
# Calls the v1beta REST endpoint directly: the SDK rejected speech_metadata/speechConfig.
import base64, csv, json, os, re, subprocess, sys, time, urllib.error, urllib.request, wave
from pathlib import Path


def load_dotenv(path):
    # Minimal .env reader (KEY=value lines, # comments, optional quotes) so no package is needed.
    # Variables already set in the shell win, so `TTS_MODEL=... python3 tts_episode.py` still overrides the file.
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip().removeprefix("export ").strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)


load_dotenv(Path(__file__).resolve().parent / ".env")

# TTS_MODEL=gemini-3.8-flash-lite-tts switches models when the default one is overloaded.
MODEL = os.environ.get("TTS_MODEL", "gemini-3.8-flash-tts")
MAX_RETRIES = 6  # backoff 15s, 30s, 60s ... capped at 5 min
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
# Parts per API call. 12 (~3 min of audio) keeps an episode at 2-3 requests, which matters on a
# 10-requests-per-day quota, while a bad take stays cheap to redo. TTS_PER_PART=1 is shorthand for 1:
# every part then gets an exact start time, at the cost of one request per part.
PARTS_PER_REQUEST = 1 if os.environ.get("TTS_PER_PART") == "1" else int(os.environ.get("TTS_PARTS_PER_REQUEST", "12"))
if PARTS_PER_REQUEST < 1:
    sys.exit("TTS_PARTS_PER_REQUEST must be at least 1")

key = os.environ.get("GEMINI_API_KEY", "").strip()
if not key:
    sys.exit("GEMINI_API_KEY is not set (export it, or put it in .env next to tts_episode.py)")

src = Path(sys.argv[1]).resolve()
ep = json.loads(src.read_text(encoding="utf-8"))
out = src.with_suffix(".mp3")


def synth(parts):
    body = {
        "contents": [{"role": "user", "parts": [
            {"text": p["text"], "speech_metadata": {"style": p["style"]}} for p in parts]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"voice": ep["voice"]}},
        },
    }
    data = json.dumps(body).encode()
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(URL, data=data, method="POST", headers={
            "x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                res = json.load(r)
            return base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            # Overload and rate limits are transient; anything else is a real error.
            if e.code not in (429, 500, 503) or attempt == MAX_RETRIES:
                sys.exit(f"HTTP {e.code}: {msg}")
            wait = min(15 * 2 ** attempt, 300)
            print(f"  HTTP {e.code}, retry {attempt + 1}/{MAX_RETRIES} in {wait}s", flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == MAX_RETRIES:
                sys.exit(f"network error: {e}")
            time.sleep(15)


def save_wav(path, audio):
    if audio[:4] == b"RIFF":
        path.write_bytes(audio)
        return
    # Headerless PCM (24 kHz mono 16-bit): wrap it so ffmpeg can concat.
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(audio)


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


# Chunk cache per chunk size: switching TTS_PER_PART never mixes old and new takes.
work = src.parent / (src.stem + "_parts") / f"n{PARTS_PER_REQUEST}"
work.mkdir(parents=True, exist_ok=True)
files = []
for n, i in enumerate(range(0, len(ep["parts"]), PARTS_PER_REQUEST)):
    wav = work / f"chunk_{n:02d}.wav"
    files.append(wav)
    if wav.exists():  # delete a chunk file to regenerate only that chunk
        continue
    save_wav(wav, synth(ep["parts"][i:i + PARTS_PER_REQUEST]))
    print("ok", wav)

# With one part per request every part start is exact, so write them out; otherwise use align_timings.py.
if PARTS_PER_REQUEST == 1:
    timings, t = [], 0.0
    for n, f in enumerate(files):
        i = n * PARTS_PER_REQUEST
        preview = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", ep["parts"][i]["text"])).strip()
        timings.append({"part": i + 1, "start_seconds": round(t, 1), "text": preview[:80]})
        t += wav_seconds(f)
    tpath = src.with_name(src.stem + "_timings.csv")
    with open(tpath, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["part", "start_seconds", "text"])
        w.writeheader()
        w.writerows(timings)
    print("timings", tpath)

lst = work / "list.txt"
lst.write_text("".join(f"file '{f.resolve()}'\n" for f in files))
subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                "-c:a", "libmp3lame", "-q:a", "2", str(out)], check=True)
print("done", out)

amb = ep.get("ambience")
if amb:
    bg = (src.parent / amb["file"]).resolve()
    lead, tail = amb.get("lead_in", 4), amb.get("tail", 6)
    total = lead + sum(wav_seconds(f) for f in files) + tail
    fade_out = min(tail, 6)
    fmt = "aformat=sample_rates=44100:channel_layouts=stereo"
    graph = (
        f"[0:a]{fmt},adelay={int(lead * 1000)}:all=1,apad=whole_dur={total}[v];"
        f"[1:a]{fmt},volume={amb.get('volume_db', -5)}dB,atrim=duration={total},"
        f"afade=t=in:d={min(lead, 3)},afade=t=out:st={total - fade_out}:d={fade_out}[bg];"
        "[v][bg]amix=inputs=2:duration=longest:normalize=0[m]"
    )
    mixed = src.with_name(src.stem + "_ambience.mp3")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-stream_loop", "-1", "-i", str(bg),
                    "-filter_complex", graph, "-map", "[m]", "-c:a", "libmp3lame", "-q:a", "2", str(mixed)],
                   check=True)
    print("done", mixed)
