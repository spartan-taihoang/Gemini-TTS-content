# Guide: turning a podcast or prayer script into TTS JSON

Instructions for an AI assistant (or a person) converting a plain-text script into the JSON that `tts_episode.py` reads. The goal is a calm, natural bedtime delivery, made with `style` and inline tags, **without changing the words**.

Give the assistant this file, the plain text, and the host's voice name. Ask for the JSON only.

---

## 1. Hard rules

1. **Keep every word.** The text in the app (`transcript`, `prayer_text`) must match the audio, and `whisper_timings.py` matches lines by their wording. Never add, remove, reorder or reword sentences, including small "natural" fillers like "you know" or "now,".
2. **Only these text changes are allowed:**
   - Write all-caps words in normal case when they are not meant to be stressed (`LORD` → `Lord`). The model stresses ALL-CAPS words.
   - Replace parentheses with `...` (`(by grace ye are saved.)` → `... by grace ye are saved.`).
   - Add a missing final period.
   - Use ALL CAPS on at most one word per episode for deliberate stress (e.g. `RICH in mercy`).
3. **Never put directions in `text`.** Anything in `text` is spoken aloud. Words like `(softly)`, `[pause]` or `Say gently:` go in `style` or become a tag.
4. **Truncated or garbled text: flag it, don't guess.** If a sentence looks cut off (`could be releademanded.`), leave it as is and list it under "Questions" after the JSON. Copying from a terminal often cuts long lines; ask for the text as a file.
5. **Never split one transcript line across two parts.** A part may hold several lines, but each line belongs to exactly one part.

## 2. Output format

```json
{
  "title": "<Series> - Episode <n>: <topic>",
  "voice": "<voice name given by the user>",
  "parts": [
    {"style": "<how this part is delivered>", "text": "<verbatim text with inline tags>"}
  ]
}
```

- Use the same `voice` for every episode of a series. Ask if you don't know which voice to use.
- **Two people (host and guest):** replace `voice` with `"voices": {"David": "Olin", "Maya": "Koda"}` (at most 2) and give every part a `"speaker"` from those names. A part is one person's turn, never both. Don't write `David:` in `text`; the name is only in `speaker`.
- Add `"ambience": {"file": "../../shared_ambience/ambience_soft_pad.flac", "volume_db": -5, "lead_in": 4, "tail": 6}` only when the user asks for a version with background audio. In-app podcasts are voice only.
- **Meditations** use `"volume_db": -12` (file `../../shared_ambience/harmony_sound.flac` or another loop there). The meditation voice speaks softly, around -25 dB against about -20 dB for a prayer, so -5 puts the background as loud as the voice; -12 keeps it about 6–7 dB under.
- Output valid JSON: straight double quotes around keys and values; typographic quotes and apostrophes inside the text are fine.

## 3. Splitting into parts

A part is one **beat**: a stretch read in one manner. Start a new part when the delivery changes.

- Typical new-part points: the welcome, a scripture quotation, the host repeating a verse, a rhetorical question, the turn to "you" and "tonight", the prayer, and the goodnight.
- Group short lines that share a manner into one part. Aim for roughly 1–5 transcript lines per part.
- About 20–35 parts for a 6–7 minute episode. Very short parts are fine when the manner really changes (e.g. `But captivity to what?` on its own as a question).
- The script sends 12 parts per request, so a part boundary is not a request boundary. You don't need to plan around that.

## 4. Styles

Keep `style` short (3–8 words) and in English. Reuse this fixed set so the voice stays consistent across episodes. Create a new style only if none fits, and keep it in the same tone.

| Beat | Style |
|---|---|
| Welcome / opening question | `warm, gentle late-night welcome, a soft smile in the voice, speaking slowly` |
| Teaching, explaining (the baseline) | `thoughtful, calm teaching tone` |
| Reading a scripture verse | `reverent, slow, reading scripture aloud` |
| Host repeating a verse right after it | `slow, reflective, letting the words sink in` |
| Rhetorical question | `curious, gently wondering` |
| Key turn ("But God.", "God moves.") | `quiet, awed emphasis` |
| Short parallel lines ("Not because… / Not because…") | `gentle, steady, building conviction` |
| A list of single words or short phrases | `slow, deliberate, each phrase landing softly` |
| Illustration or story ("Think of a chair.") | `gentle, a soft smile in the voice, illustrating` or `tender, quiet storytelling` |
| Heartfelt one-liner ("This is grace.") | `soft, heartfelt, slower` |
| Reassurance after a hard truth | `quiet, reassuring conviction` |
| Speaking directly to the listener, application | `tender, intimate, very soft, speaking slowly` |
| Prayer | `prayerful, hushed, very slow` |
| Goodnight / closing blessing | `soft, near-whispered, soothing goodnight` |

Avoid energetic styles (`excited`, `surprised`, `dramatic`, `cheerful`): this is bedtime content. Never describe the speaker's age, gender or accent; the `voice` decides that.

## 5. Inline tags

Tags use **angle brackets** and stay in English. Common ones:

