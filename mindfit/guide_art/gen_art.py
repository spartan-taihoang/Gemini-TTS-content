#!/usr/bin/env python3
# Generate MindFit guide artwork with a Gemini image model (square 1:1, PNG), saved next to this script.
# Usage: python3 -I mindfit/guide_art/gen_art.py [slug ...]   (no args = all guides)
# Keys: GEMINI_API_KEY* lines in the .env at the repo root (never printed); tries each key until one has quota.
# The committed .jpg files are these PNGs converted with: sips -s format jpeg -s formatOptions 85 <in.png> --out <out.jpg>
import base64, json, sys, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE.parent.parent / ".env"
MODEL = "gemini-2.5-flash-image"
STYLE = ("Soft painterly digital illustration, calm and contemplative, gentle gradients, no text, no letters, "
         "no people's faces, square composition with a quiet focal point, suited to a faith and sleep meditation app.")
GUIDES = {
    "finding-rest": "A moonlit hillside under a deep indigo night sky, a single lantern glowing, stars, peaceful stillness. Palette: indigo and violet.",
    "calming-an-anxious-heart": "Still blue water at dawn with a gentle ripple, a small boat resting, soft mist. Palette: calm blues.",
    "a-thankful-heart": "A warm golden-hour table with bread, a cup and wildflowers by a window, soft sunlight. Palette: amber and gold.",
    "healing-and-hope": "A green path through a quiet valley as first light breaks over the hills, a small sprouting plant in the foreground. Palette: teal and soft green.",
    "evening-prayer-for-rest": "Open hands holding a small glowing candle against a dark navy dusk sky, tiny stars. Palette: deep navy and warm candlelight.",
    "peace-in-the-psalms": "A shepherd's staff leaning on a rock beside still waters and green pasture under soft clouds, no figures. Palette: sky blue and sage.",
    "morning-thanks": "Sunrise over a quiet field with morning light streaming through trees, a small bird on a branch. Palette: peach, gold and soft orange.",
    "grief-and-comfort": "A single candle and a folded blanket near a window with soft rain outside, tender and quiet. Palette: muted teal and gray-green.",
}


def load_keys(path):
    found = []
    for line in path.read_text().splitlines():
        name, sep, value = line.partition("=")
        if sep and name.strip().startswith("GEMINI_API_KEY"):
            found.append(value.strip().strip("'\""))
    return [k for k in found if k]


def generate(prompt, keys):
    body = {"contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "1:1"}}}
    last = None
    for key in keys:
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
            data=json.dumps(body).encode(), method="POST",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code} {e.read().decode()[:160]}"
            continue
        for cand in data.get("candidates", []):
            for part in cand.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline:
                    return base64.b64decode(inline["data"])
        last = "no image in response: " + json.dumps(data)[:200]
    sys.exit(f"failed: {last}")


if __name__ == "__main__":
    api_keys = load_keys(ENV)
    if not api_keys:
        sys.exit(f"no GEMINI_API_KEY* in {ENV}")
    for slug in (sys.argv[1:] or GUIDES):
        path = HERE / f"{slug}.png"
        path.write_bytes(generate(f"{GUIDES[slug]} {STYLE}", api_keys))
        print("saved", path.name)
