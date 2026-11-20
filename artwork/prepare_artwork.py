# Prepare Gemini artwork for upload in one step: crop out the sparkle watermark, square it, scale it down and save a
# JPEG under a size limit.
# Usage: python3 artwork/prepare_artwork.py <image | folder> [...] [--side bottom|right] [--cut 0.15]
#                                          [--size 1024] [--max-kb 200] [--out DIR]
# Each <name>.<png|jpg|jpeg|webp> becomes <name>_clean_small.jpg next to it (or in --out); the original is kept.
# A folder is searched recursively and skips files that are already _clean_small. Needs ffmpeg.
#
# Watermark: the sparkle grows slower than the image. It covers 97-143 px from the bottom and right edges on a
# 1024 px image and 65-160 px on a 2048 px one. The default cut, 100 px + 6% of the side (161 px at 1024, 223 px at
# 2048), clears both. --side bottom (default) cuts the bottom and keeps the whole top, where the app draws the
# title; --side right keeps the bottom instead. --cut 0.15 cuts a fixed share of the side.
#
# Size: the app loads track art at 540 x 600 px, so 1024 px is plenty. The JPEG takes the best quality that fits under
# --max-kb (the backend allows 10 MB, but a small file loads faster on a phone).
import argparse, json, subprocess, sys, tempfile
from pathlib import Path

EXTS = {".png", ".jpg", ".jpeg", ".webp"}
SUFFIX = "_clean_small"

parser = argparse.ArgumentParser()
parser.add_argument("paths", nargs="+")
parser.add_argument("--side", choices=["bottom", "right"], default="bottom")
parser.add_argument("--cut", type=float, help="share of the side to cut off (default: 100 px + 6%% of the side)")
parser.add_argument("--size", type=int, default=1024, help="output width and height in px (default 1024)")
parser.add_argument("--max-kb", type=int, default=200, help="largest output file in KB (default 200)")
parser.add_argument("--out", help="output folder (default: next to each image)")
args = parser.parse_args()

images = []
for arg in args.paths:
    p = Path(arg)
    if p.is_dir():
        # Skip earlier outputs (and the _clean / _small files of the old two-script flow).
        images += sorted(f for f in p.rglob("*") if f.suffix.lower() in EXTS
                         and not f.stem.endswith((SUFFIX, "_clean", "_small")))
    elif p.suffix.lower() in EXTS and p.is_file():
        images.append(p)
    else:
        sys.exit(f"not an image or folder: {arg}")
if not images:
    sys.exit("no images found")

for src in images:
    info = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                               "stream=width,height", "-of", "json", str(src)]))["streams"][0]
    w, h = info["width"], info["height"]
    cut = round(min(w, h) * args.cut) if args.cut else round(100 + 0.06 * min(w, h))
    if args.side == "bottom":
        side = min(w, h - cut)                       # rows below h - cut hold the sparkle
        x, y = (w - side) // 2, 0
    else:
        side = min(w - cut, h)                       # columns right of w - cut hold the sparkle
        x, y = 0, (h - side) // 2
    size = min(args.size, side)                      # never enlarge past what the crop kept
    vf = f"crop={side}:{side}:{x}:{y},scale={size}:{size}:flags=lanczos"
    out_dir = Path(args.out) if args.out else src.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"{src.stem}{SUFFIX}.jpg"
    with tempfile.TemporaryDirectory() as tmp:
        trial = Path(tmp) / "trial.jpg"
        # ffmpeg's JPEG quality: 2 is best, 31 worst. Take the best that fits; stop at 12 to keep it clean.
        for q in range(2, 13):
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vf", vf, "-q:v", str(q),
                            "-frames:v", "1", str(trial)], check=True)
            if trial.stat().st_size <= args.max_kb * 1024:
                break
        trial.replace(dst)
    kb = dst.stat().st_size / 1e3
    note = "" if kb * 1e3 <= args.max_kb * 1024 else f" (still over {args.max_kb} KB at the lowest allowed quality)"
    print(f"{src.name}: {w}x{h}, cut {cut} px from the {args.side} -> {dst.name}: {size}x{size}, {kb:.0f} KB, "
          f"quality {q}{note}")
