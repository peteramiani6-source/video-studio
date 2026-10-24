# video-studio

Two things it does:

- **Event mode:** turns a long event recording (or a folder of phone and camera clips) into a finished video. You get a title card, the dead time cut out, each talk kept whole, speaker lower-thirds, fades, balanced audio and an end card. You also get a highlight reel, subtitles, YouTube chapters and vertical social clips.
- **Montage mode:** for short edits judged on the picture (behind the scenes, promos, recaps). The editor looks at a keyframe of every shot, skips blurry and shaky ones, puts the shots in story order (wide → close-ups → a human ending), and slides the vertical crop onto the people.
- **Clip mode:** drop a talk or podcast into `inbox/` and get captioned 9:16 clips, plus a `captions.md` ready to post.

Claude Code orchestrates through the `video-edit` skill. A model handles judgment calls only (choosing moments and writing copy). FFmpeg does all the cutting and rendering.

```
inbox/ -> [1 prepare] -> [2 transcribe] -> [3 pick clips] -> [4 render + cut pauses] -> out/<job>/
          stream copy    Whisper/Groq      Claude/Gemini      FFmpeg
```

## Quick start

```bash
./setup.sh                              # venv, deps, tool checks
claude                                  # log in once with your Claude subscription, then /exit
cp ~/Videos/episode1.mp4 inbox/
scripts/run.sh inbox/episode1.mp4       # run once by hand first
```

### Edit a whole event

```bash
cp event.example.json "inbox/Fireside Night/event.json"   # optional: speakers, notes, must_keep
scripts/event.sh "inbox/Fireside Night" "YSA Fireside Evening" "Langata Ward | 14 Nov 2026"
```

The results go to `out/event-.../`:

| File | What it is |
|---|---|
| `event_full.mp4` | The finished edit (1080p) |
| `event_highlights.mp4` | A 1–2 minute highlight reel |
| `event_full.srt` | Subtitles matched to the edited video |
| `youtube.md` | Title, description and chapters to paste into YouTube |
| `clip_NN_*.mp4` | Vertical clips for Reels, Shorts and TikTok |
| `captions.md` | Captions for those clips |

To review the edit, open `work/<job>/plan.json`, or run `claude` and just ask (for example "drop the announcements", "Grace's surname is spelled Wanjirũ", "make it under 20 minutes"). It updates the plan and re-renders without re-transcribing. While iterating, `python3 scripts/render_event.py <job> --draft --skip-highlights` renders a fast half-resolution preview (`event_full_draft.mp4`).

### Make a behind-the-scenes or promo montage

```bash
scripts/montage.sh "inbox/Garden BTS" "behind the scenes of our garden interview"
```

The result is `out/montage-.../montage.mp4` plus `montage.md` (the hook, caption, hashtags and the cut list with reasons). To see what the editor saw, open the contact sheets in `work/<job>/frames/`. To change the cut, edit `work/<job>/edit.json` (or ask Claude Code, for example "open on the wide shot, less tripod"), then run `python3 scripts/render_shots.py <job>`.

### Clips on autopilot

```bash
scripts/watch.sh                        # runs the pipeline; Claude Code steps in only if a step fails
MODE=claude scripts/watch.sh            # Claude Code processes every file
MODE=direct scripts/watch.sh            # never calls Claude Code
```

**On Windows:** see `WINDOWS.md` (WSL2 setup, Explorer inbox, auto-start). On Linux, see `deploy/video-studio.service`.

## Ask Claude Code

Run `claude` in this folder, then ask things like:
- "Process inbox/episode2.mp4"
- "Clip 3 of the last job starts too early, start it at the question instead and re-render"
- "Make the captions bigger and yellow"
- "Give me 6 clips of 20-30 seconds from the last job"

## Which AI does what

| Step | Default | Switch in `config/models.env` |
|---|---|---|
| Orchestration | Scripts; Claude Code fixes failures | `MODE=claude` / `MODE=direct` in the watcher |
| Transcription | faster-whisper (local) | `STT=groq` |
| Edit decisions, clip picking, copy | Your Claude subscription via Claude Code | `PICKER=claude` (API), `gemini`, `none` |
| Shot choice in montages (sees the frames) | Your Claude subscription via Claude Code | same `PICKER` setting |
| Cut / reframe / captions | FFmpeg | — |
| Pause removal (inside clips) | FFmpeg, from word timestamps | `SILENCE_CUT=0` |

## Layout

```
CLAUDE.md                     rules Claude Code follows here
.claude/skills/video-edit/    the skill (auto-loaded by Claude Code in this folder)
config/models.env             model routing + clip rules
config/brand.json             caption font/colours, output size, encode quality
scripts/event.sh              event mode: full edited video
scripts/merge.py              joins and normalises event clips
scripts/plan_event.py         the model writes the edit (plan.json)
scripts/render_event.py       title/end cards, segments, lower-thirds, highlights, SRT, chapters
scripts/llm.py                one place for model calls (subscription, API or Gemini)
scripts/montage.sh            montage mode: shot-based edit from what the camera saw
scripts/shots.py              scene cuts, sharpness, motion, keyframes, contact sheets
scripts/plan_shots.py         the model looks at the sheets and orders the shots (edit.json)
scripts/render_shots.py       renders edit.json: crop follows the subject, look, captions, hook
scripts/run.sh                clip mode: full pipeline for one file
scripts/prepare.sh            step 1 (stream copy, no re-encode)
scripts/transcribe.py         step 2
scripts/pick_clips.py         step 3
scripts/render.py             step 4
scripts/watch.sh              inbox watcher (inotify / fswatch / polling)
deploy/video-studio.service   systemd user unit
remotion/                     code-generated videos
assets/                       optional logo.png and intro_music.mp3
event.example.json            event details template
SHOOTING.md                   on-set checklist (focus, glare, framing, audio)
inbox/ work/ out/ archive/ logs/
```

## Notes

- **Before you shoot:** read `SHOOTING.md`. Focus, glare and a cluttered frame can't be fixed in the edit.
- **Look:** colour, stabilization and the wind filter live under `look` in `config/brand.json` (`stabilize`: `off` / `deshake` / `vidstab`).
- `python3 scripts/doctor.py` checks that ffmpeg, Whisper and your chosen model (login or key) are ready. `run.sh` and `event.sh` run it automatically first.
- Resume a failed event with `scripts/event.sh --resume <job-id>`. Finished steps (the merge and the long transcription) are skipped.
- Only one job renders at a time. A second one waits instead of slowing both down.
- Run `python3 -m unittest discover -s tests` for the fast unit tests, and `tests/smoke.sh` for the full render test.

- Each step is safe to re-run. To tweak one clip, edit `work/<job>/clips.json` and run
  `python3 scripts/render.py <job> --only 3`.
- `tests/smoke.sh` renders a generated test video through both modes with real FFmpeg and no models.
  GitHub Actions runs it on every pull request (`.github/workflows/ci.yml`).
- To resume a failed clip job, run `scripts/run.sh inbox/<file> <job>`. Finished steps are skipped.
- Each clip opens with its `hook` on screen. Style it, or turn it off, under `hook` in `config/brand.json`.
- A failed file goes into `logs/failed.txt` and the watcher skips it. Delete that line to retry.
- Whisper model size: `small` works fine on CPU. Use `medium` or `large-v3` with a GPU, or `STT=groq`.
- With a Claude subscription you need no API keys. `.env` is only for Groq (fast transcription) or API billing.
- Long events on CPU: transcription takes about as long as the recording. `STT=groq` takes minutes instead.
