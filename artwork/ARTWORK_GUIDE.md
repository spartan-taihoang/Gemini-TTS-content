# Guide: creating track artwork with Gemini

For MindFit (and SleepFit). The goal: every track has a cover in one shared style, with a readable white title on top,
that looks right everywhere the app shows it. Batch 1 (done): the tracks on the **Sleep** tab (stories, kids, music,
study, soundscapes), one image per track. Batch 2: **daily prayer** and **meditation**, each with **one shared image**
for every track of that kind (section 5b).

## 1. How the app shows artwork (read this before generating)

| Where | Size | Crop | Drawn on top of the image |
|---|---|---|---|
| Grid card on the Sleep tab (`SleepCard`) | 200 pt tall, about half the screen wide; the app loads the image at **540 × 600 px** (9:10) | aspect fill, rounded corners | **white title, centered, starting 64 pt from the top edge** (about the upper third); **dark pill label at the bottom** (narrator name or "Piano · Ocean"); a lock at the top left if premium |
| Story row / list | square, 64 × 64 and 112 × 112 pt | square crop, corner radius 14 | nothing |
| Player | small square image | square crop | nothing |

What this means:

1. **Generate square 1:1 images**, at least **1024 × 1024 px**. Cropping a square to 9:10 loses only a little on both
   sides, and the same image works as is in the square slots.
2. **Keep the subject in the central 70%**, away from the edges (they get cropped). The **bottom 15%** is cut off
   completely when the watermark is removed (section 4), so put nothing important near the bottom.
3. **The middle and upper third must be dark and low in detail**: the white title sits there. Put no bright or busy
   detail in the middle of the image. The bottom should be dark too, because of the label.
4. **Absolutely no text** in the image (the app draws the title). No logo, no watermark, no signature.
5. Each track already has a **color gradient** (`art_from` → `art_to`), shown while the image loads. Pick image colors
   close to that gradient (the "Gradient" column below) so the colors don't flash when the image appears.

## 2. Upload limits (backend)

- Formats: **JPEG, PNG or WebP**. At most **10 MB** (aim for under 1 MB: JPEG at quality ~85 is enough).
- Artwork is not required to publish: a track without an image still shows its gradient.
- One image can serve several tracks (Vanilla Lo-Fi and Ravel Lo-Fi have 2 tracks each, sharing one image).

## 3. Shared style (keep it the same for every image)

Paste this **style block** at the start of every prompt, then add the track's **subject description** from section 5.

```text
Square 1:1 cover art for a calm bedtime and relaxation app. Soft, painterly digital illustration with gentle
gradients and subtle grain, like a quiet storybook painting. Muted, dusky palette; low contrast; dreamy and warm.
Simple composition: one clear subject in the lower-middle of the frame but well above the bottom edge, with plenty of soft, dark, empty space in
the upper-middle area. Calm, peaceful mood, nothing scary or dramatic, no harsh light. The edges of the image will be
cropped, so keep the subject within the central 70 percent and leave the bottom 15 percent free of anything important. No text, no letters, no numbers, no logos, no
watermark, no signature, no border, no frame.
```

Add a line for the track kind:

| Kind | Append to the style block |
|---|---|
| Sleep story | `Night-time scene, deep blues and indigo, soft moonlight or lamplight glow.` |
| Kids story | `Gentle children's picture-book style, rounded friendly shapes, soft warm colors, cozy and sweet, still calm.` |
| Relaxing music | `Abstract or nature-inspired, flowing soft shapes suggesting music, warm and soothing.` |
| Study music | `Cozy, softly lit desk or window scene, calm focus, warm lamp light, gentle and uncluttered.` |
| Soundscape | `Atmospheric nature scene focused on the sound source, immersive and tranquil, no people.` |

Notes for Gemini:

- Either a Gemini image model (the backend is configured with `gemini-2.5-flash-image`, changed through
  `GEMINI_IMAGE_MODEL`) or the Gemini app / AI Studio works. If you can choose an aspect ratio, choose **1:1**.
- Don't describe real people, copyrighted characters, or the style of a specific living artist.
- People in the image: seen from a distance or from behind, no face close-ups (fewer broken faces and hands).
- If stray lettering appears, generate again with `Absolutely no text or lettering anywhere.` at the end.
- Make 3–4 options per track and pick the one with the darkest, most open middle.

## 4. Workflow

