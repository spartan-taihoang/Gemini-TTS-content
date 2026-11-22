# Bible audio replaced after its first version (to re-upload)

Chapters below already had audio in an earlier version and were made again. Upload their files again to replace the old
ones. Chapters that had no audio before (new chapters) are not listed here.

Each chapter folder holds four files that all changed together: `<chapter>.m4a`, `<chapter>.mp3`, `<chapter>.json`,
`<chapter>_timings.csv` (the timings no longer match the old audio).

Path: `mindfit/bible/<testament>/<NN_book>/<chapter>/`

| Book | Chapters | Count | What changed | Commit |
|---|---|---|---|---|
| New Testament / 40_matthew | matthew_01 to matthew_28 | 28 | Charon (Gemini 2.5 Flash) replaced by Cruz (Gemini 3.8) | 0579376 |
| New Testament / 41_mark | mark_01 to mark_16 | 16 | Charon (2.5 Pro and 3.8) replaced by Cruz (3.8) | 0579376 |
| New Testament / 45_romans | romans_01 to romans_16 | 16 | Charon (Gemini 2.5 Flash) replaced by Cruz (Gemini 3.8) | 0579376 |
| Old Testament / 01_genesis | genesis_01, genesis_02 | 2 | Made again | 7fab9bb |
| Old Testament / 19_psalms | psalms_023 | 1 | Charon replaced by Cruz | c00f2c0 |

Total: 63 chapters, 252 files (4 per chapter).

John (43_john) is still all Charon (Gemini 3.8) and was not changed.

Commits are the ones in which each file changed last (`git log -- <path>`); the oldest files can be listed with
`git log --diff-filter=M --name-only -- 'mindfit/bible/**/*.m4a'`.
