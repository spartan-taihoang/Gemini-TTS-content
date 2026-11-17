# Gemini TTS – audio for podcasts and daily prayers

These scripts turn a script file (JSON) into an MP3 with Gemini TTS (`gemini-3.8-flash-tts`). They are used for SleepFit content. **The audio and folder structure is for reference. You only need the python script.**

## Layout

```
gemini-tts/
├── tts_episode.py          # main script: JSON -> MP3
├── align_timings.py        # estimates start_seconds from existing audio (no API calls)
├── podcast/
│   └── <episode>/
│       ├── <episode>.json
│       ├── <episode>.mp3            # generated
│       ├── <episode>_timings.csv    # generated (TTS_PER_PART=1 mode)
│       └── <episode>_parts/         # per-chunk audio cache
└── daily_prayer/
    ├── ambience_soft_pad.flac       # self-made background pad, no third-party license, loops seamlessly every 60 s
    ├── <name>.json
    ├── <name>.mp3
    └── <name>_ambience.mp3          # version with background (when the JSON has "ambience")
```

Every output file is written next to its JSON file.

## Setup (once)

```bash
cd ~/tools/gemini-tts
python3 -m venv .venv && source .venv/bin/activate   # optional: the scripts use only the standard library
sudo apt install -y ffmpeg                          # needed to join and mix audio
```

Create an API key in Google AI Studio. To set it without showing it on screen or saving it in your shell history:

```bash
read -rs GEMINI_API_KEY && export GEMINI_API_KEY
```

After pasting, check that the key does not start with `200~`. Some terminals insert those characters when you paste, and they are not part of the key.

## Running

```bash
python3 tts_episode.py podcast/salvation_and_grace_ep1/salvation_and_grace_ep1.json
python3 tts_episode.py daily_prayer/genesis_2_18.json
```

| Environment variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Gemini API key |
| `TTS_MODEL` | `gemini-3.8-flash-tts` | Model to use. Switch to `gemini-3.8-flash-lite-tts` when the main model is overloaded |
| `TTS_PER_PART` | (off) | `1` = send one request per part and also write `_timings.csv` |

### What the script does

1. Groups the `parts` into chunks: 6 parts per request by default, or 1 part per request with `TTS_PER_PART=1`.
2. Calls the Gemini API (REST `v1beta`) once per chunk and saves each result in `<name>_parts/n6/` or `<name>_parts/n1/`.
3. Joins the chunks into `<name>.mp3`.
4. If the JSON has `ambience`, also writes `<name>_ambience.mp3` with the background mixed in.
5. With `TTS_PER_PART=1`, writes `<name>_timings.csv` with the start time of each part, ready to enter as `start_seconds` in web-admin.

On HTTP 429, 500 or 503 (overload or quota), the script retries up to 6 times. The wait starts at 15 seconds, doubles after each failure, and is capped at 5 minutes.

### Regenerating one chunk

The script skips any chunk that already has a file in `_parts/`. To redo a chunk, delete its `chunk_XX.wav` and run the same command again. Only the missing chunk is sent to the API, and the MP3 is rebuilt.

## JSON format

```json
{
  "title": "Faith and Truth - Episode 2",
  "voice": "Aoede",
  "ambience": {"file": "ambience_soft_pad.flac", "volume_db": -12, "lead_in": 4, "tail": 6},
  "parts": [
    {"style": "warm, gentle late-night welcome, speaking slowly",
     "text": "Welcome to Faith and Truth. <short pause> I'm Sarah Mitchell. <long pause>"},
    {"style": "reverent, slow, reading scripture aloud",
     "text": "Now faith is the substance of things hoped for, the evidence of things not seen. <long pause>"}
  ]
}
```

| Field | Required | Description |
|---|---|---|
| `title` | no | A label for your own reference. The script does not use it |
| `voice` | yes | Voice name, e.g. `Charon`, `Kore`, `Aoede`, `Enzo`. Listen to the voices in AI Studio before choosing |
| `parts[].style` | yes | How the whole part is delivered (emotion, pace, volume). Keep it short and in English |
| `parts[].text` | yes | What is spoken, **word for word**. Tags can be added inline |
| `ambience` | no | Adds a version with background audio. See the fields below |