| Tag | Use |
|---|---|
| `<short pause>` | Between items of a list or parallel lines, before a key phrase, after a question before its answer |
| `<long pause>` | **Only** at the end of a scripture part. Gemini sometimes reads this tag aloud ("long pause"), far more with Jori, so it is kept to where a long silence really matters |
| `<exhales>` | At most once per episode, at a moment of release ("…trying to be good enough… `<exhales>` here's rest.") |
| `<breath>` | Rarely, before a long scripture verse |
| `<chuckle>` | Once in the welcome, as a warm greeting ("Welcome to Salvation and Grace. `<chuckle>` I'm Jason Greene."). Optionally once more at a light moment: an everyday illustration or a gentle aside about ourselves ("We often want Scripture to be a floodlight, don't we? `<chuckle>`") |

Rules:

- Don't end a part with a tag, except a scripture part, which ends with `<long pause>`. The end of a part and a change of style already make a pause: removing these tags in Faith and Truth ep6 gave as much silence as before (slightly more), and no tag was read aloud.
- Inside a part, use `<short pause>`, never `<long pause>`. "Let's pray." is followed by `<short pause>`.
- Put `<short pause>` after a line, not inside a phrase. Never more than one tag in a row.
- Leave existing `...` in place: they already make a natural pause. Add `<short pause>` after `...` only where the line needs a clearer break.
- `<chuckle>`: put one in the welcome, right after the show name or the host's name, never in the middle of the opening question. Use the welcome style with a smile: `warm, gentle late-night welcome, a soft smile in the voice, speaking slowly`. A second one, if any, goes in a teaching or illustration part with a smiling style (e.g. `gentle, a soft smile in the voice, illustrating`). Never in scripture, prayer, the goodnight, or near a hard truth (sin, death, judgment), where it sounds dismissive.
- Don't use the other laughing, sighing or crying tags (`<laugh>`, `<laughter>`, `<giggle>`, `<sigh>`, `<sob>`, `<gasp>`) in this content.
- Roughly one tag per sentence at most. More tags make the reading choppy.

## 6. Scripture

- A verse is quoted word for word (King James wording in these scripts). Keep its punctuation, `thee`/`thou`, `hath`, etc.
- Give the quotation its own part with the scripture style, and end it with `<long pause>`.
- A verse split across two lines by a terminal or editor is one line: join it.
- If the reference is spoken (e.g. "Genesis, chapter two, verse eighteen"), write numbers as words.

## 7. Daily prayers

A daily prayer has a verse, a reference and a prayer. Every daily prayer uses `"voice": "Charon"` and `"ambience": {"file": "../../shared_ambience/ambience_soft_pad.flac", "volume_db": -5, "lead_in": 4, "tail": 6}` (the JSON sits in `daily_prayer/<name>/`). Use two parts:

```json
{"style": "calm, reverent, reading scripture aloud slowly",
 "text": "And the Lord God said, <short pause> It is not good that the man should be alone; <short pause> I will make him an help meet for him. <short pause> Genesis, chapter two, verse eighteen. <long pause>"},
{"style": "warm, gentle, prayerful, speaking slowly",
 "text": "Lord God, <short pause> thank You for seeing our need for companionship and care. <short pause> Bless the people You have placed beside me, <short pause> and help me to love them as You love me. <short pause> Amen."}
```

## 8. Worked example

Welcome (every episode starts like this):

```json
{"style": "warm, gentle late-night welcome, a soft smile in the voice, speaking slowly",
 "text": "Welcome to Salvation and Grace. <chuckle> I'm Jason Greene. <short pause> Tonight, we're asking a quiet question... <short pause> is there any place too far for God's grace to reach?"}
```

Teaching passage:

Input:

```
Paul begins with two words... but God.

Everything changes... with those two words.

But God.

Into that darkness... into that spiritual death... God moves.

Not because we deserved it.
Not because we earned it.
Not because we were good enough, or tried hard enough.

He moved because of his great love for us.
```

Output parts:

```json
{"style": "thoughtful, calm teaching tone",
 "text": "Paul begins with two words... <short pause> but God. <short pause> Everything changes... with those two words."},
{"style": "quiet, awed emphasis",
 "text": "But God. <short pause> Into that darkness... into that spiritual death... God moves."},
{"style": "gentle, steady, building conviction",
 "text": "Not because we deserved it. <short pause> Not because we earned it. <short pause> Not because we were good enough, or tried hard enough. <short pause> He moved because of his great love for us."}
```

In both, every word of the input is present, in order. Only tags were added.

## 9. Self-check before answering

- [ ] Removing all `<...>` tags from the parts gives back the input text, word for word (apart from the allowed changes in rule 2).
- [ ] No transcript line is split across two parts.
- [ ] Every `style` comes from the table, or is a short phrase in the same tone.
- [ ] `<long pause>` appears only at the end of scripture parts; other parts end with their last word, no tag; no two tags are next to each other.
- [ ] One `<chuckle>` in the welcome and at most one more elsewhere; at most one `<exhales>`; each in a fitting part.
- [ ] No ALL-CAPS word except at most one deliberate stress.
- [ ] The JSON parses.
- [ ] Anything that looked truncated or garbled is listed under "Questions", not guessed.

Also save the plain text, one transcript line per line, as `transcript.txt` next to the JSON. `whisper_timings.py` needs it.
