#!/usr/bin/env python3
# Generate cover pictures for MindFit's Bible plans that read from several books (a plan of one book borrows that
# book's picture from mindfit/book_art), with a Gemini image model (4:3, PNG), saved next to this script.
# 4:3 because the plan detail's header is 1170 x 870 px; the list card crops it to a square. The title is drawn over the
# picture by the app, so the picture has no text and no figures, and its lower half stays calm and dark enough for it.
# Usage: python3 -I mindfit/plan_art/gen_plan_art.py [slug ...]   (no args = every plan listed in PLANS)
# Keys: GEMINI_API_KEY* lines in the .env at the repo root (never printed); tries each key until one has quota.
# The committed .jpg files are these PNGs converted with: sips -s format jpeg -s formatOptions 85 <in.png> --out <out.jpg>
import base64, json, sys, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE.parent.parent / ".env"
MODEL = "gemini-2.5-flash-image"
STYLE = ("Cinematic natural landscape photograph, soft atmospheric light, rich saturated color in mid-tones, not "
         "pastel and not washed out. The lower third is calm and a little darker so white text can sit over it. "
         "Strictly nature: no buildings, no man-made objects, no people, no animals. The image contains no text of any "
         "kind: no letters, words, captions, signs or watermarks. Wide frame for a Bible and meditation app.")
# slug (the plan's title in kebab case): subject and palette.
PLANS = {
    "new-testament-in-90-days": "Sunrise over a calm lake with a path of golden light across the water and layered "
                                "blue hills in the distance, the first light of a new day. Palette: deep blue and gold.",
    "psalms-of-comfort": "A quiet meadow beside still water at twilight under a soft lavender sky, gentle mist over "
                         "the grass. Palette: violet and soft green.",
    "life-of-jesus": "Rolling hills above a lake at sunrise with wildflowers and a narrow footpath leading toward the "
                     "water, no figures. Palette: sky blue and warm gold.",
    "letters-of-hope": "A winding country road through green hills toward a bright warm horizon in clear morning "
                       "light. Palette: fresh green and gold.",
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
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "4:3"}}}
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
    for slug in (sys.argv[1:] or PLANS):
        path = HERE / f"{slug}.png"
        path.write_bytes(generate(f"{PLANS[slug]} {STYLE}", api_keys))
        print("saved", path.name)