`ambience` fields:

- `file`: path to the background audio, relative to the JSON's folder.
- `volume_db`: background level. -12 is a good default; use -9 for louder or -15 for quieter.
- `lead_in`: seconds of background before the voice starts.
- `tail`: seconds of background after the voice ends, fading out.

### Writing `text`

- The model speaks **every word** in `text`. Never put directions such as `(whispering)` or `Say softly:` here, because they will be read aloud. Directions go in `style`.
- **ALL-CAPS** words are spoken with emphasis. Write `Lord`, not `LORD`. Use all caps only where you want emphasis, e.g. `RICH in mercy`.
- Use punctuation to shape the rhythm: commas, `...` and `--`.
- Check the source text for truncated sentences before generating. Some text taken from the database has had missing words.

### Inline tags in `text`

Tags use **angle brackets**, not square brackets, and are always written in English:

- Pauses: `<short pause>`, `<long pause>`
- Breath and emotion: `<breath>`, `<exhales>`, `<sigh>`, `<chuckle>`, `<laugh>`, `<whispers>`, `<yawn>`, `<gasp>`, …

For bedtime content, use mostly the pause tags, with an occasional `<exhales>`, and keep the other tags to a minimum.

### Writing `style`

Reuse a fixed set of styles so the voice stays consistent across episodes:

| Used for | Style |
|---|---|
| Opening | `warm, gentle late-night welcome, speaking slowly` |
| Teaching (baseline) | `thoughtful, calm teaching tone` |
| Reading scripture | `reverent, slow, reading scripture aloud` |
| Repeating a verse | `slow, reflective, letting the words sink in` |
| Rhetorical question | `curious, gently wondering` |
| Key moment | `quiet, awed emphasis` |
| Speaking to the listener | `tender, intimate, very soft, speaking slowly` |
| Prayer | `prayerful, hushed, very slow` |
| Goodnight | `soft, near-whispered, soothing goodnight` |

Tips:

- Keep styles short. Do not put age, gender or accent in a style; those come from the `voice`.
- When the delivery changes noticeably, start a new part with its own style.

## Entering `start_seconds` in web-admin

- **New audio:** run with `TTS_PER_PART=1` and copy the numbers from `_timings.csv`. Each CSV row is one **part** of the JSON. If a part contains several transcript lines, only the first line of that part gets an exact time.
- **Audio already made in the default mode, which you want to keep:**
  ```bash
  python3 align_timings.py <name>.json transcript.txt <name>_parts/n6 <name>_timings.csv
  ```
  `transcript.txt` holds one transcript line per line. The times are estimated from the silences in the audio:
  - Rows marked `exact=yes` are exact.
  - Rows marked `check=listen` may be off; play the audio at that time and correct the value by hand if needed.
- Always take timings from the **voice-only** file. The `_ambience` version is shifted by `lead_in` seconds.
- A CSV only matches the MP3 from **the same run**. Every new API call produces a slightly different reading, because Gemini TTS does not give identical output between runs.

## Troubleshooting

| Error | Cause / fix |
|---|---|
| `HTTP 400 ... Unknown name` | The request contains a field the API does not accept. Check the JSON. If the error mentions `voice`, change `speechConfig` to use `prebuiltVoiceConfig.voiceName` |
| `HTTP 401/403` | Wrong key, or not a Gemini API key. Create a new key in AI Studio |
| `HTTP 429` | Quota exceeded. The script retries automatically. Quotas apply per project, not per key, and the daily quota resets at midnight Pacific time |
| `HTTP 503` | The model is overloaded. The script retries automatically. If it keeps failing, delete `_parts/` and run with `TTS_MODEL=gemini-3.8-flash-lite-tts`, so the episode does not mix chunks from two models |

## Limits & cost

- Per request: up to 8,192 input tokens and 16,384 output audio tokens (about 10 minutes of audio). A 6-part request uses far less than this.
- Flash TTS costs about $0.014 per minute of audio (estimated from 25 tokens per second at $9 per 1M output tokens). A 10-minute episode costs about $0.14.
- Never commit an API key. Revoke and replace any key that has been exposed.
