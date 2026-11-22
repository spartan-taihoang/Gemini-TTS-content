# Make one Bible chapter from several short requests, for chapters that the normal tts_bible.py run cannot voice in one
# request: the model skips a stretch of a long list of names, or the recitation filter blocks the whole text.
# Usage (run with the .venv that has faster-whisper):
#   .venv/bin/python tts_bible_split.py <book> <chapter> [<chapter> ...] [--parts N] [--retry]
#   e.g. tts_bible_split.py 15_ezra ezra_02 --parts 2
# The chapter's verses (lines of transcript.txt) are cut into N runs of about equal length, each run is one request
# (cached in <book>/_batches/split_<chapter>_<i>of<N>.wav/.json), Whisper checks each run, and the runs are joined into
# <chapter>.mp3, <chapter>.m4a, <chapter>_timings.csv and <chapter>.json, the same files tts_bible.py writes.
# A run is accepted when Whisper finds its last words and no stretch of 12+ transcript words went unspoken. (The
# normal check counts every word Whisper spells differently, so a list of names fails it even when it was read in full.)
# A run that fails the check stays cached and is not sent again; use --retry to send it again.
# Models, voice and keys come from the same BIBLE_* variables as tts_bible.py; the keys default to GEMINI_API_KEY_02 only.
import argparse, csv, difflib, hashlib, json, math, os, re, sys
from pathlib import Path

os.environ.setdefault("BIBLE_KEYS", "GEMINI_API_KEY_02")
ROOT = Path(__file__).resolve().parent
# tts_bible.py runs its command line at import time, so load only the part above it (its functions and settings).
source = (ROOT / "tts_bible.py").read_text(encoding="utf-8").split("parser = argparse")[0]
tts = {"__file__": str(ROOT / "tts_bible.py"), "__name__": "tts_bible"}
exec(compile(source, "tts_bible.py", "exec"), tts)

WORDS_PER_REQUEST = 650  # about 5 minutes of audio, far below the length at which the model starts skipping text
MIN_SKIPPED_BLOCK = 12  # a block of this many transcript words with (almost) nothing heard counts as skipped
MAX_SKIPPED_WORDS = 10


class Recorder:
    # Wraps the Whisper model so the words heard in a request can be compared with the transcript after tts["align"].
    def __init__(self, model):
        self.model, self.heard = model, []

    def transcribe(self, *args, **kwargs):
        segments, info = self.model.transcribe(*args, **kwargs)
        segments = list(segments)
        heard = [re.sub(r"[^a-z0-9']", "", w.word.lower()) for s in segments for w in s.words]
        self.heard = [h for h in heard if h]
        return segments, info


def split_lines(lines, count):
    # Contiguous runs of verses with about the same number of words.
    words = [len(line.split()) for line in lines]
    total, runs, start, running = sum(words), [], 0, 0
    for index, size in enumerate(words):
        running += size
        left_over = len(lines) - index - 1
        if len(runs) < count - 1 and running >= total * (len(runs) + 1) / count and left_over >= count - len(runs) - 1:
            runs.append(list(range(start, index + 1)))
            start = index + 1
    runs.append(list(range(start, len(lines))))
    return runs


NUMBER_WORDS = {"one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve",
                "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty",
                "forty", "fourscore", "fifty", "sixty", "threescore", "seventy", "eighty", "ninety", "hundred",
                "thousand", "score", "a"}


def without_numbers(tokens):
    # Whisper writes "650" for "six hundred fifty", so numbers never match; compare the other words only.
    return [t for t in tokens if t not in NUMBER_WORDS and not any(ch.isdigit() for ch in t)]


def compare_with_transcript(heard, words):
    # Returns (skipped blocks, number of skipped words, whether the end of the text was heard), numbers left out.
    heard, words = without_numbers(heard), without_numbers(words)
    matcher = difflib.SequenceMatcher(None, heard, words, autojunk=False)
    blocks, matched_at = [], set()
    for tag, heard_start, heard_end, word_start, word_end in matcher.get_opcodes():
        length = word_end - word_start
        if tag == "equal":
            matched_at.update(range(word_start, word_end))
        if tag in ("delete", "replace") and length >= MIN_SKIPPED_BLOCK and heard_end - heard_start <= length // 4:
            blocks.append(" ".join(words[word_start:word_start + 8]) + f" ... ({length} words)")
    tail_found = any(k in matched_at for k in range(max(0, len(words) - 10), len(words)))
    return blocks, sum(int(b.rsplit("(", 1)[1].split()[0]) for b in blocks), tail_found


