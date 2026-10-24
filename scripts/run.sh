#!/usr/bin/env bash
# Full pipeline for one file: prepare -> transcribe -> pick clips -> render (pauses cut per clip).
# Usage: scripts/run.sh inbox/episode.mp4 [job-id]
#   job-id resumes a failed job: steps whose output already exists are skipped.
#   JOB_FILE=<path> makes the script write the job id there (used by watch.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python

src="${1:?usage: scripts/run.sh <video> [job-id]}"
[ -f "$src" ] || { echo "not found: $src" >&2; exit 1; }
$PY scripts/doctor.py --quiet || exit 1   # before the job exists, so a config problem never marks the file failed
# shellcheck source=scripts/lock.sh
source scripts/lock.sh; studio_lock

base="$(basename "$src")"
if [ -n "${2:-}" ]; then
  job="$2"
  [ -d "work/$job" ] || { echo "job not found: work/$job" >&2; exit 1; }
else
  slug="$(echo "${base%.*}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')"
  job="${slug}-$(date +%Y%m%d-%H%M%S)"
fi
mkdir -p "work/$job" "out/$job" logs archive
[ -n "${JOB_FILE:-}" ] && echo "$job" > "$JOB_FILE"

log() { echo "$(date '+%F %T') [$job] $*" | tee -a logs/pipeline.log; }
step="start"
trap 'log "FAILED at step: $step (see messages above)"; echo "$base" >> logs/failed.txt' ERR

log "${2:+resume }start: $src"
step="prepare"
if [ -f "work/$job/tight.mp4" ]; then log "prepare: tight.mp4 exists, skipping"
else scripts/prepare.sh "$src" "$job" >>logs/pipeline.log 2>&1; fi
step="transcribe";   $PY scripts/transcribe.py "$job"
step="pick_clips"
if [ -n "${2:-}" ] && [ -f "work/$job/clips.json" ]; then log "pick: clips.json exists, skipping"
else $PY scripts/pick_clips.py "$job"; fi
step="render";       $PY scripts/render.py "$job"

# Archive the source only after success, and only if it came from inbox/
case "$(cd "$(dirname "$src")" && pwd)" in
  "$ROOT/inbox") mv "$src" "archive/$base" ;;
esac
# A resumed job that now succeeds is no longer a known failure
if [ -f logs/failed.txt ]; then grep -vxF "$base" logs/failed.txt > logs/failed.tmp || true; mv logs/failed.tmp logs/failed.txt; fi
log "done: out/$job"
echo "out/$job"
