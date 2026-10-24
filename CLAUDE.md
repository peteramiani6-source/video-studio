# Video Studio

Raw recordings go into `inbox/`. Results come out in `out/<job-id>/`:
- **Event mode** (`scripts/event.sh`): a full edited video, a highlight reel, subtitles, YouTube chapters, and social clips
- **Montage mode** (`scripts/montage.sh`): a shot-based edit picked from the frames (behind the scenes, promos)
- **Clip mode** (`scripts/run.sh`): captioned 9:16 clips
- **Scripture mode** (`scripts/scripture.sh`): animated verse episodes from `scripture/episodes/*.json` (Remotion)

## Rules
- Never edit or delete files in `inbox/`. `scripts/run.sh` moves a source to `archive/` only after the job succeeds.
- Each job works only inside `work/<job-id>/` and writes results to `out/<job-id>/`.
- For any request to edit, clip, caption or reframe a video, use the `video-edit` skill.
- To change an event edit, edit `work/<job>/plan.json` and re-run `scripts/render_event.py`. Don't re-transcribe.
- To change a montage, edit `work/<job>/edit.json` (look at `work/<job>/frames/sheet_*.jpg` first) and re-run `scripts/render_shots.py`.
- Mechanical steps (cutting, cropping, subtitles, rendering) use FFmpeg or Remotion only. Use a model only to
  choose moments and shots and write titles, hooks and captions.
- Scripture: never write or alter verse text (it comes from the bundled KJV), and never set `"reviewed": true`. Only the user reviews.
- Model choices live in `config/models.env`. Caption styling lives in `config/brand.json`. Don't hard-code either.
- Read keys from `.env`. Never print, log or commit them.
- Every run appends to `logs/pipeline.log`.
- If a step fails, read the log, fix the cause, and re-run only the failed step. Every step is safe to re-run.

## Layout
Every important folder has a README.md; read it before changing that folder.
- `scripts/`: the pipeline (one entry script per mode, plus steps)
- `config/`: models.env, brand.json, event template
- `remotion/`: animation templates (React); `scripture/`: episodes, KJV, audio
- `docs/`: Windows setup, shooting checklist; `tests/`: unit and render tests
- `.claude/skills/video-edit/`: the skill Claude Code loads