1. Build the prompt: **style block** + the line for the **track kind** + the **subject description** (section 5).
2. Generate 3–4 images and pick 1. Check it against section 6.
3. Save the original in `artwork/`, named after the track (for example `artwork/the_night_train_north.png`).
4. Run **one command** to crop out the watermark and shrink the file:
   ```bash
   python3 artwork/prepare_artwork.py artwork
   ```
   Each original becomes **`<name>_clean_small.jpg`** next to it (the original is kept), and this is the only file you
   need:
   - It crops out **Gemini's sparkle in the bottom-right corner**: it removes 100 px + 6% of the side from the bottom
     (~16% of a 1024 px image, ~11% of a 2048 px one) and takes the centered square.
   - It scales down to **1024 px** (never up, if less than that is left) and saves a **JPEG under 200 KB** at the best
     quality that fits.
   - Options: `--side right` cuts the right side instead of the bottom (keeps the bottom of the image); `--cut 0.18`
     cuts a fixed share if any of the sparkle is left; `--size 800` and `--max-kb 100` for smaller files; `--out DIR`
     to save somewhere else.
   - Running it again is safe: it skips existing `_clean_small` files as inputs and overwrites the results.
   Upload **`_clean_small.jpg`**, never the original.
5. Send it back to Claude to upload to dev and attach to the track (or do it yourself: web-admin → Tracks → open the
   track → Art image → upload). For Vanilla Lo-Fi and Ravel Lo-Fi, attach the same image to both the Relaxing and the
   Study track.

## 5. Tracks that need artwork (batch 1: Sleep tab, 21 images)

### Sleep stories

| Track | Subject description (paste after the style block) | Gradient |
|---|---|---|
| The Shepherd's Lantern | `An old shepherd seen from behind, sitting against a low stone wall on a hilltop at night, a small glowing lantern on a rock beside him, a few sleeping sheep, a sky full of stars.` | #3A4E7A → #0F1630 |
| The Night Train North | `An old green night train with warm glowing windows travelling through a snowy pine forest under a full moon, soft falling snow.` | #4A5D7E → #121A2B |
| The Cottage by the Tide | `A small white cottage with one lit window on the dunes beside a calm sea at dusk, the moon laying a silver path on the water.` | #7FA9B8 → #1C3440 |

### Kids stories

| Track | Subject description | Gradient |
|---|---|---|
| Samuel Hears a Voice | `A small boy sitting up in a simple bed inside a quiet tent, a single golden oil lamp glowing nearby, listening, seen from the side.` | #E8B07A → #5A3A6B |
| The Lost Sheep | `A kind shepherd carrying a small fluffy lamb on his shoulders across moonlit green hills, holding a lantern, seen from a distance.` | #A7C4A0 → #3E5A3A |
| The Big Red Umbrella | `A big friendly brown bear holding a large red umbrella in the rain, with a rabbit, a mouse, a hedgehog, a squirrel and a little bird huddled underneath, a forest path.` | #E07A6B → #6B2A2A |
| Kiko and the Kite | `A little girl seen from behind on a grassy hilltop, flying a handmade paper kite with a long ribbon tail high into a soft evening sky.` | #F2C46D → #4E7FA8 |

### Relaxing music

| Track | Subject description | Gradient |
|---|---|---|
| Quiet Keys | `Soft abstract piano keys dissolving into gentle violet waves of light.` | #8C7BB8 → #2F2650 |
| Soft Piano | `A single upright piano in a dim, warm room, a soft lamp glow, sheet music, calm and empty.` | #D9C4A8 → #4A3A2E |
| Vanilla Lo-Fi (also used for Study) | `A cozy window seat at dusk with a steaming mug, headphones and a vinyl record, warm vanilla and caramel tones.` | #E8C9A0 → #6B4A3A |
| Ravel Lo-Fi (also used for Study) | `An antique piano in a softly lit Parisian room at twilight, lavender light through tall windows.` | #B8A9D9 → #3A2F5C |

### Study music

| Track | Subject description | Gradient |
|---|---|---|
| Piano by the Stream | `A small wooden desk with an open notebook beside a window overlooking a quiet forest stream, morning light.` | #93BFA9 → #2C4E40 |

### Soundscapes

