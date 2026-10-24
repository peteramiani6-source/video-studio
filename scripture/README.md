# scripture/

Content for **scripture mode**: short animated videos that show one passage and how to live it. The default series name is "One Verse, Real Life"; change it under `scripture` in `config/brand.json`.

```
scripture/
├── episodes/     one JSON file per episode (ep001.json, ep002.json, ...)
├── data/         kjv.json.gz: the King James Version, bundled
├── audio/        your voiceover recordings (not in git)
└── music/        royalty-free background music (not in git)
```

## Making an episode

```bash
scripts/scripture.sh new "Philippians 4:6-7" --theme "anxiety at night"   # Claude drafts the words
scripts/scripture.sh show ep004                                            # read it as a script
# edit scripture/episodes/ep004.json until it's right, then set "reviewed": true
scripts/scripture.sh render ep004                     # vertical by default
scripts/scripture.sh render ep004 --format both       # vertical and wide (YouTube)
scripts/scripture.sh render ep004 --draft             # quick half-size preview, allowed before review
scripts/scripture.sh render --all                     # every reviewed episode that has no video yet
scripts/scripture.sh check                            # validate every episode
```

Videos go to `out/scripture/<id>/`, together with `post.md` (caption, hashtags and the quoted verse).

## The episode file

| Field | Written by | Notes |
|---|---|---|
| `reference` | you | "Proverbs 3:5-6", "1 Cor 13:4-7", "Ps 23". Up to 8 verses, within one chapter |
| `reference_display`, `verse` | the tool | the exact KJV text. **Never edit by hand.** `check` and `render` refuse a verse that doesn't match the KJV. `check --fix` restores it |
| `hook` | Claude, then you | the opening line on screen (≤ 70 characters) |
| `reflection` | Claude, then you | what it means today (≤ 420 characters) |
| `apply` | Claude, then you | 1–3 "live it this week" points (≤ 90 characters each) |
| `closing` | Claude, then you | an end-card question that invites comments |
| `caption`, `hashtags` | Claude, then you | for the post (goes to `post.md`) |
| `format` | you | `vertical`, `wide` or `both` |
| `voiceover` | you | e.g. `audio/ep004.mp3`. The video stretches to fit the voiceover's length |
| `music` | you | e.g. `music/calm-piano.mp3`. Plays quietly under the voice and fades out at the end |
| `reviewed` | **you** | starts `false`. Set it to `true` only after reading the whole script |

## Rules this mode follows

- **The verse is never written by the model.** It comes from `data/kjv.json.gz` and is checked again at render time.
- **Nothing publishes unreviewed.** A video without `"reviewed": true` can only be rendered as a draft, which has `DRAFT · NOT REVIEWED` stamped on it.
- **Claude is told to stay faithful to the verse in context** and not add doctrine it doesn't teach. A person still checks every script; ideally someone whose judgment you trust reviews the first batch too.

## The Bible text

`data/kjv.json.gz` is the King James Version (1769 text, 66 books, 31,102 verses). It's in the public domain almost everywhere. In the UK it's under Crown patent, which allows quotation like this. Most modern translations (NIV, ESV and others) are copyrighted and limit how much you can quote, so they aren't bundled. For other Church texts, check the publisher's terms before building a channel on them.

## Voiceover and music

- Record each episode in one take: hook, verse, reflection, the points, the closing question. One session can cover a whole batch. Save the files as `audio/<id>.mp3` and set `"voiceover"` in each episode.
- Use only music you have the rights to: YouTube Audio Library, Pixabay Music, or a licensed library.
- Without a voiceover, scene lengths come from reading speed (`words_per_second` in `brand.json`).

## Changing the look

Colours, series name and handle are in `config/brand.json` under `scripture`. The animation itself (layout, motion, fonts) is the Remotion template in `remotion/src/scripture/`. See [remotion/README.md](../remotion/README.md).
