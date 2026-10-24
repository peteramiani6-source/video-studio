# scripts/

The pipeline. Each mode has one **entry script** (`.sh`) that runs the health check, takes the job lock and calls the **steps** (`.py`) in order. Every step can also be run on its own with a job id, and every step is safe to re-run.

## Entry scripts

| Script | Mode | Steps it runs |
|---|---|---|
| `event.sh <file-or-folder> [title] [subtitle]` / `--resume <job>` | Event | merge → transcribe → plan_event → render_event → render (social clips) |
| `montage.sh <file-or-folder> [brief]` / `--resume <job>` | Montage | merge → transcribe (speech optional) → shots → plan_shots → render_shots |
| `run.sh <file> [job]` | Clip | prepare → transcribe → pick_clips → render |
| `scripture.sh new / show / check / voice / render` | Scripture | scripture.py, voice.py (+ Remotion) |
| `watch.sh` | Clip, automatic | watches `inbox/`, runs `run.sh` per new video; Claude Code steps in if a step fails |

## Steps

| File | What it does | Writes |
|---|---|---|
| `prepare.sh` | copies the source into the job without re-encoding | `work/<job>/tight.mp4` |
| `merge.py` | joins a folder of clips (mixed phone/camera) or remuxes one file | `tight.mp4`, `sources.json` |
| `transcribe.py` | speech to text with word timings (`STT=local` or `groq`) | `transcript.srt`, `words.json` |
| `pick_clips.py` | the model picks the strongest moments | `clips.json` |
| `render.py` | cuts clips, removes pauses, crops 9:16, burns the hook and captions | `out/<job>/clip_NN_*.mp4`, `captions.md` |
| `plan_event.py` | the model writes the event edit (keep/cut, chapters, speakers) | `plan.json`, `clips.json` |
| `render_event.py` | title/end cards, segments with name tags, highlights, SRT, chapters | `event_full.mp4`, `event_highlights.mp4`, `youtube.md` |
| `shots.py` | scene cuts, sharpness, motion, keyframes, contact sheets | `shots.json`, `frames/sheet_NN.jpg` |
| `plan_shots.py` | the model *looks at the sheets* and orders the shots | `edit.json` |
| `render_shots.py` | renders the shot list: crop follows the subject, look, captions, hook | `montage.mp4`, `montage.md` |
| `scripture.py` | scripture episodes: KJV lookup, drafting, review gate, Remotion render | `scripture/episodes/*.json`, `out/scripture/<id>/` |
| `voice.py` | AI voiceover (Kokoro, local): narrator + character, scene timing, lip sync; `--script` for your own recording | `scripture/audio/<id>_ai.wav` + `.json` |

## Shared modules

| File | Purpose |
|---|---|
| `common.py` | paths, `.env` + `config/models.env` loading, logging, SRT and time helpers, ffprobe |
| `llm.py` | the only place that talks to a model: `ask(prompt, images)`, `ask_json(...)` with validation and one retry |
| `look.py` | colour, stabilization and wind filter from `brand.json` → `look` |
| `lock.sh` | one heavy job at a time (`flock`) |
| `doctor.py` | the health check: `--mode video` (default), `scripture`, `scripture-write`, `scripture-voice` |

## Conventions

- **Job folders:** a job works only in `work/<job>/` and writes results only to `out/<job>/`. Sources in `inbox/` are never modified; they move to `archive/` after success.
- **Model output:** always validated before it's written. Times are parsed, broken entries dropped, and the step fails loudly if nothing usable is left. Raw replies are kept next to the output (`*_raw.txt`).
- **Settings:** come from `config/`. Nothing is hard-coded in the scripts.
- **Logs:** every step logs to `logs/pipeline.log`.
