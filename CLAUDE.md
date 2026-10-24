# Video Studio

Raw recordings go into `inbox/`. Results come out in `out/<job-id>/`:
- **Event mode** (`scripts/event.sh`): a full edited video, a highlight reel, subtitles, YouTube chapters, and social clips
- **Montage mode** (`scripts/montage.sh`): a shot-based edit picked from the frames (behind the scenes, promos)
- **Clip mode** (`scripts/run.sh`): captioned 9:16 clips

## Rules
- Never edit or delete files in `inbox/`. `scripts/run.sh` moves a source to `archive/` only after the job succeeds.
- Each job works only inside `work/<job-id>/` and writes results to `out/<job-id>/`.
- For any request to edit, clip, caption or reframe a video, use the `video-edit` skill.
- To change an event edit, edit `work/<job>/plan.json` and re-run `scripts/render_event.py`. Don't re-transcribe.
- To change a montage, edit `work/<job>/edit.json` (look at `work/<job>/frames/sheet_*.jpg` first) and re-run `scripts/render_shots.py`.
- Mechanical steps (cutting, cropping, subtitles, rendering) use FFmpeg or Remotion only. Use a model only to
  choose moments and shots and write titles, hooks and captions.
- Model choices live in `config/models.env`. Caption styling lives in `config/brand.json`. Don't hard-code either.
- Read keys from `.env`. Never print, log or commit them.
- Every run appends to `logs/pipeline.log`.
- If a step fails, read the log, fix the cause, and re-run only the failed step. Every step is safe to re-run.

## Layout
- `scripts/`: the pipeline (`run.sh` runs everything for one file)
- `.claude/skills/video-edit/`: the skill Claude Code loads
- `remotion/`: programmatic videos (React), set up separately
