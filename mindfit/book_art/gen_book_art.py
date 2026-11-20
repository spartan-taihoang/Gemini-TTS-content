#!/usr/bin/env python3
# Generate one nature texture picture per Bible book for MindFit's Daily Bible card (16:9, PNG), saved next to this script.
# Style follows Abide's Daily Bible: a photographic close-up of one natural surface (water, leaves, stone, grass, sky) in
# rich saturated color, with the card's white book name and chapter laid over it. No buildings, objects, animals or people.
# The carousel card is 280 x 150 pt (about 1.87:1) and the See all list shows a 96 pt square, so the picture is a texture
# with no focal object in the middle: any crop of it still works.
# Usage: python3 -I mindfit/book_art/gen_book_art.py [number ...]   (no args = every book listed in BOOKS)
# Files are named <number>_<slug>.png where number is the canon book number (Genesis 1 ... Revelation 66), the key the
# app looks the picture up by. Keys: GEMINI_API_KEY* lines in the .env at the repo root (never printed).
# The committed .jpg files are the PNGs converted with: sips -s format jpeg -s formatOptions 85 <in.png> --out <out.jpg>
import base64, json, sys, urllib.error, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ENV = HERE.parent.parent / ".env"
MODEL = "gemini-2.5-flash-image"
STYLE = ("Photographic nature close-up, shot as a macro or detail photograph with natural soft depth of field. "
         "Rich, deep, saturated color in mid-tones, not pastel, not washed out and not black: bright enough to feel "
         "alive, dark enough for white text to read over it. The texture fills the whole frame evenly with no "
         "single object in the center. Strictly nature: no buildings, no man-made objects, no people, no animals. "
         "The image contains no text of any kind: no letters, words, captions, signs, signatures, or watermarks, "
         "including in the corners. Wide landscape frame, for a Bible and meditation app.")
