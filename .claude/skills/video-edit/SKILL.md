---
name: video-edit
description: Edit videos in this repo. Use it for full edited event videos (title card, trimmed talks, lower-thirds, highlights, YouTube chapters) and for captioned 9:16 clips for Reels, Shorts and TikTok. Use it whenever you're asked to edit, cut, clip, caption or reframe a recording, or when a new file lands in inbox/.
---

# video-edit

There are two modes. Run both from the repo root.

## A. Event mode: one finished video from a long recording

```bash
scripts/event.sh <video-or-folder> "Event title" "Subtitle (date, venue)"
```

**Input:** a single file, or a folder of clips. A folder's clips are joined in filename order, and mixed phone and camera footage is normalised to 1920x1080.

**Optional event.json:** put one in the folder, or next to the file with the same name. Copy `event.example.json` to start. It can hold:
- `speakers`: the correct spellings for lower-thirds
- `notes`: for example "keep the choir number"
- `must_keep`: time ranges that are never cut
- `target_minutes`: a target length for the edit

**Steps (each one can be re-run on its own with the job id):**

| # | Command | Output |
|---|---------|--------|
| 1 | `python3 scripts/merge.py <src> <job>` | `work/<job>/tight.mp4` |
| 2 | `python3 scripts/transcribe.py <job>` | `transcript.srt`, `words.json` |
| 3 | `python3 scripts/plan_event.py <job> --title ".." --subtitle ".."` | `plan.json`, `clips.json` |
| 4 | `python3 scripts/render_event.py <job>` | `out/<job>/event_full.mp4`, `event_highlights.mp4`, `event_full.srt`, `youtube.md` |
| 5 | `python3 scripts/render.py <job>` | vertical social clips plus `captions.md` |

**plan.json is the edit.** Each entry in `segments` has `start` and `end` (seconds in `tight.mp4`), plus `label` (the chapter title), `speaker` and `role` (for the lower-third). `highlights` and `social_clips` follow the same pattern.

When the user asks for changes, edit `work/<job>/plan.json` and re-run step 4 only:
- **"Cut the part where...":** find it in `transcript.srt`, then remove or split that segment.
- **"Keep the song after the second talk":** add a segment covering that gap.
- **"Wrong name or title":** fix `speaker`, `role` or `label`.
- **"Shorter edit":** drop the weakest segments, and say which ones you dropped.

While iterating, render with `--draft --skip-highlights`. That makes a half-resolution preview (`event_full_draft.mp4`) in a fraction of the time and leaves the final files alone. Once the user is happy, run step 4 again without `--draft`. Styling (colours, fonts, card text, loudness) lives in `config/brand.json` under `event`. To add a logo or intro music, put `logo.png` or `intro_music.mp3` in `assets/`.

## B. Clip mode: short vertical clips from a talk or podcast

```bash
scripts/run.sh inbox/<file>
```

The steps are `prepare.sh` (a stream copy, no re-encode), then `transcribe.py`, then `pick_clips.py`, then `render.py`. `render.py` cuts pauses inside each clip using the word timestamps (`SILENCE_CUT`, `SILENCE_MIN_GAP` and `SILENCE_MARGIN` in `config/models.env`). Clip times in `clips.json` refer to the original recording. The output is `out/<job>/clip_NN_*.mp4` plus `captions.md`.

To change one clip, edit `work/<job>/clips.json`, then run `python3 scripts/render.py <job> --only N`.
Each clip's `hook` is burned into its first seconds (styling under `hook` in `config/brand.json`).

To resume a failed job after fixing the cause, run `scripts/run.sh inbox/<file> <job>`. It skips the steps that already have output and archives the source when it succeeds.

## Models (`config/models.env`)

- `PICKER=claude-code` is the default. It uses the user's Claude subscription through the `claude` CLI, so no API key is needed. Other options are `claude` (API), `gemini` and `none`.
- `STT=local` runs faster-whisper on the CPU. `STT=groq` is faster and better for recordings over an hour.

## Never

- Modify or delete files in `inbox/`.
- Print API keys.
- Upload or post anything. Output stops at `out/`.
- If a step fails, check `logs/pipeline.log`, fix the cause, and re-run only that step.
