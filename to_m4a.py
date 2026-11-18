# Convert MP3 files to M4A (AAC in an MP4 container), which is the only audio format SleepFit accepts.
# Usage: python3 to_m4a.py <file.mp3 | folder> [...]   (a folder is searched recursively for *.mp3)
# Each <name>.mp3 becomes <name>.m4a next to it; the MP3 is kept. Needs ffmpeg. AAC_BITRATE=96k overrides the default.
import os, subprocess, sys
from pathlib import Path

BITRATE = os.environ.get("AAC_BITRATE", "128k")

if len(sys.argv) < 2:
    sys.exit(__doc__)

mp3s = []
for arg in sys.argv[1:]:
    p = Path(arg)
    if p.is_dir():
        mp3s += sorted(p.rglob("*.mp3"))
    elif p.suffix.lower() == ".mp3" and p.is_file():
        mp3s.append(p)
    else:
        sys.exit(f"not an mp3 file or folder: {arg}")
if not mp3s:
    sys.exit("no .mp3 files found")

for mp3 in mp3s:
    m4a = mp3.with_suffix(".m4a")
    # faststart puts the index at the front so the file can start playing before it has fully downloaded.
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-vn", "-c:a", "aac", "-b:a", BITRATE,
                    "-movflags", "+faststart", str(m4a)], check=True)
    print(f"{mp3} -> {m4a} ({m4a.stat().st_size / 1e6:.1f} MB)")