# number: (slug, subject and palette).
BOOKS = {
    1: ("genesis", "Sunlit turquoise sea surface with fine ripples and light dappling. Palette: turquoise and aqua."),
    2: ("exodus", "Wet rippled sand at the edge of deep blue water. Palette: deep blue and sand."),
    3: ("leviticus", "Smooth warm river stones packed together in soft side light. Palette: ochre and terracotta."),
    4: ("numbers", "Fine sand dune ripples in soft warm light, calm and natural. Palette: warm sand, soft amber and pale gold."),
    5: ("deuteronomy", "Layered rock strata of a cliff face. Palette: rust and slate blue."),
    6: ("joshua", "Clear river water flowing over pebbles. Palette: teal and amber."),
    7: ("judges", "Close-up of a desert acacia branch with small feathery leaves and thorns, soft backlight. Palette: olive green and warm gold."),
    8: ("ruth", "Golden barley ears in warm light. Palette: wheat gold and brown."),
    9: ("1-samuel", "Smooth wet river pebbles. Palette: blue-gray and green."),
    10: ("2-samuel", "Silvery olive leaves on a branch. Palette: silver green and violet."),
    11: ("1-kings", "Dense cedar needles and branches. Palette: deep forest green."),
    12: ("2-kings", "A bright clear daytime sky, medium sky-blue with soft white cumulus clouds and warm sunlight, a natural unedited photograph look. Palette: sky blue and white."),
    13: ("1-chronicles", "Velvet green moss on stone. Palette: emerald."),
    14: ("2-chronicles", "Warm sandstone surface with fine layers. Palette: sand and dusty rose."),
    15: ("ezra", "Gray-green lichen on rock. Palette: gray-green and cream."),
    16: ("nehemiah", "Weathered rough rock surface with moss in the cracks. Palette: slate and moss green."),
    17: ("esther", "Purple lavender flowers close-up. Palette: royal purple and violet."),
    18: ("job", "Only sky filling the entire frame: a bright morning sky after rain, soft clouds parting to clear blue with gentle sunlight. Nothing but sky and clouds, no ground, no plants, no horizon, no trees. A natural unedited photograph look. Palette: sky blue, soft white and a touch of pale gold."),
    19: ("psalms", "Green grass blades with dew drops. Palette: vivid green and sky blue."),
    20: ("proverbs", "Fern fronds close-up in sunlight. Palette: vivid green and gold."),
    21: ("ecclesiastes", "Ocean wave foam and tide pattern on teal water. Palette: aqua and sea green."),
    22: ("song-of-solomon", "Pink blossoms on a branch close-up. Palette: rose pink and plum."),
    23: ("isaiah", "Desert wildflowers close-up. Palette: magenta and gold."),
    24: ("jeremiah", "Cracked red clay earth with a faint green sprout. Palette: terracotta and deep red."),
    25: ("lamentations", "Raindrops on a dark green leaf. Palette: deep green and silver."),
    26: ("ezekiel", "Dry golden grass bending in wind with motion blur. Palette: gold and sage."),
    27: ("daniel", "Rough rock surface lit by warm golden light. Palette: umber and gold."),
    28: ("hosea", "Red poppy petals close-up. Palette: poppy red and crimson."),
    29: ("joel", "Fresh green sprouts with dew after rain. Palette: lime green and deep green."),
    30: ("amos", "River rapids over dark rocks. Palette: teal and white foam."),
    31: ("obadiah", "Red rock canyon wall in sunset light. Palette: red rock and orange."),
    32: ("jonah", "Deep blue ocean swell surface. Palette: deep ocean blue and cobalt."),
    33: ("micah", "Silver-green olive leaves in sunlight. Palette: olive green and silver."),
    34: ("nahum", "Dark turbulent river surface reflecting storm clouds. Palette: deep teal and charcoal blue."),
    35: ("habakkuk", "Rugged rock surface against an orange sky glow. Palette: gray-blue and orange."),
    36: ("zephaniah", "Layered mauve dusk clouds. Palette: mauve and amber."),
    37: ("haggai", "Pebbles and wet sand with fine grain. Palette: warm gray and amber."),
    38: ("zechariah", "Olive leaves in deep blue twilight. Palette: deep green and indigo."),
    39: ("malachi", "Sunrise rays breaking through clouds. Palette: orange and gold."),
    40: ("matthew", "Wildflower field close-up in morning light. Palette: coral, cream and green."),
    41: ("mark", "Calm lake surface with soft ripples. Palette: teal and slate."),
    42: ("luke", "Warm golden grass close-up in low light. Palette: amber and honey."),
    43: ("john", "Deep starry night sky with soft glow. Palette: deep blue and violet."),
    44: ("acts", "Fresh green leaves in bright morning sunlight moving in a gentle breeze with soft motion blur, light and airy. Palette: bright green and warm gold."),
    45: ("romans", "Smooth pebble shore meeting a thin wave. Palette: stone gray and rose gold."),
    46: ("1-corinthians", "Sea-worn rock with wave spray. Palette: marble gray and sea blue."),
    47: ("2-corinthians", "Cracked clay earth with tiny wildflowers growing through. Palette: clay brown and gold."),
    48: ("galatians", "Open green meadow grass under a blue sky. Palette: sky blue and fresh green."),
    49: ("ephesians", "Layered clouds above a sea horizon. Palette: navy and warm amber."),
    50: ("philippians", "Spring blossoms close-up. Palette: soft pink and green."),
    51: ("colossians", "Lavender sky with beams of light through clouds. Palette: lavender and gold."),
    52: ("1-thessalonians", "Dawn glow opening in the sky over dark fields. Palette: midnight blue and amber."),
    53: ("2-thessalonians", "Dense star field over dark hills. Palette: night blue and warm yellow."),
    54: ("1-timothy", "Aged oak wood grain. Palette: oak brown and gold."),
    55: ("2-timothy", "Red autumn leaves close-up. Palette: deep red and flame orange."),
    56: ("titus", "Turquoise Mediterranean water with silver olive leaves at the edge. Palette: turquoise and olive."),
    57: ("philemon", "White jasmine flowers on dark green leaves. Palette: white, green and soft gold."),
    58: ("hebrews", "A bright blue daytime sky with thin white wispy cirrus clouds, clean and open, a natural unedited photograph look. Palette: clear sky blue and white."),
    59: ("james", "Fresh green leaves with raindrops. Palette: vivid green and amber."),
    60: ("1-peter", "Blue-green sage leaves close-up. Palette: cobalt blue and teal."),
    61: ("2-peter", "A bright morning star above misty mountains before sunrise. Palette: deep blue and pale gold."),
    62: ("1-john", "Dark red leaf with fine veins in macro. Palette: crimson and burgundy."),
    63: ("2-john", "Ivy leaves climbing a rock surface. Palette: green and soft gold."),
    64: ("3-john", "Rosemary and lavender sprigs in warm light. Palette: forest green and violet."),
    65: ("jude", "Rocky coast with waves and spray. Palette: dark teal and pale gold."),
    66: ("revelation", "Radiant clouds with golden rays of light. Palette: gold, violet and pale blue."),
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
            "generationConfig": {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "16:9"}}}
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
    for number in ([int(a) for a in sys.argv[1:]] or BOOKS):
        slug, scene = BOOKS[number]
        path = HERE / f"{number:02d}_{slug}.png"
        path.write_bytes(generate(f"{scene} {STYLE}", api_keys))
        print("saved", path.name)
