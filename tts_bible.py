# Render Bible chapters to audio with Gemini TTS, several chapters per request to save quota.
# Usage (run with the .venv that has faster-whisper, e.g. `uv run python tts_bible.py ...`):
#   tts_bible.py status                          progress per testament and book (chapters that have an .m4a)
#   tts_bible.py plan <book>                     show the request plan for a book, no API call (book: genesis, 01_genesis, a path)
#   tts_bible.py batch <book>                    write the merged transcripts <book>/batches/b001_genesis_01.txt, ... (no API call)
#   tts_bible.py run <book> [--max-requests N] [--only b005] [--force]    send the batch files to Gemini; needs `batch` first
#   tts_bible.py probe [model[=Voice] ...]       one short request per model: which ones accept this voice and style
# BIBLE_MODELS="gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts" lists the models in fallback order: when one is out of
# daily quota the next takes over. Each chapter's JSON records the model and voice that made it.
# Chapters are read from <chapter>/transcript.txt (one verse per line). A chapter is never split: neighbouring chapters
# of the same style are merged into one request while their estimated audio (words / the genre's pace in
# bible_styles.json) stays within BIBLE_MERGE_MINUTES (default 9, under the ~10.9-minute output cap); a longer chapter
# gets a request of its own. `batch` writes each request as a text file named after the chapters it merges
# (b012_genesis_14-15.txt), and `run` sends exactly those files, so what you review is what is spoken. Whisper (local,
# no quota) then finds where each chapter starts in the audio, cuts it there and writes <chapter>.mp3, <chapter>.m4a
# and <chapter>_timings.csv next to the transcript. Request audio is cached in <book>/_batches/ (git-ignored), so a
# rerun only sends the requests still missing.
import argparse, base64, csv, datetime, difflib, hashlib, json, math, os, re, subprocess, sys, time, urllib.error, urllib.request, wave
from pathlib import Path


def load_dotenv(path):
    # Minimal .env reader (same rules as tts_episode.py): variables already set in the shell win.
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip().removeprefix("export ").strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(name, value)


ROOT = Path(__file__).resolve().parent
BIBLE = ROOT / "mindfit" / "bible"
load_dotenv(ROOT / ".env")

VOICE = os.environ.get("BIBLE_VOICE", "Cruz")


def parse_models(spec):
    # "a,b=Voice" -> [("a", VOICE), ("b", "Voice")]; a model may need its own voice (named voices like Cruz may exist
    # only on the 3.8 models).
    models = []
    for item in spec.split(","):
        name, _, voice = item.strip().partition("=")
        if name:
            models.append((name, voice or VOICE))
    return models


# Models tried in order: when one runs out of daily quota the next takes over for the rest of the run.
MODELS = parse_models(os.environ.get("BIBLE_MODELS", "gemini-3.8-flash-tts,gemini-3.8-flash-lite-tts"))
# Quota belongs to the project a key came from, so every extra key is another daily allowance. BIBLE_KEYS names the
# environment variables to use, in order (a process pinned to one key: BIBLE_KEYS=GEMINI_API_KEY_02). The slots are
# tried model-first, so the better model on every key is used up before the fallback model starts.
KEY_VARS = [k.strip() for k in os.environ.get("BIBLE_KEYS", "GEMINI_API_KEY,GEMINI_API_KEY_02").split(",")
            if os.environ.get(k.strip(), "").strip()]
SLOTS = [(key_var, model, voice) for model, voice in MODELS for key_var in KEY_VARS]


def slot_label(slot):
    key_var, model, _ = slot
    return f"{model} [{key_var}]"
