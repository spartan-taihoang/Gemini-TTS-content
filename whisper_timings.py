# Measure start_seconds per transcript line from the finished audio with Whisper (runs locally, no Gemini requests).
# Usage: python3 whisper_timings.py <audio.m4a|mp3> <transcript.txt> <out.csv>
# Measures the spoken words, so it stays accurate on long chunks and around <chuckle> and long pauses.
# Needs faster-whisper, which this folder does not otherwise use. Install it once in its own virtualenv; Apple's
# /usr/bin/python3 (3.9) works, while very new Pythons can fail to build its `av` dependency:
#   /usr/bin/python3 -m venv .venv && .venv/bin/pip install faster-whisper
#   .venv/bin/python whisper_timings.py podcast/<name>/<name>.m4a podcast/<name>/transcript.txt podcast/<name>/<name>_timings.csv
# The first run downloads the model (base.en, about 150 MB). WHISPER_MODEL=small.en is slower and a bit more accurate.
# transcript.txt holds one transcript line per line and must match what was spoken (same file the audio was made from).
# Output columns: line,start_seconds,exact,check,text; exact/check stay empty.
import csv, difflib, os, re, sys

if len(sys.argv) != 4:
    sys.exit(__doc__)
try:
    from faster_whisper import WhisperModel
except ImportError:
    sys.exit("faster-whisper is not installed; see the setup lines at the top of this file")

audio, lines_txt, out_csv = sys.argv[1:4]
lines = [l.strip() for l in open(lines_txt, encoding="utf-8") if l.strip()]

model = WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
segments, _ = model.transcribe(audio, word_timestamps=True, language="en", vad_filter=False,
                               beam_size=5, condition_on_previous_text=False)
heard = [(re.sub(r"[^a-z0-9']", "", w.word.lower()), w.start) for s in segments for w in s.words]
heard = [(t, s) for t, s in heard if t]

# Flatten the transcript into words, remembering which words belong to which line.
words, bounds = [], []
for l in lines:
    toks = re.findall(r"[a-z0-9']+", l.lower())
    bounds.append((len(words), len(words) + len(toks)))
    words += toks

# Align heard words to transcript words; a matched word gives that word an exact time.
at = {}
sm = difflib.SequenceMatcher(None, [t for t, _ in heard], words, autojunk=False)
for tag, a, a2, b, b2 in sm.get_opcodes():
    if tag == "equal" or (tag == "replace" and a2 - a == b2 - b):  # same word, or one misheard word
        for k in range(b2 - b):
            at[b + k] = heard[a + k][1]
    elif tag == "replace" and "".join(t for t, _ in heard[a:a2]) == "".join(words[b:b2]):  # "good night" vs "goodnight"
        at[b] = heard[a][1]

# A line starts at its first matched word, stepped back ~0.25 s per unmatched word before it.
starts = []
for a, b in bounds:
    hit = next((k for k in range(a, b) if k in at), None)
    starts.append(None if hit is None else max(0.0, at[hit] - 0.25 * (hit - a)))
# Lines with no matched word are placed between their neighbours.
for i, s in enumerate(starts):
    if s is None:
        p = next((j for j in range(i - 1, -1, -1) if starts[j] is not None), None)
        q = next((j for j in range(i + 1, len(starts)) if starts[j] is not None), None)
        starts[i] = (starts[p] + (starts[q] - starts[p]) * (i - p) / (q - p)) if p is not None and q is not None \
            else (starts[p] if p is not None else 0.0)
for i in range(1, len(starts)):  # web-admin rejects start_seconds that go backwards
    starts[i] = max(starts[i], starts[i - 1])
starts[0] = 0.0

with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["line", "start_seconds", "exact", "check", "text"])
    for i, (l, s) in enumerate(zip(lines, starts)):
        w.writerow([i + 1, round(s, 2), "", "", l])
matched = len(at)
print(f"{len(lines)} lines; {matched}/{len(words)} words matched ({100 * matched // len(words)}%) -> {out_csv}")