| Track | Subject description | Gradient |
|---|---|---|
| Summer Night Crickets | `Tall grass and wildflowers in a meadow on a warm summer night, fireflies glowing softly, a deep starry sky.` | #4A5A3A → #141C10 |
| Music Box Waltz | `An open antique music box with a tiny turning ballerina, glowing softly on a dark wooden shelf, gentle sparkles.` | #F2D0D9 → #5C3A4A |
| Gentle Rain | `Soft rain falling over a quiet forest at night, misty air, raindrops catching faint light.` | #7E93A8 → #1F2A36 |
| Rain on the Window | `Raindrops running down a window pane at night, the blurred warm glow of a room light behind the glass.` | #6F8BA0 → #16222E |
| Quiet Stream | `A small clear stream flowing over smooth stones in a mossy forest, soft green light.` | #7FB5A8 → #1E3F38 |
| Ocean Waves | `Slow waves rolling onto a wide empty beach at dusk, soft foam, a calm horizon.` | #5E8FB5 → #0F2238 |
| Soft Harmony | `Abstract soft glowing light ribbons floating in a deep violet space, like a calm aurora.` | #B8A0C9 → #2E2340 |

Old tracks that don't need artwork: Canon in D (already has an image), River flows in you (test track). The two
devotionals (New Every Morning, The Good Shepherd) aren't shown anywhere in iOS yet, so they come later.

### Ambient sounds (background sounds users mix under a session)

Rain and Ocean reuse the images of the Gentle Rain and Ocean Waves tracks (same audio), so there is nothing to
generate for them. Only Fireplace is left. For the kind line, use the **Soundscape** one.

| Ambient | File name | Subject description |
|---|---|---|
| Fireplace | `fireplace.png` | `A cozy stone fireplace with a softly glowing wood fire in a dark, quiet room, warm embers, a knitted blanket draped over an armchair nearby. No people.` |

Ambient images will show in the player's background-sound mixer (not built yet, #42), so they follow the rules in
section 1 too.

## 5b. Batch 2: daily prayer and meditation (2 shared images)

No separate image per track: **1 image for all 31 daily prayers** and **1 image for all 19 meditations**. Within each
kind only the words differ, so one shared image per kind keeps the app tidy and consistent; the title on the card
(drawn by the app) already tells the tracks apart. Claude uploads each image **once** and attaches it to every track
of that kind.

The app doesn't use these images anywhere yet (the Meditation tab and Home's daily cards aren't built; First Session,
Library and Player don't show track images yet), but they should be on dev so they appear as soon as those screens
are ready.

Because one image has to suit every track, keep the subject **generic, not tied to one verse or one theme**: no
people, no text, no symbol that belongs to a single track.

Build the prompt as in section 4: **style block (section 3)** + the kind line below + **subject description**. Make
3–4 options, pick 1, save it in `artwork/` under the exact file name, then run `prepare_artwork.py` as usual.

| Kind (track count) | File name | Kind line (append to the style block) | Subject description |
|---|---|---|---|
| Daily prayer (31) | `daily_prayer.png` | `Quiet, reverent evening mood, warm candlelight against deep blue dusk, gentle and hopeful.` | `A small wooden table by an open window at dusk, a single lit candle and an open old book resting beside it, soft curtains moving in the breeze, a few stars appearing in the deep blue sky outside. No people, no hands.` |
| Meditation (19) | `meditation.png` | `Serene, spacious and still, soft mist and gentle light, a feeling of slow breathing.` | `A perfectly still lake at twilight surrounded by soft misty hills, a single small tree on the shore reflected in the water, the last warm glow of the sun on the horizon and the first stars above. No people.` |

Tips for each kind:

- **Daily prayer**: warm tones (candle, dusk light) on deep blue, the feel of an evening prayer. Don't draw praying
  hands or a kneeling person: they break easily and tie the image to one specific picture. If the book's pages have
  writing on them, add `The book's pages are blank, no writing.` and generate again.
- **Meditation**: cool, spacious, still (lake, mist, twilight). The sky at the top must be dark and empty so the title
  reads well. No lotus flower, meditation pose or symbols of other religions (this is a Christian app).

Gradients: the 31 prayers currently have 6 different gradients and the 19 meditations have 5, by collection (shown
while the image loads). Once a shared image is up, Claude can set the gradient of every track of that kind to the
image's 2 main colors so the colors don't change on load; tell Claude if you want that.

## 6. Checklist before uploading

- [ ] Square, ≥ 1024 px, JPEG/PNG/WebP, under 10 MB.
- [ ] No text, numbers or logos; `prepare_artwork.py` has been run and the Gemini sparkle is gone (upload the `_clean_small.jpg` file).
- [ ] The middle and upper third are dark enough for white text (try putting a large white title on the image).
- [ ] The subject is in the central 70% and survives a 9:10 crop and a small square crop.
- [ ] The main colors are close to the track's gradient.
- [ ] Same style as the existing images (put them side by side to compare).
- [ ] No real people, no copyrighted characters, no distorted faces or hands.
