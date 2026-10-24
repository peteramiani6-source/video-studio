# config/

Settings for every mode. Scripts read these on each run, so a change applies to the next render with no restart.

## `models.env`: which AI does what, and clip rules

| Setting | Default | Meaning |
|---|---|---|
| `STT` | `local` | transcription: `local` (faster-whisper on your CPU) or `groq` (hosted, needs `GROQ_API_KEY`) |
| `WHISPER_MODEL` / `WHISPER_DEVICE` / `WHISPER_BATCH` | `small` / `cpu` / `8` | local Whisper size, device and batching |
| `PICKER` | `claude-code` | who makes the edit decisions: `claude-code` (your subscription), `claude` (API), `gemini`, `none` |
| `CLIP_COUNT`, `CLIP_MIN`, `CLIP_MAX` | `4`, `25`, `60` | clip mode: how many clips, and their length in seconds |
| `SILENCE_CUT`, `SILENCE_MIN_GAP`, `SILENCE_MARGIN` | `1`, `0.8`, `0.2` | clip mode: cut pauses longer than the gap, keeping a margin |
| `EVENT_SOCIAL_CLIPS`, `EVENT_CLIP_COUNT` | `1`, `5` | event mode: also make vertical clips |

API keys never go here. They go in `.env` in the repo root (gitignored). See `.env.example`.

## `brand.json`: how things look

| Section | Used by | What it controls |
|---|---|---|
| `width`, `height`, `fps`, `caption` | clip, montage | 9:16 size and burned-caption style |
| `hook` | clip, montage | the opening text: `seconds`, `font_size`, `anchor` (`bottom` sits above the captions), `y`, `shadow`, `outline`, `box` |
| `look` | clip, event, montage | `contrast`, `saturation`, `stabilize` (`off`/`deshake`/`vidstab`), `wind_filter` |
| `montage` | montage | `format` (`vertical`/`wide`), target `seconds`, `min_shot`/`max_shot`, `gear_max`, `scene_threshold` |
| `video` | clip, montage | encoder quality (`crf`, `preset`), audio bitrate, loudness normalisation |
| `event` | event | title/end card colours and text, fonts, lower-third timing, fades, loudness |
| `scripture` | scripture | channel brand and voice: `series`, `handle`, `audience`, `tone`, `faith_context`, `background` (two colours), `accent`, `text`, `words_per_second`, music volumes |

Colours are hex (`"#E8B04B"`). Ask Claude Code to change them for you ("make the scripture accent green"), or edit them directly.

## `event.example.json`: template for event details

Copy it into an event folder as `event.json`:

| Field | Meaning |
|---|---|
| `title`, `subtitle` | title card text |
| `speakers` | correct spellings for name tags |
| `notes` | instructions for the edit, e.g. "keep the choir number" |
| `must_keep` | time ranges that are never cut, e.g. `[["00:42:10", "00:47:30"]]` |
| `target_minutes` | aim for a shorter edit; `null` keeps all real content |