# Each chapter's style comes from its genre in bible_styles.json (one short constant string per genre keeps the voice
# steady); BIBLE_STYLE, when set, overrides it for every chapter.
STYLE_OVERRIDE = os.environ.get("BIBLE_STYLE", "").strip()
STYLE_CONFIG = json.loads((ROOT / "bible_styles.json").read_text(encoding="utf-8"))
MERGE_MINUTES = float(os.environ.get("BIBLE_MERGE_MINUTES", "9"))  # merge neighbours up to this much estimated audio
PART_WORDS = 120  # words per part inside a request (a part never spans two chapters)
# A request's audio must stay under the output limit (16,384 tokens, about 10.9 min); estimates use each genre's pace.
MAX_MINUTES = float(os.environ.get("BIBLE_MAX_MINUTES", "9.5"))
# Share of transcript words Whisper must find in the audio before it is cut. Whisper writes numbers as digits and
# spells old names its own way ("130" for "an hundred and thirty", "Canaan" for "Cainan"), so genealogies like
# Genesis 5 score ~94% on a perfect reading; a missing or repeated passage scores far lower.
MIN_MATCH = float(os.environ.get("BIBLE_MIN_MATCH", "0.90"))
# Lists are full of numbers and names Whisper writes differently (Genesis 5 scores 88% on a clean reading).
MIN_MATCH_LIST = float(os.environ.get("BIBLE_MIN_MATCH_LIST", "0.85"))
MAX_RETRIES = 6


class QuotaExhausted(Exception):
    pass


class TTSFailed(Exception):
    pass


class NoAudio(TTSFailed):
    # HTTP 200 without audio: finishReason RECITATION means the safety filter judged the text too close to a memorised
    # source (Bible verses are), so another model may still voice it.
    pass


class Transient(TTSFailed):
    # Overload, rate limit or network trouble that outlasted every retry: this batch fails, the next one may work.
    pass


def chapter_numbers(spec):
    # "5,10,25-31" -> {5, 10, 25..31}
    numbers = set()
    for piece in spec.split(","):
        low, _, high = piece.strip().partition("-")
        numbers.update(range(int(low), int(high or low) + 1))
    return numbers


def genre_of(slug, number):
    book = STYLE_CONFIG["books"].get(slug)
    if book is None:
        sys.exit(f"bible_styles.json has no entry for book '{slug}'")
    for genre, spec in book.get("chapters", {}).items():
        if number in chapter_numbers(spec):
            return genre
    return book["genre"]


