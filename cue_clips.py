# Turn a short-cue episode (one spoken line per part, e.g. breath cues) into one M4A clip per cue.
# Usage: TTS_PER_PART=1 python3 tts_episode.py <folder>/<name>.json   (one request, so one file, per cue)
#        python3 cue_clips.py <folder>/<name>.json
# Reads "cues" (one name per part, same order) from the JSON, trims the silence around each part's own take in
# <name>_parts/n1/, and writes clips/<cue>.m4a. Pauses inside a line are kept. Writes nothing unless every part has
# its take, so a clip never lands under the wrong cue. To redo one cue, delete its chunk_NN.wav and run both again.
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SILENCE_DB = -40
# Kept at both ends so a clip doesn't start or end on a clipped consonant.
EDGE_PAD = 0.05
# Longest each cue should be (spec 5.2); longer ones are reported, not rejected.
HINTS = {"intro": 5.0, "inhale": 1.0, "hold": 1.5, "exhale": 1.0, "finish": 4.0}


def duration(audio):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(audio)]))


def spoken_span(audio):
    """(start, end) in seconds from the first to the last sound above SILENCE_DB."""
    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(audio), "-af",
                          f"silencedetect=noise={SILENCE_DB}dB:d=0.05", "-f", "null", "-"],
                         capture_output=True, text=True, check=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", log)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", log)]
    total = duration(audio)
    start = ends[0] if starts and starts[0] <= 0.01 and ends else 0.0
    # The trailing silence runs to the end of the file; some ffmpeg builds close it there, others leave it open.
    end = starts[-1] if starts and (len(starts) > len(ends) or ends[-1] >= total - 0.01) else total
    if end - start <= 0:
        sys.exit(f"{audio} is silent")
    return start, end


def write_clips(sources, names, out_dir):
    """One AAC .m4a per name from its source take, swapped into out_dir only once every clip is written."""
    missing = [str(s) for s in sources if not Path(s).is_file()]
    if len(sources) != len(names) or missing:
        sys.exit(f"need one take per cue ({len(names)}); missing: {', '.join(missing) or len(names) - len(sources)}")
    out_dir = Path(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=".clips-", dir=out_dir.parent))
    try:
        for name, source in zip(names, sources):
            start, end = spoken_span(source)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source),
                            "-ss", f"{max(0.0, start - EDGE_PAD):.3f}",
                            "-to", f"{min(duration(source), end + EDGE_PAD):.3f}",
                            "-vn", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                            str(work / f"{name}.m4a")], check=True)
        if out_dir.exists():
            shutil.rmtree(out_dir)
        work.rename(out_dir)
    finally:
        if work.exists():
            shutil.rmtree(work)
    return [out_dir / f"{name}.m4a" for name in names]


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: python3 cue_clips.py <folder>/<name>.json")
    src = Path(sys.argv[1])
    ep = json.loads(src.read_text())
    names = ep.get("cues") or sys.exit('the JSON needs "cues": one name per part')
    if len(names) != len(ep["parts"]):
        sys.exit(f'"cues" has {len(names)} names for {len(ep["parts"])} parts')
    takes = src.parent / f"{src.stem}_parts" / "n1"
    sources = [takes / f"chunk_{n:02d}.wav" for n in range(len(names))]
    for clip in write_clips(sources, names, src.parent / "clips"):
        seconds = duration(clip)
        hint = HINTS.get(clip.stem)
        warn = f"  WARNING over {hint:.1f}s" if hint and seconds > hint else ""
        print(f"{clip.stem:<8} {seconds:5.2f}s  {clip}{warn}")


if __name__ == "__main__":
    main()
