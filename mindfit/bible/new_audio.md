# Bible audio made for chapters that had none before (to upload)

These chapters had no audio before and were made in commit `542f91c`. Upload their files as new (nothing is replaced).
Each chapter folder holds four files: `<chapter>.m4a`, `<chapter>.mp3`, `<chapter>.json`, `<chapter>_timings.csv`.

Path: `mindfit/bible/<testament>/<NN_book>/<chapter>/`

| Book | Chapters | Count |
|---|---|---|
| New Testament / 44_acts | acts_03, acts_04, acts_05, acts_06, acts_22 | 5 |
| New Testament / 51_colossians | colossians_03, colossians_04 | 2 |
| Old Testament / 02_exodus | exodus_35 | 1 |
| Old Testament / 03_leviticus | leviticus_13, leviticus_17, leviticus_18, leviticus_24 | 4 |
| Old Testament / 04_numbers | numbers_07, numbers_24, numbers_33 | 3 |
| Old Testament / 05_deuteronomy | deuteronomy_11 | 1 |
| Old Testament / 06_joshua | joshua_22 | 1 |
| Old Testament / 09_1_samuel | 1_samuel_28 | 1 |
| Old Testament / 14_2_chronicles | 2_chronicles_15, _16, _17, _21, _22, _23 | 6 |
| Old Testament / 15_ezra | ezra_02 | 1 |
| Old Testament / 16_nehemiah | nehemiah_07, nehemiah_09 | 2 |
| Old Testament / 17_esther | esther_05 | 1 |
| Old Testament / 18_job | job_19 | 1 |
| Old Testament / 23_isaiah | isaiah_14 | 1 |
| Old Testament / 26_ezekiel | ezekiel_21 | 1 |
| Old Testament / 28_hosea | hosea_07, hosea_08, hosea_09 | 3 |
| Old Testament / 36_zephaniah | zephaniah_01, zephaniah_02 | 2 |

Total: 36 chapters, 144 files (4 per chapter).

The first 29 chapters were made in commit `542f91c`. Acts 22, Ezekiel 21, Hosea 8–9, Nehemiah 7 and Zephaniah 1–2 were made later, from the same kind of split requests.

Chapters made in several requests (Acts 3–6, Colossians 3–4, Numbers 7, Ezra 2, Nehemiah 7, and others) were joined from their parts; their parts stay cached in `_batches/`, which is not committed.
Nehemiah 7's verse timings for 51–59 are estimated by word count, not measured.

To list the files again: `git show --diff-filter=A --name-only 542f91c -- 'mindfit/bible/**/*.m4a'`.
