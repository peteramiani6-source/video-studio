#!/usr/bin/env bash
# Montage mode: short shot-based edits (behind the scenes, promos, recaps) where the picture matters.
# merge -> transcribe (speech optional) -> shots (scene cuts, sharpness, motion, contact sheets)
#   -> plan_shots (the model looks at the sheets and orders the shots) -> render_shots
#
# Usage:
#   scripts/montage.sh <video-or-folder> ["what it is, e.g. behind the scenes of our garden interview"]
#   scripts/montage.sh --resume <job-id>     # continue a failed job: finished steps are skipped
#
# A folder of angles/takes is fine: every take becomes its own shots. To re-plan, delete
# work/<job>/edit.json and resume. Settings: "montage" (length, shot limits, format) and "look" in brand.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
set -a; source config/models.env; set +a

usage() { echo "usage: scripts/montage.sh <video-or-folder> [brief]  |  scripts/montage.sh --resume <job-id>" >&2; exit 1; }
[ $# -ge 1 ] || usage

if [ "$1" = "--resume" ]; then
  job="${2:-}"; [ -n "$job" ] || usage
  meta="work/$job/meta.json"
  [ -f "$meta" ] || { echo "no $meta: not a montage job" >&2; exit 1; }
  read_meta() { $PY -c 'import json,sys; print(json.load(open(sys.argv[1]))[sys.argv[2]])' "$meta" "$1"; }
  src="$(read_meta src)"; brief="$(read_meta brief)"
  resume=1
else
  src="$1"; brief="${2:-}"
  [ -e "$src" ] || { echo "not found: $src" >&2; exit 1; }
  name="$(basename "${src%/}")"; name="${name%.*}"
  slug="$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')"
  job="montage-${slug}-$(date +%Y%m%d-%H%M%S)"
  resume=0
fi

$PY scripts/doctor.py --quiet || exit 1
# shellcheck source=scripts/lock.sh
source scripts/lock.sh; studio_lock

mkdir -p "work/$job" "out/$job" logs archive
if [ "$resume" = 0 ]; then
  $PY -c 'import json,sys; json.dump(dict(src=sys.argv[1], brief=sys.argv[2]), open(sys.argv[3], "w"), indent=2)' \
    "$src" "$brief" "work/$job/meta.json"
fi

log() { echo "$(date '+%F %T') [$job] $*" | tee -a logs/pipeline.log; }
step="start"
trap 'log "FAILED at step: $step. Fix the cause, then: scripts/montage.sh --resume $job"' ERR

if [ "$resume" = 1 ]; then log "montage resume: $src"; else log "montage start: $src"; fi
step="merge"
if [ -f "work/$job/tight.mp4" ]; then log "merge: tight.mp4 exists, skipping"
else
  [ -e "$src" ] || { log "source $src is gone (archived?) and tight.mp4 is missing"; exit 1; }
  $PY scripts/merge.py "$src" "$job"
fi
step="transcribe";  $PY scripts/transcribe.py "$job" --allow-empty   # captions are optional here
step="shots";       $PY scripts/shots.py "$job"                      # skips itself when shots.json exists
step="plan"
if [ "$resume" = 1 ] && [ -f "work/$job/edit.json" ]; then log "plan_shots: edit.json exists, skipping"
else $PY scripts/plan_shots.py "$job" --brief "$brief"; fi
step="render";      $PY scripts/render_shots.py "$job"

if [ -e "${src%/}" ]; then
  case "$(cd "$(dirname "${src%/}")" && pwd)" in
    "$ROOT/inbox") mv "${src%/}" "archive/" ;;
  esac
fi
log "montage done: out/$job"
echo "out/$job"
