#!/usr/bin/env bash
# Full event edit: merge -> transcribe -> plan -> render full video + highlights (+ vertical clips)
#
# Usage:
#   scripts/event.sh <video-or-folder> ["Event title"] ["Subtitle, e.g. date and venue"]
#   scripts/event.sh --resume <job-id>      # continue a failed job: finished steps are skipped
#
# Put an optional event.json in the folder (or next to the file with the same name) for speakers,
# notes, must_keep ranges and target length. See config/event.example.json.
# To re-plan a job from scratch, delete work/<job>/plan.json and resume.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
set -a; source config/models.env; set +a

usage() { echo "usage: scripts/event.sh <video-or-folder> [title] [subtitle]  |  scripts/event.sh --resume <job-id>" >&2; exit 1; }
[ $# -ge 1 ] || usage

if [ "$1" = "--resume" ]; then
  job="${2:-}"; [ -n "$job" ] || usage
  meta="work/$job/meta.json"
  [ -f "$meta" ] || { echo "no $meta: not an event job, or started before resume support" >&2; exit 1; }
  read_meta() { $PY -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$meta" "$1"; }
  src="$(read_meta src)"; title="$(read_meta title)"; subtitle="$(read_meta subtitle)"
  resume=1
else
  src="$1"; title="${2:-}"; subtitle="${3:-}"
  [ -e "$src" ] || { echo "not found: $src" >&2; exit 1; }
  name="$(basename "${src%/}")"; name="${name%.*}"
  slug="$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')"
  job="event-${slug}-$(date +%Y%m%d-%H%M%S)"
  resume=0
fi

$PY scripts/doctor.py --quiet || exit 1
# shellcheck source=scripts/lock.sh
source scripts/lock.sh; studio_lock

mkdir -p "work/$job" "out/$job" logs archive
if [ "$resume" = 0 ]; then
  $PY -c 'import json,sys; json.dump(dict(src=sys.argv[1], title=sys.argv[2], subtitle=sys.argv[3]), open(sys.argv[4], "w"), indent=2)' \
    "$src" "$title" "$subtitle" "work/$job/meta.json"
fi

log() { echo "$(date '+%F %T') [$job] $*" | tee -a logs/pipeline.log; }
step="start"
trap 'log "FAILED at step: $step. Fix the cause, then: scripts/event.sh --resume $job"' ERR

if [ "$resume" = 1 ]; then log "event resume: $src"; else log "event start: $src"; fi
step="merge"
if [ -f "work/$job/tight.mp4" ]; then log "merge: tight.mp4 exists, skipping"
else
  [ -e "$src" ] || { log "source $src is gone (archived?) and tight.mp4 is missing"; exit 1; }
  $PY scripts/merge.py "$src" "$job"
fi
step="transcribe";  $PY scripts/transcribe.py "$job"   # skips itself when transcript.srt exists
step="plan"
if [ "$resume" = 1 ] && [ -f "work/$job/plan.json" ]; then log "plan: plan.json exists, skipping"
else $PY scripts/plan_event.py "$job" --title "$title" --subtitle "$subtitle"; fi
step="render";      $PY scripts/render_event.py "$job"
if [ "${EVENT_SOCIAL_CLIPS:-1}" = "1" ] && [ "$(cat "work/$job/clips.json")" != "[]" ]; then
  step="social";    $PY scripts/render.py "$job"
fi

if [ -e "${src%/}" ]; then
  case "$(cd "$(dirname "${src%/}")" && pwd)" in
    "$ROOT/inbox") mv "${src%/}" "archive/" ;;
  esac
fi
log "event done: out/$job"
echo "out/$job"
