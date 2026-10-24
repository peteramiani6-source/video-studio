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

## Resuming and checking

- **A failed event:** fix the cause, then run `scripts/event.sh --resume <job-id>`. Merge, transcription and (on resume) the plan are skipped when their output exists. To re-plan, delete `work/<job>/plan.json` first.
- **Before anything runs:** `run.sh` and `event.sh` call `scripts/doctor.py`, which checks ffmpeg, the Whisper setup and the `PICKER` login or key. If it prints FAIL lines, fix those first. Run `python3 scripts/doctor.py` any time to see the full check.
- **Unusable model replies:** the plan step retries once with the error, then fails, leaving `plan.json` as it was. The raw replies are kept in `work/<job>/plan_raw.txt`.
- **One job at a time:** a second `run.sh` or `event.sh` waits for the first one to finish.

## Look and feel (`config/brand.json`)

- **`look`**: `contrast` and `saturation` (eq filter), `stabilize` (`off`, `deshake` or `vidstab`; vidstab is smoothest but renders about 5× slower), `wind_filter` (a high-pass at `wind_cutoff_hz`). These apply to both clip and event renders.
- **`hook`**: `seconds` (1.5), `font_size`, `anchor` (`bottom` sits just above the captions at `y`), `shadow`, `outline`, `box`.

Map feedback to settings:
- **"Shaky":** set `stabilize` to `vidstab`.
- **"Washed out":** raise `saturation`, or `contrast` a little.
- **"Windy":** keep `wind_filter` on, and say that a lapel mic is the real fix.
- **"Text too long, too small or hard to read":** change `hook.seconds`, `font_size` or `shadow`.

Focus, glare and a cluttered frame are shooting problems. Point the user to `SHOOTING.md` rather than promising an edit fix.

## Models (`config/models.env`)

- `PICKER=claude-code` is the default. It uses the user's Claude subscription through the `claude` CLI, so no API key is needed. Other options are `claude` (API), `gemini` and `none`.
- `STT=local` runs faster-whisper on the CPU. `STT=groq` is faster and better for recordings over an hour.

## Never

- Modify or delete files in `inbox/`.
- Print API keys.
- Upload or post anything. Output stops at `out/`.
- If a step fails, check `logs/pipeline.log`, fix the cause, and re-run only that step.