class Chapter:
    def __init__(self, folder):
        self.folder = folder
        self.name = folder.name
        self.lines = [l.strip() for l in (folder / "transcript.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
        self.m4a = folder / f"{self.name}.m4a"
        slug, number = self.name.rsplit("_", 1)
        self.genre = genre_of(slug, int(number))
        self.style = STYLE_OVERRIDE or STYLE_CONFIG["styles"][self.genre]


def words_of(line):
    return len(line.split())


def book_folder(arg):
    path = Path(arg)
    if path.is_dir():
        return path.resolve()
    hits = [d for d in sorted(BIBLE.glob("*/*")) if d.is_dir() and arg in (d.name, d.name.split("_", 1)[1])]
    if len(hits) != 1:
        sys.exit(f"book '{arg}': expected one match under {BIBLE}, found {len(hits)}")
    return hits[0]


def load_chapters(book):
    return [Chapter(d) for d in sorted(book.iterdir()) if d.is_dir() and (d / "transcript.txt").is_file()]


def chapter_minutes(chapter):
    return sum(words_of(l) for l in chapter.lines) / STYLE_CONFIG["pace"][chapter.genre]


def pack(chapters, limit_minutes):
    # A request is a list of (chapter index, line index). A chapter is never split: it either stands alone or shares a
    # request with its neighbours, as long as they keep the same style and the estimated audio stays within the limit.
    # A chapter longer than the limit simply gets a request of its own (`plan` flags the ones that may not fit in the
    # audio limit).
    batches, current, current_minutes = [], [], 0.0

    def flush():
        nonlocal current, current_minutes
        if current:
            batches.append(current)
        current, current_minutes = [], 0.0

    for ci, chapter in enumerate(chapters):
        minutes = chapter_minutes(chapter)
        if current_minutes + minutes > limit_minutes or (current and chapters[current[0][0]].style != chapter.style):
            flush()
        current += [(ci, li) for li in range(len(chapter.lines))]
        current_minutes += minutes
    flush()
    return batches


def batch_words(chapters, items):
    return sum(words_of(chapters[ci].lines[li]) for ci, li in items)


class Batch:
    # One request: a merged-transcript file plus the (chapter index, line index) pairs it holds.
    def __init__(self, path, items, text):
        self.path, self.stem, self.items, self.text = path, path.stem, items, text
        # The hash ignores the request number in the header, so renumbering never makes cached audio look stale.
        head, _, body = text.partition("\n")
        self.sha = hashlib.sha1((head.rsplit("| genre", 1)[-1] + "\n" + body).encode()).hexdigest()


def batch_stem(n, chapters, items):
    first, last = chapters[items[0][0]], chapters[items[-1][0]]
    if first is not last:
        return f"b{n:03d}_{first.name}-{last.name.rsplit('_', 1)[1]}"
    return f"b{n:03d}_{first.name}"


def render_batch(n, chapters, items):
    # "## genesis_24 lines 35-67" says which verses of a long chapter this request holds.
    head = chapters[items[0][0]]
    out = [f"# b{n:03d} | {batch_words(chapters, items)} words | voice {VOICE} | genre {head.genre} | style: {head.style}"]
    for ci in dict.fromkeys(ci for ci, _ in items):
        lines = [li for c, li in items if c == ci]
        out += ["", f"## {chapters[ci].name} lines {lines[0] + 1}-{lines[-1] + 1}"]
        out += [chapters[ci].lines[li] for li in lines]
    return "\n".join(out) + "\n"


def read_batches(book, chapters):
    folder = book / "batches"
    paths = sorted(folder.glob("b*.txt"))
    if not paths:
        sys.exit(f"no batch files in {folder}: run `tts_bible.py batch {book.name}` first")
    index = {c.name: i for i, c in enumerate(chapters)}
    batches = []
    for path in paths:
        text, items, ci, expected, header_style = path.read_text(encoding="utf-8"), [], None, 0, None
        for raw in text.splitlines():
            if raw.startswith("# "):
                header_style = raw.rsplit("style: ", 1)[-1]
                continue
            header = re.fullmatch(r"## (\S+) lines (\d+)-(\d+)", raw)
            if header:
                if ci is not None and expected:
                    sys.exit(f"{path.name}: section of {chapters[ci].name} is shorter than its header says")
                ci, first, last = index[header.group(1)], int(header.group(2)) - 1, int(header.group(3)) - 1
                expected, cursor = last - first + 1, first
            elif raw.strip():
                if ci is None or expected == 0 or chapters[ci].lines[cursor] != raw.strip():
                    sys.exit(f"{path.name}: line does not match {chapters[ci].name if ci is not None else '?'} transcript; rerun `batch`")
                items.append((ci, cursor))
                cursor, expected = cursor + 1, expected - 1
        if not items or {chapters[c].style for c, _ in items} != {header_style}:
            sys.exit(f"{path.name}: style differs from bible_styles.json; rerun `batch`")
        batches.append(Batch(path, items, text))
    return batches


def parts_of(chapters, items):
    parts, text, count, last = [], [], 0, None
    for ci, li in items:
        line = chapters[ci].lines[li]
        if text and (ci != last or count >= PART_WORDS):
            parts.append({"style": chapters[last].style, "text": " ".join(text)})
            text, count = [], 0
        text.append(line)
        count += words_of(line)
        last = ci
    if text:
        parts.append({"style": chapters[last].style, "text": " ".join(text)})
    return parts


def request_parts(parts, style_mode):
    # metadata: the 3.8 models take the style in speech_metadata. Older models reject that field ("Speech metadata is not
    # supported"): "prefix" puts the style in the text as an instruction, "none" sends the plain text.
    if style_mode == "metadata":
        return [{"text": p["text"], "speech_metadata": {"style": p["style"]}} for p in parts]
    if style_mode == "prefix":
        return [{"text": f"Say {p['style']}: {p['text']}"} for p in parts]
    return [{"text": p["text"]} for p in parts]


def synth(parts, model, voice, style_mode="metadata", key_var=None):
    key_var = key_var or (KEY_VARS[0] if KEY_VARS else "GEMINI_API_KEY")
    key = os.environ.get(key_var, "").strip()
    if not key:
        sys.exit(f"{key_var} is not set (export it, or put it in .env next to this script)")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": request_parts(parts, style_mode)}],
        "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"voice": voice}}},
    }
    data = json.dumps(body).encode()
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(url, data=data, method="POST", headers={
            "x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                res = json.load(r)
            try:
                return base64.b64decode(res["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
            except (KeyError, IndexError):  # the model sometimes answers 200 with no audio (finishReason OTHER); retry
                reason = (res.get("candidates") or [{}])[0].get("finishReason", "no candidates")
                # A recitation block repeats: across 38 retries in the logs none ever produced audio, and every try costs
                # one of the 100 requests per model per day, so fail at once and let the next model try.
                if attempt == MAX_RETRIES or reason == "RECITATION":
                    raise NoAudio(f"{model}: response had no audio ({reason})")
                print(f"  {model}: response had no audio ({reason}), retry {attempt + 1}/{MAX_RETRIES}", flush=True)
                time.sleep(5)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")
            if e.code == 429 and "PerDay" in msg:  # waiting minutes cannot fix a daily quota
                raise QuotaExhausted(msg)
            if e.code not in (429, 500, 503):
                raise TTSFailed(f"{model}: HTTP {e.code}: {msg[:600]}")
            if attempt == MAX_RETRIES:
                raise Transient(f"{model}: HTTP {e.code} after {MAX_RETRIES} retries: {msg[:300]}")
            wait = min(15 * 2 ** attempt, 300)
            print(f"  HTTP {e.code}, retry {attempt + 1}/{MAX_RETRIES} in {wait}s", flush=True)
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            if attempt == MAX_RETRIES:
                raise Transient(f"{model}: network error: {e}")
            time.sleep(15)


def save_wav(path, audio):
    if audio[:4] == b"RIFF":
        path.write_bytes(audio)
        return
    with wave.open(str(path), "wb") as w:  # headerless PCM, 24 kHz mono 16-bit
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(audio)


def wav_seconds(path):
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


_whisper = None


def align(wav, lines):
    # Returns, per line, its start and a cut point (middle of the silence before it) in seconds, plus the share of
    # transcript words Whisper found. Same word matching as whisper_timings.py.
    global _whisper
    if _whisper is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError:
            sys.exit("faster-whisper is not installed: run with `uv run python tts_bible.py ...` or the .venv")
        _whisper = WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8")
    segments, _ = _whisper.transcribe(str(wav), word_timestamps=True, language="en", vad_filter=False,
                                      beam_size=5, condition_on_previous_text=False)
    heard = [(re.sub(r"[^a-z0-9']", "", w.word.lower()), w.start, w.end) for s in segments for w in s.words]
    heard = [h for h in heard if h[0]]
    words, bounds = [], []
    for line in lines:
        tokens = re.findall(r"[a-z0-9']+", line.lower())
        bounds.append((len(words), len(words) + len(tokens)))
        words += tokens
    at = {}  # transcript word index -> heard word index
    sm = difflib.SequenceMatcher(None, [h[0] for h in heard], words, autojunk=False)
    for tag, a, a2, b, b2 in sm.get_opcodes():
        if tag == "equal" or (tag == "replace" and a2 - a == b2 - b):
            for k in range(b2 - b):
                at[b + k] = a + k
        elif tag == "replace" and "".join(h[0] for h in heard[a:a2]) == "".join(words[b:b2]):
            at[b] = a
    starts, cuts = [], []
    for a, b in bounds:
        hit = next((k for k in range(a, b) if k in at), None)
        if hit is None:
            starts.append(None)
            cuts.append(None)
            continue
        word_index = at[hit]
        start = max(0.0, heard[word_index][1] - 0.25 * (hit - a))
        previous_end = heard[word_index - 1][2] if word_index > 0 else 0.0
        cut = previous_end + (start - previous_end) / 2 if hit == a and start > previous_end else max(0.0, start - 0.1)
        starts.append(start)
        cuts.append(cut)
    for i, s in enumerate(starts):  # lines Whisper never matched sit between their neighbours
        if s is None:
            p = next((j for j in range(i - 1, -1, -1) if starts[j] is not None), None)
            q = next((j for j in range(i + 1, len(starts)) if starts[j] is not None), None)
            guess = (starts[p] + (starts[q] - starts[p]) * (i - p) / (q - p)) if p is not None and q is not None \
                else (starts[p] if p is not None else 0.0)
            starts[i], cuts[i] = guess, guess
    for i in range(1, len(starts)):  # never backwards
        starts[i] = max(starts[i], starts[i - 1])
        cuts[i] = max(cuts[i], cuts[i - 1])
    # Whisper often drops the last few words of a long file even when they were spoken, so the end counts as present
    # when any of the last ten words is found; a truncated reading loses far more than that.
    tail = range(max(0, len(words) - 10), len(words))
    # Words heard beyond the script: a style prefix read aloud would add several per part.
    extra_speech = len(heard) - len(words) > 0.06 * len(words) + 10
    return starts, cuts, len(at) / max(1, len(words)), any(k in at for k in tail) and not extra_speech


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def build_chapter(ci, chapters, batches, cache):
    chapter = chapters[ci]
    pieces, starts, offset, made = [], [], 0.0, []
    for batch in batches:
        items = batch.items
        positions = [k for k, (c, _) in enumerate(items) if c == ci]
        if not positions:
            continue
        meta_path = cache / f"{batch.stem}.json"
        if not meta_path.is_file():
            return f"request {batch.stem} is not generated yet"
        meta = json.loads(meta_path.read_text())
        if not meta["ok"]:
            return f"request {batch.stem} does not match its transcript ({meta['matched']:.0%}); delete its .wav and .json to retry"
        made.append((meta.get("model", "unknown"), meta.get("voice", VOICE), meta.get("key", "unknown")))
        first, last = positions[0], positions[-1]
        seg_start = 0.0 if first == 0 else meta["cuts"][first]
        seg_end = meta["cuts"][last + 1] if last + 1 < len(items) else meta["seconds"]
        starts += [max(0.0, meta["starts"][k] - seg_start) + offset for k in positions]
        pieces.append((cache / f"{batch.stem}.wav", seg_start, seg_end))
        offset += seg_end - seg_start
    starts[0] = 0.0
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1])
    cut_files = []
    for k, (wav, seg_start, seg_end) in enumerate(pieces):
        cut = cache / f"_cut_{chapter.name}_{k}.wav"
        ffmpeg("-i", str(wav), "-ss", f"{seg_start:.3f}", "-to", f"{seg_end:.3f}", str(cut))
        cut_files.append(cut)
    listing = cache / f"_cut_{chapter.name}.txt"
    listing.write_text("".join(f"file '{f.resolve()}'\n" for f in cut_files))
    mp3 = chapter.folder / f"{chapter.name}.mp3"
    ffmpeg("-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "libmp3lame", "-q:a", "2", str(mp3))
    ffmpeg("-i", str(mp3), "-vn", "-c:a", "aac", "-b:a", os.environ.get("AAC_BITRATE", "128k"),
           "-movflags", "+faststart", str(chapter.m4a))
    with open(chapter.folder / f"{chapter.name}_timings.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["line", "start_seconds", "exact", "check", "text"])
        for i, (line, start) in enumerate(zip(chapter.lines, starts)):
            w.writerow([i + 1, round(start, 2), "", "", line])
    write_chapter_json(ci, chapters, *made[0])
    for f in [*cut_files, listing]:
        f.unlink()
    return None


def write_chapter_json(ci, chapters, model, voice, key):
    # Same shape as the other episode JSON files (title, voice, parts with style and text), so the chapter can also be
    # rendered alone with tts_episode.py; the parts are exactly what was spoken.
    chapter = chapters[ci]
    book, number = chapter.name.rsplit("_", 1)
    small = {"of", "the", "and"}
    title = " ".join(w if w in small else w.capitalize() for w in book.split("_"))
    parts = parts_of(chapters, [(ci, li) for li in range(len(chapter.lines))])
    rows = ",\n".join("    " + json.dumps(p, ensure_ascii=False) for p in parts)
    head = f'  "title": {json.dumps(f"Bible audio - {title} {int(number)}")},\n  "voice": {json.dumps(voice)},\n  "model": {json.dumps(model)},\n  "key": {json.dumps(key)},\n'
    (chapter.folder / f"{chapter.name}.json").write_text(f'{{\n{head}  "parts": [\n{rows}\n  ]\n}}\n', encoding="utf-8")


def cmd_plan(args):
    book = book_folder(args.book)
    chapters = load_chapters(book)
    batches = pack(chapters, MERGE_MINUTES)
    total = long_batches = 0
    for n, items in enumerate(batches, 1):
        words = batch_words(chapters, items)
        total += words
        genre = chapters[items[0][0]].genre
        minutes = words / STYLE_CONFIG["pace"][genre]
        long_batches += minutes > MAX_MINUTES
        print(f"{batch_stem(n, chapters, items):34s} {words:5d} words  ~{minutes:4.1f} min  {genre}"
              f"{'   <- may exceed the audio limit' if minutes > MAX_MINUTES else ''}")
    print(f"{book.name}: {len(chapters)} chapters, {total} words -> {len(batches)} requests "
          f"({long_batches} longer than {MAX_MINUTES} min, estimated at each genre's pace)")
    print(f"voice {VOICE}, slots {' -> '.join(slot_label(s) for s in SLOTS)}, merge up to {MERGE_MINUTES:g} min, styles from bible_styles.json"
          f"{' (overridden by BIBLE_STYLE)' if STYLE_OVERRIDE else ''}")


def cmd_batch(args):
    book = book_folder(args.book)
    chapters = load_chapters(book)
    folder = book / "batches"
    folder.mkdir(exist_ok=True)
    for old in folder.glob("b*.txt"):  # a changed cap or transcript renumbers every request
        old.unlink()
    plan = pack(chapters, MERGE_MINUTES)
    for n, items in enumerate(plan, 1):
        path = folder / f"{batch_stem(n, chapters, items)}.txt"
        path.write_text(render_batch(n, chapters, items), encoding="utf-8")
        print(f"{path.relative_to(book)}  {batch_words(chapters, items)} words")
    print(f"{len(plan)} batch files in {folder}")


def synth_with_fallback(parts, active):
    # Tries the models from `active` on. Out of daily quota moves `active` on for the rest of the run; a model that
    # returns no audio for this text (or keeps failing) is skipped for this batch only. audio is None when no model
    # could voice it; reasons lists what each model said.
    index, reasons = active, []
    while index < len(SLOTS):
        slot = SLOTS[index]
        key_var, model, voice = slot
        try:
            return synth(parts, model, voice, style_mode_for(model), key_var), slot, active, reasons
        except QuotaExhausted:
            if index + 1 >= len(SLOTS):
                raise
            if index == active:
                active += 1
            print(f"  {slot_label(slot)} is out of daily quota; switching to {slot_label(SLOTS[index + 1])}", flush=True)
        except (NoAudio, Transient) as e:
            reasons.append(f"[{key_var}] {e}")
            print(f"  [{key_var}] {e}; trying the next model/key for this batch", flush=True)
        index += 1
    return None, None, active, reasons


def load_failed(cache):
    path = cache / "failed.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_failed(cache, failed):
    path = cache / "failed.json"
    if failed:
        path.write_text(json.dumps(failed, indent=2, ensure_ascii=False))
    elif path.exists():
        path.unlink()


def record_failure(cache, batch, reasons):
    # Keyed by the batch's text hash, so a renumbered batch is still the same entry. `run` retries these on its next
    # run; `run --only failed` retries just them.
    failed = load_failed(cache)
    entry = failed.get(batch.sha, {"attempts": 0})
    failed[batch.sha] = {"batch": batch.stem, "attempts": entry["attempts"] + 1,
                         "last": datetime.datetime.now().isoformat(timespec="seconds"), "reasons": reasons}
    save_failed(cache, failed)


def style_mode_for(model):
    # Only the 3.8 models take the style as speech_metadata; the older ones reject it, so their style goes in front of
    # the text as "Say <style>: ..." (probed: it is not spoken). BIBLE_LEGACY_STYLE_MODE=none drops the style.
    return "metadata" if model.startswith("gemini-3.8") else os.environ.get("BIBLE_LEGACY_STYLE_MODE", "prefix")


def adopt_cached(cache, batch):
    # `batch` renumbers requests, so audio made under an old name is found by the hash of its text and renamed.
    if (cache / f"{batch.stem}.json").exists():
        return
    for meta_path in cache.glob("b*.json"):
        if json.loads(meta_path.read_text()).get("sha") == batch.sha:
            for ext in (".json", ".wav"):
                meta_path.with_suffix(ext).rename(cache / f"{batch.stem}{ext}")
            print(f"  reusing audio {meta_path.stem} as {batch.stem}")
            return


def book_voice(chapters):
    # The voice most of this book's finished chapters were made in (each chapter JSON records it), or None for a book
    # with no audio yet. One book keeps one voice: a book started in Charon is finished in Charon.
    counts = {}
    for c in chapters:
        info = c.folder / f"{c.name}.json"
        if c.m4a.exists() and info.exists():
            voice = json.loads(info.read_text()).get("voice")
            if voice:
                counts[voice] = counts.get(voice, 0) + 1
    return max(counts, key=counts.get) if counts else None


def cmd_run(args):
    global SLOTS, VOICE
    book = book_folder(args.book)
    chapters = load_chapters(book)
    existing_voice = book_voice(chapters)
    if existing_voice and existing_voice != VOICE and not os.environ.get("BIBLE_FORCE_VOICE"):
        print(f"this book already has audio in {existing_voice}: using {existing_voice} instead of {VOICE} "
              f"(BIBLE_FORCE_VOICE=1 overrides)", flush=True)
        VOICE = existing_voice
        SLOTS = [(key_var, model, existing_voice) for key_var, model, _ in SLOTS]
    batches = read_batches(book, chapters)
    cache = book / "_batches"
    cache.mkdir(exist_ok=True)
    failed_before = load_failed(cache)
    if failed_before:
        print(f"retrying {len(failed_before)} batch(es) that failed last time: "
              f"{', '.join(f['batch'] for f in failed_before.values())}")
    if args.only == "failed":
        selected = [b for b in batches if b.sha in failed_before]
    else:
        selected = [b for b in batches if not args.only or b.stem.startswith(args.only)]
    if not selected:
        sys.exit("no previously failed batch to retry" if args.only == "failed" else f"no batch file starts with '{args.only}'")
    wanted = {ci for b in selected for ci, _ in b.items}
    pending = [ci for ci, c in enumerate(chapters) if ci in wanted and (args.force or not c.m4a.exists())]
    sent, active, blocked, built_now = 0, 0, [], set()
    try:
        for batch in selected:
            if not any(ci in pending for ci, _ in batch.items):
                continue
            adopt_cached(cache, batch)
            wav, meta_path = cache / f"{batch.stem}.wav", cache / f"{batch.stem}.json"
            if meta_path.exists() and json.loads(meta_path.read_text()).get("sha") != batch.sha:
                sys.exit(f"{batch.path.name} changed after its audio was made; delete _batches/{batch.stem}.* to redo it")
            made_by = ("unknown", VOICE, "unknown")  # a WAV left by an earlier run has no record of its model or key
            if not wav.exists():
                if args.max_requests is not None and sent >= args.max_requests:
                    print(f"stopped after {sent} requests (--max-requests)")
                    break
                try:
                    audio, slot, active, reasons = synth_with_fallback(parts_of(chapters, batch.items), active)
                except TTSFailed as e:  # a request error that no retry fixes: keep it in the log, then stop
                    record_failure(cache, batch, [str(e)])
                    raise
                if audio is None:
                    record_failure(cache, batch, reasons)
                    blocked.append(batch.stem)
                    print(f"  FAILED {batch.stem}: no model returned audio; logged in _batches/failed.json", flush=True)
                    continue
                failed = load_failed(cache)
                if failed.pop(batch.sha, None):
                    save_failed(cache, failed)
                save_wav(wav, audio)
                made_by = (slot[1], slot[2], slot[0])  # model, voice, name of the key variable (never its value)
                sent += 1
                print(f"ok {batch.stem} via {slot_label(slot)} ({sent} requests this run)", flush=True)
            if not meta_path.exists():
                starts, cuts, matched, has_tail = align(wav, [chapters[ci].lines[li] for ci, li in batch.items])
                genre = chapters[batch.items[0][0]].genre
                ok = matched >= (MIN_MATCH_LIST if genre == "list" else MIN_MATCH) and has_tail
                if not ok:
                    print(f"  WARNING {batch.stem}: {matched:.0%} of words matched"
                          f"{'' if has_tail else ', the end is missing or extra words were spoken (check the audio)'}",
                          flush=True)
                meta_path.write_text(json.dumps({"ok": ok, "matched": matched, "seconds": wav_seconds(wav),
                                                 "starts": starts, "cuts": cuts, "sha": batch.sha,
                                                 "model": made_by[0], "voice": made_by[1], "key": made_by[2]}))
            # Cut the chapters of this request right away, so audio shows up as it is made and survives a stopped run.
            for ci in dict.fromkeys(c for c, _ in batch.items):
                if ci in pending and ci not in built_now and build_chapter(ci, chapters, batches, cache) is None:
                    built_now.add(ci)
                    print(f"built {chapters[ci].name}", flush=True)
    except QuotaExhausted as e:
        print(f"daily quota exhausted on every model and key ({', '.join(slot_label(s) for s in SLOTS)}) after {sent} "
              f"requests this run; rerun after the reset (midnight Pacific).\n{str(e)[:300]}")
    built = len(built_now)
    for ci in pending:
        if ci in built_now:
            continue
        problem = build_chapter(ci, chapters, batches, cache)
        if problem:
            print(f"skip {chapters[ci].name}: {problem}")
        else:
            built += 1
            print(f"built {chapters[ci].name}")
    print(f"{built} chapters built, {len(pending) - built} still pending, {sent} requests sent")
    if blocked:
        print(f"FAILED this run (see {cache / 'failed.json'}; rerun `run` or `run --only failed` to retry): "
              f"{', '.join(blocked)}")


def cmd_probe(args):
    # One short verse per model (one request each) to see which models accept this voice and the style field, before
    # trusting them as fallbacks. The WAVs go to _probe/ so they can be listened to.
    models = parse_models(",".join(args.models)) if args.models else MODELS
    out = ROOT / "_probe"
    out.mkdir(exist_ok=True)
    parts = [{"style": STYLE_CONFIG["styles"]["narrative"], "text": "In the beginning God created the heaven and the earth."}]
    for model, voice in models:
        try:
            wav = out / f"{model}_{voice}_{args.style_mode}.wav"
            save_wav(wav, synth(parts, model, voice, args.style_mode))
            print(f"OK    {model} voice {voice} style:{args.style_mode}: {wav_seconds(wav):.1f}s -> {wav}")
        except QuotaExhausted:
            print(f"QUOTA {model}: daily quota exhausted")
        except TTSFailed as e:
            print(f"FAIL  {e}")


def cmd_status(_):
    overall_done = overall_total = 0
    for testament in sorted((p for p in BIBLE.iterdir() if p.is_dir()), key=lambda p: p.name != "old"):
        t_done = t_total = 0
        rows = []
        for book in sorted(p for p in testament.iterdir() if p.is_dir()):
            chapters = load_chapters(book)
            done = sum(1 for c in chapters if c.m4a.exists())
            t_done, t_total = t_done + done, t_total + len(chapters)
            failed = len(load_failed(book / "_batches"))
            rows.append(f"  {book.name:24s} {done:3d}/{len(chapters):3d}{f'   {failed} failed batch(es)' if failed else ''}")
        print(f"{testament.name}: {t_done}/{t_total}")
        print("\n".join(rows))
        overall_done, overall_total = overall_done + t_done, overall_total + t_total
    print(f"total: {overall_done}/{overall_total} chapters")


parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
sub = parser.add_subparsers(dest="command", required=True)
sub.add_parser("status").set_defaults(func=cmd_status)
plan = sub.add_parser("plan")
plan.add_argument("book")
plan.set_defaults(func=cmd_plan)
probe = sub.add_parser("probe")
probe.add_argument("models", nargs="*", help="model or model=Voice; default: BIBLE_MODELS")
probe.add_argument("--style-mode", choices=["metadata", "prefix", "none"], default="metadata",
                   help="how the style is sent: speech_metadata (3.8 models), as a 'Say ...:' prefix, or not at all")
probe.set_defaults(func=cmd_probe)
batch = sub.add_parser("batch")
batch.add_argument("book")
batch.set_defaults(func=cmd_batch)
run =sub.add_parser("run")
run.add_argument("book")
run.add_argument("--max-requests", type=int, default=None, help="stop before sending more than N requests")
run.add_argument("--only", help="send only the batch files whose name starts with this, e.g. b005; `failed` retries "
                 "just the batches that failed before (_batches/failed.json)")
run.add_argument("--force", action="store_true", help="rebuild chapters that already have an .m4a")
run.set_defaults(func=cmd_run)
arguments = parser.parse_args()
try:
    arguments.func(arguments)
except TTSFailed as e:
    sys.exit(str(e))
