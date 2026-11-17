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
│       ├── <episode>_timings.csv    # start_seconds per line (TTS_PER_PART=1 or align_timings.py)
│       └── <episode>_parts/         # per-chunk audio cache
└── daily_prayer/
    ├── ambience_soft_pad.flac       # self-made background pad, no third-party license, loops seamlessly every 60 s
    ├── <name>.json
    ├── <name>.mp3
    └── <name>_ambience.mp3          # version with background (when the JSON has "ambience")
```

Every output file is written next to its JSON file.

## Setup on macOS (once)

1. Install Homebrew if it is not installed yet (see https://brew.sh). Then install Python 3 and ffmpeg:
   ```bash
   brew install python ffmpeg
   ```
   ffmpeg is needed to join and mix audio. The scripts use only Python's standard library, so there is nothing to `pip install`.

2. Check that both tools are available:
   ```bash
   python3 --version && ffmpeg -version | head -1
   ```

3. Create an API key in Google AI Studio and store it in the macOS Keychain, so it is never written to a file or your shell history. Paste the key when prompted:
   ```bash
   security add-generic-password -a "$USER" -s gemini-api-key -w
   ```
   After pasting, check that the key does not start with `200~`. Some terminals insert those characters when you paste, and they are not part of the key.

4. Load the key in each new terminal before running the scripts:
   ```bash
   export GEMINI_API_KEY="$(security find-generic-password -a "$USER" -s gemini-api-key -w)"
   ```
   To replace the key later, run `security delete-generic-password -a "$USER" -s gemini-api-key`, then repeat step 3.

## Running

```bash
python3 tts_episode.py podcast/salvation_and_grace_ep1/salvation_and_grace_ep1.json
python3 tts_episode.py daily_prayer/genesis_2_18.json
```

| Environment variable | Default | Meaning |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Gemini API key |
| `TTS_MODEL` | `gemini-3.8-flash-tts` | Model to use. Switch to `gemini-3.8-flash-lite-tts` when the main model is overloaded |
| `TTS_PARTS_PER_REQUEST` | `12` | Parts per API call. 12 is about 3 minutes of audio, so an episode takes 2–3 requests |
| `TTS_PER_PART` | (off) | `1` = one request per part (same as `TTS_PARTS_PER_REQUEST=1`) and also write `_timings.csv` |

### What the script does

1. Groups the `parts` into chunks: 12 parts per request by default (`TTS_PARTS_PER_REQUEST`), or 1 part per request with `TTS_PER_PART=1`.
2. Calls the Gemini API (REST `v1beta`) once per chunk and saves each result in `<name>_parts/n<N>/`, where N is the parts per request (e.g. `n12/`, `n1/`). Changing N starts a new folder, so takes made with different settings are never mixed.
3. Joins the chunks into `<name>.mp3`.
4. If the JSON has `ambience`, also writes `<name>_ambience.mp3` with the background mixed in.
5. With `TTS_PER_PART=1`, writes `<name>_timings.csv` with the exact start time of each part. In the default mode, use `align_timings.py` instead (see below).

On HTTP 429, 500 or 503 (overload or quota), the script retries up to 6 times. The wait starts at 15 seconds, doubles after each failure, and is capped at 5 minutes.

### Regenerating one chunk

The script skips any chunk that already has a file in `_parts/`. To redo a chunk, delete its `chunk_XX.wav` and run the same command again. Only the missing chunk is sent to the API, and the MP3 is rebuilt.

## JSON format

To turn a plain-text script into this JSON (or to have an AI assistant do it), follow [SCRIPT_GUIDE.md](SCRIPT_GUIDE.md).

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
  python3 align_timings.py <name>.json transcript.txt <name>_parts/n12 <name>_timings.csv
  ```
  `transcript.txt` holds one transcript line per line. The times are estimated from the silences in the audio:
  - Rows marked `exact=yes` are exact.
  - Rows marked `check=listen` may be off; play the audio at that time and correct the value by hand if needed.
  - Only the first line of each chunk is exact, so larger chunks mean fewer exact rows. On episode 1, most estimates were within 1 second, but some lines in the middle of a 12-part chunk were off by about 3 seconds. Spot-check a few rows mid-chunk even when they are not flagged.
  - The script reads the parts-per-chunk count from the folder name (`n12` = 12). Chunks stored directly in `<name>_parts/` come from older runs, which always used 6.
  - It uses the pause tags in the JSON as hints: a line followed by `<long pause>` should end at a long silence.
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

- Per request: up to 8,192 input tokens and 16,384 output audio tokens (about 10 minutes of audio). A 12-part request is about 3 minutes of audio. Don't put a whole episode in one request: long takes drift in voice and are expensive to redo.
- Flash TTS costs about $0.014 per minute of audio (estimated from 25 tokens per second at $9 per 1M output tokens). A 10-minute episode costs about $0.14.
- Never commit an API key. Revoke and replace any key that has been exposed.