def make_run(chapter, lines, stem, cache, recorder, mode, active):
    # Returns (meta, active) for one run of verses, or (None, active) when the run cannot be voiced.
    # mode: "" keeps a cached run as it is, "recheck" checks its audio again, "retry" sends the request again.
    wav, meta_path = cache / f"{stem}.wav", cache / f"{stem}.json"
    text = "\n".join(chapter.lines[i] for i in lines)
    sha = hashlib.sha1(text.encode()).hexdigest()
    made_by = None
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta["sha"] == sha and (meta["is_accepted"] or not mode):
            return meta, active
        meta_path.unlink()
        if mode == "retry" or meta["sha"] != sha:
            wav.unlink(missing_ok=True)
        else:  # checking the same audio again: it was made by the model, voice and key the old record names
            made_by = (meta["model"], meta["voice"], meta["key"])
    if not wav.exists():
        parts = tts["parts_of"]([chapter], [(0, i) for i in lines])
        audio, slot, active, reasons = tts["synth_with_fallback"](parts, active)
        if audio is None:
            print(f"  {stem}: no audio ({'; '.join(reasons)})", flush=True)
            return None, active
        tts["save_wav"](wav, audio)
        made_by = (slot[1], slot[2], slot[0])
        print(f"  {stem}: audio made by {tts['slot_label'](slot)}", flush=True)
    starts, cuts, matched, has_tail = tts["align"](wav, [chapter.lines[i] for i in lines])
    words = [w for i in lines for w in re.findall(r"[a-z0-9']+", chapter.lines[i].lower())]
    blocks, skipped, has_tail = compare_with_transcript(recorder.heard, words)
    meta = {"sha": sha, "lines": [lines[0] + 1, lines[-1] + 1], "seconds": tts["wav_seconds"](wav), "starts": starts,
            "matched": matched, "has_tail": has_tail, "skipped_words": skipped, "skipped_blocks": blocks,
            "is_accepted": bool(has_tail and skipped <= MAX_SKIPPED_WORDS),
            "model": made_by[0] if made_by else "unknown", "voice": made_by[1] if made_by else tts["VOICE"],
            "key": made_by[2] if made_by else "unknown"}
    meta_path.write_text(json.dumps(meta))
    print(f"  {stem}: {matched:.0%} of words matched, tail {'found' if has_tail else 'MISSING'}, {skipped} words skipped"
          f" -> {'accepted' if meta['is_accepted'] else 'REJECTED'}", flush=True)
    for block in blocks:
        print(f"      skipped: {block}", flush=True)
    return meta, active


def build(chapter, metas):
    # Join the runs into the chapter files (the same ones tts_bible.build_chapter writes).
    cache = chapter.folder.parent / "_batches"
    starts, offset, wavs = [], 0.0, []
    for meta in metas:
        starts += [max(0.0, start) + offset for start in meta["starts"]]
        offset += meta["seconds"]
        wavs.append(cache / f"{meta['stem']}.wav")
    starts[0] = 0.0
    for i in range(1, len(starts)):
        starts[i] = max(starts[i], starts[i - 1])
    listing = cache / f"_join_{chapter.name}.txt"
    listing.write_text("".join(f"file '{wav.resolve()}'\n" for wav in wavs))
    mp3 = chapter.folder / f"{chapter.name}.mp3"
    tts["ffmpeg"]("-f", "concat", "-safe", "0", "-i", str(listing), "-c:a", "libmp3lame", "-q:a", "2", str(mp3))
    tts["ffmpeg"]("-i", str(mp3), "-vn", "-c:a", "aac", "-b:a", os.environ.get("AAC_BITRATE", "128k"),
                  "-movflags", "+faststart", str(chapter.m4a))
    with open(chapter.folder / f"{chapter.name}_timings.csv", "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["line", "start_seconds", "exact", "check", "text"])
        for number, (line, start) in enumerate(zip(chapter.lines, starts), 1):
            writer.writerow([number, round(start, 2), "", "", line])
    tts["write_chapter_json"](0, [chapter], metas[0]["model"], metas[0]["voice"], metas[0]["key"])
    listing.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("book")
    parser.add_argument("chapters", nargs="+", help="chapter folder names, e.g. ezra_02")
    parser.add_argument("--parts", type=int, help=f"requests per chapter (default: one per ~{WORDS_PER_REQUEST} words)")
    parser.add_argument("--retry", action="store_true", help="send again the runs that failed the check")
    parser.add_argument("--recheck", action="store_true", help="check the cached audio of the runs that failed again "
                        "(no request)")
    args = parser.parse_args()
    book = tts["book_folder"](args.book)
    from faster_whisper import WhisperModel
    recorder = Recorder(WhisperModel(os.environ.get("WHISPER_MODEL", "base.en"), device="cpu", compute_type="int8"))
    tts["_whisper"] = recorder
    cache = book / "_batches"
    cache.mkdir(exist_ok=True)
    active, requests_made = 0, 0
    for name in args.chapters:
        chapter = tts["Chapter"](book / name)
        count = args.parts or max(2, math.ceil(sum(len(l.split()) for l in chapter.lines) / WORDS_PER_REQUEST))
        runs = split_lines(chapter.lines, count)
        print(f"{name}: {len(chapter.lines)} verses in {len(runs)} requests "
              f"({', '.join(f'{r[0] + 1}-{r[-1] + 1}' for r in runs)})", flush=True)
        metas = []
        try:
            for number, lines in enumerate(runs, 1):
                stem = f"split_{name}_{number}of{len(runs)}"
                mode = "retry" if args.retry else "recheck" if args.recheck else ""
                meta, active = make_run(chapter, lines, stem, cache, recorder, mode, active)
                if meta is None or not meta["is_accepted"]:
                    break
                metas.append({**meta, "stem": stem})
        except tts["QuotaExhausted"]:
            print("daily quota exhausted on every model and key; rerun after the reset (midnight Pacific).")
            sys.exit(1)
        if len(metas) < len(runs):
            print(f"{name}: not built (a request failed or did not pass the check; finished runs stay cached)")
            continue
        build(chapter, metas)
        print(f"{name}: built ({sum(m['seconds'] for m in metas) / 60:.1f} min)")


main()
