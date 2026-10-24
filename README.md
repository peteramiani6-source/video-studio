# video-studio

Video editing driven from the terminal by Claude Code. A model makes the judgment calls (which moments, which shots, what words). FFmpeg and Remotion do all the cutting and rendering, so results are repeatable and free to re-render.

| Mode | For | Command | Result |
|---|---|---|---|
| **Event** | a long recording: fireside, conference, service | `scripts/event.sh` | full edit, highlight reel, subtitles, YouTube chapters, social clips |
| **Montage** | short edits judged on the picture: behind the scenes, promos, recaps | `scripts/montage.sh` | a shot-based cut, in story order, with the crop following the people |
| **Clip** | a talk or podcast | `scripts/run.sh` | captioned 9:16 clips plus post captions |
| **Scripture** | animated verse videos ("One Verse, Real Life") | `scripts/scripture.sh` | verse + reflection + "live it" points, vertical and/or wide |

## Quick start

```bash
./setup.sh                 # Python venv, Remotion (npm ci), tool checks
claude                     # log in once with your Claude subscription, then /exit
```

On Windows, everything runs in WSL2. See [docs/WINDOWS.md](docs/WINDOWS.md).

### Edit a whole event
```bash
cp config/event.example.json "inbox/Fireside Night/event.json"   # optional: speakers, notes, must_keep
scripts/event.sh "inbox/Fireside Night" "YSA Fireside Evening" "Langata Ward | 14 Nov 2026"
```
Results go to `out/event-…/`: `event_full.mp4`, `event_highlights.mp4`, `event_full.srt`, `youtube.md`, plus vertical clips and `captions.md`. To change the edit, ask Claude Code ("drop the announcements", "make it under 20 minutes"). It edits `work/<job>/plan.json` and re-renders without re-transcribing.

### Make a behind-the-scenes or promo montage
```bash
scripts/montage.sh "inbox/Garden BTS" "behind the scenes of our garden interview"
```
Claude looks at a keyframe of every shot, skips blurry and shaky ones, and orders the shots: wide → close-ups → a human ending. The result is `montage.mp4` plus `montage.md` (the cut list, with a reason for each shot).

### Clips from a talk or podcast
```bash
scripts/run.sh inbox/episode1.mp4
scripts/watch.sh           # or leave this running: every video dropped in inbox/ becomes clips
```

### Scripture episodes
```bash
scripts/scripture.sh new "Proverbs 3:5-6" --theme "decisions after school"   # Claude drafts the words
scripts/scripture.sh show ep004                                               # read it as a script
# review it, fix anything, set "reviewed": true in scripture/episodes/ep004.json
scripts/scripture.sh render ep004                                             # -> out/scripture/ep004/
scripts/scripture.sh render --all                                             # every reviewed episode
```
The verse is always the exact KJV text from the bundled Bible. Claude only writes the words around it, and nothing renders until a person has reviewed it. See [scripture/README.md](scripture/README.md).

## Folder guide

Each folder has its own README with the details.

| Folder | What's in it |
|---|---|
| [`scripts/`](scripts/README.md) | the pipeline: one entry script per mode, plus the steps they run |
| [`config/`](config/README.md) | `models.env` (which AI does what), `brand.json` (look, captions, hook, scripture brand), event template |
| [`remotion/`](remotion/README.md) | animation templates in React (the scripture episode), fonts |
| [`scripture/`](scripture/README.md) | episodes, the bundled KJV, your voiceovers and music |
| [`assets/`](assets/README.md) | logo and intro music for event videos |
| [`docs/`](docs/README.md) | Windows/WSL setup, shooting checklist |
| [`tests/`](tests/README.md) | unit tests and the end-to-end render test CI runs |
| [`deploy/`](deploy/README.md) | systemd service that keeps the inbox watcher running |
| [`inbox/`](inbox/README.md) | drop recordings here |
| `work/`, `out/`, `archive/`, `logs/` | created on the first run (not in git): job scratch, results, processed sources, logs |
| `.claude/skills/video-edit/` | the skill Claude Code follows in this folder |

## Which AI does what

| Step | Default | Switch in `config/models.env` |
|---|---|---|
| Orchestration | the scripts; Claude Code fixes failures | `MODE=claude` / `MODE=direct` in the watcher |
| Transcription | faster-whisper on your CPU | `STT=groq` (much faster for long recordings) |
| Edit decisions, clip and shot choice, writing | your Claude subscription through Claude Code | `PICKER=claude` (API), `gemini`, `none` |
| Cutting, cropping, captions, rendering | FFmpeg | none |
| Animation | Remotion (React, rendered in headless Chrome) | none |

With a Claude subscription you need no API keys. `.env` is only for Groq (fast transcription) or API billing.

## Ask Claude Code

Run `claude` in this folder, then ask things like:
- "Process inbox/episode2.mp4"
- "Clip 3 of the last job starts too early, start it at the question instead"
- "Open the montage on the wide shot and use less of the tripod"
- "Draft three episodes on patience, then show me the scripts"
- "Make the scripture accent colour green and re-render ep002"

## Good to know

- **Before you shoot:** read [docs/SHOOTING.md](docs/SHOOTING.md). Focus, glare and a cluttered frame can't be fixed in the edit.
- **Health check:** `python3 scripts/doctor.py` checks ffmpeg, Whisper and your model login or key. Every mode runs it first.
- **Resume:** a failed job can be resumed: `scripts/event.sh --resume <job>`, `scripts/montage.sh --resume <job>`, `scripts/run.sh <file> <job>`. Finished steps are skipped.
- **One job at a time:** a second job waits for the first instead of slowing both down.
- **Tests:** `python3 -m unittest discover -s tests` (fast) and `tests/smoke.sh` (full renders). CI runs both on every pull request.
- **Long recordings on CPU:** transcription takes about as long as the recording. `STT=groq` takes minutes instead.
