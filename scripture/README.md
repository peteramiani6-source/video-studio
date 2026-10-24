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
scripts/scripture.sh voice ep004                      # AI voiceover (narrator + character), see Voiceover below
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
| `hook` | Claude, then you | the opening line on screen (≤ 70 characters). Not shown when there's a skit |
| `skit` | Claude (`new --skit`), then you | optional comic opening, see Skits below |
| `reflection` | Claude, then you | what it means today (≤ 420 characters) |
| `apply` | Claude, then you | 1–3 "live it this week" points (≤ 90 characters each) |
| `closing` | Claude, then you | an end-card question that invites comments |
| `caption`, `hashtags` | Claude, then you | for the post (goes to `post.md`) |
| `format` | you | `vertical`, `wide` or `both` |
| `voiceover` | you, or `voice` | `audio/ep004_ai.wav` (set by `voice`), or your own recording, e.g. `audio/ep004.mp3` |
| `music` | you | e.g. `music/calm-piano.mp3`. Plays quietly under the voice and fades out at the end |
| `reviewed` | **you** | starts `false`. Set it to `true` only after reading the whole script |

## Skits: a comic opening with the character

An episode can open with a short skit: the channel's cartoon character acting out the everyday situation the verse speaks to, before the verse lands. See `ep004.json` (overthinking at 2:47 AM, then Philippians 4:6–7).

```bash
scripts/scripture.sh new "Galatians 6:9" --theme "procrastinating" --skit   # Claude drafts the skit too
```

A skit is a list of **beats**, shown in order with hard cuts (comic timing), in place of the hook:

```json
"skit": [
  {"shot": "wide", "bg": "#1D2540", "pose": "lying", "face": "wide", "caption": "2:47 AM", "seconds": 2.0},
  {"shot": "closeup", "bg": "#FFFFFF", "pose": "talk", "face": "worried", "caption": "What if I fail the exam...", "talk": true, "seconds": 2.4},
  {"shot": "wide", "bg": "flash", "pose": "panic", "face": "wide", "caption": "AND MY WHOLE FUTURE?!", "thoughts": ["exam", "rent", "fees"], "seconds": 2.6},
  {"shot": "wide", "bg": "#FFFFFF", "pose": "idle", "face": "deadpan", "caption": "...okay. Wait.", "seconds": 1.8}
]
```

| Field | Options |
|---|---|
| `shot` | `wide` (full body) or `closeup` (face fills the frame) |
| `bg` | any colour (`"#FFFFFF"`), or `"flash"` to cycle the flash colours for a chaotic moment |
| `pose` | `idle`, `talk`, `shrug`, `think`, `facepalm`, `panic`, `pray`, `laugh`, `wave`, `lying` (in bed) |
| `face` | `neutral`, `deadpan`, `wide`, `worried`, `happy`, `peace`, `laugh` |
| `caption` | big comic text at the top, ≤ 60 characters |
| `say` | what the character says out loud in the voiceover (≤ 90 characters); empty = silent beat. A talking beat with no `say` speaks its caption |
| `talk` | `true` makes the mouth move |
| `thoughts` | up to 6 short words popping up around the head |
| `seconds` | 0.6–6 per beat; the whole skit stays under 20 s |

**Tone rule (Claude follows it, you check it in review):** the joke is about us (overthinking, procrastinating, 2 AM worries), never about God, the scriptures or anything sacred, and never mocking anyone. End the skit on a quiet "wait…" beat so the verse lands as the answer.

The character is the channel's own design. Change its colours under `scripture.character` in `config/brand.json`. To see every pose and face: `cd remotion && npx remotion still src/index.ts CharacterSheet sheet.png`.

`check` and `render` warn when an episode runs past 60 seconds, the sweet spot for Reels and Shorts. Shorten the reflection, an apply point or the skit.

## Rules this mode follows

- **The verse is never written by the model.** It comes from `data/kjv.json.gz` and is checked again at render time.
- **Nothing publishes unreviewed.** A video without `"reviewed": true` can only be rendered as a draft, which has `DRAFT · NOT REVIEWED` stamped on it.
- **Claude is told to stay faithful to the verse in context** and not add doctrine it doesn't teach. A person still checks every script; ideally someone whose judgment you trust reviews the first batch too.

## The Bible text

`data/kjv.json.gz` is the King James Version (1769 text, 66 books, 31,102 verses). It's in the public domain almost everywhere. In the UK it's under Crown patent, which allows quotation like this. Most modern translations (NIV, ESV and others) are copyrighted and limit how much you can quote, so they aren't bundled. For other Church texts, check the publisher's terms before building a channel on them.

## Voiceover

**AI voice (free, on your computer):**

```bash
scripts/scripture.sh voice ep004            # writes audio/ep004_ai.wav and sets it as the voiceover
scripts/scripture.sh render ep004 --draft
scripts/scripture.sh voice --voices         # list voices; pick them in config/models.env (TTS_NARRATOR, TTS_CHARACTER)
```

- Two voices: the **character** speaks the skit lines (`say`), the **narrator** reads the hook, the reference and verse, the reflection, the points and the closing question.
- Each scene lasts as long as its line, so the verse appears word by word while it is read, each "live it" point appears as it's spoken, and the character's mouth follows the voice.
- Engine: [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (Apache 2.0), about 1.5 s of CPU per second of speech. `setup.sh` downloads it (~120 MB into `models/kokoro/`). After that it works offline.
- The verse is read exactly as the KJV has it. Only the reference is said in words ("Philippians chapter 4, verses 6 to 7").
- Change any words (or the skit timing or voices) and `check`/`render` say the voiceover is out of date. Run `voice` again; unchanged lines come from a cache, so it's quick.
- The voices are American or British English. For a Kenyan or East African sound, your own voice (below) will connect better. The AI voice is good for drafts and for testing timing.

**Your own voice:**

```bash
scripts/scripture.sh voice ep004 --script   # prints every line in order: CHARACTER / NARRATOR
```

Record it in one take, save as `audio/ep004.mp3` and set `"voiceover": "audio/ep004.mp3"`. The scenes stretch to fit your recording, and the character's mouth follows your voice during talking beats. One session can cover a whole batch.

## Music

- Use only music you have the rights to: YouTube Audio Library, Pixabay Music, or a licensed library.
- Without a voiceover, scene lengths come from reading speed (`words_per_second` in `brand.json`).

## Changing the look

Colours, series name and handle are in `config/brand.json` under `scripture`. The animation itself (layout, motion, fonts) is the Remotion template in `remotion/src/scripture/`. See [remotion/README.md](../remotion/README.md).
