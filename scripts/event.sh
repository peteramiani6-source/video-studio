#!/usr/bin/env bash
# Full event edit: merge -> transcribe -> plan -> render full video + highlights (+ vertical clips)
#
# Usage:
#   scripts/event.sh <video-or-folder> ["Event title"] ["Subtitle, e.g. date and venue"]
#
# Put an optional event.json in the folder (or next to the file with the same name) for speakers,
# notes, must_keep ranges and target length. See event.example.json.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python
set -a; source config/models.env; set +a

src="${1:?usage: scripts/event.sh <video-or-folder> [title] [subtitle]}"
title="${2:-}"; subtitle="${3:-}"
[ -e "$src" ] || { echo "not found: $src" >&2; exit 1; }

name="$(basename "${src%/}")"; name="${name%.*}"
slug="$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9' '-' | sed 's/^-//;s/-$//')"
job="event-${slug}-$(date +%Y%m%d-%H%M%S)"
mkdir -p "work/$job" "out/$job" logs archive

log() { echo "$(date '+%F %T') [$job] $*" | tee -a logs/pipeline.log; }
step="start"
trap 'log "FAILED at step: $step. Fix the cause, then re-run that step with job id $job"' ERR

log "event start: $src"
step="merge";       $PY scripts/merge.py "$src" "$job"
step="transcribe";  $PY scripts/transcribe.py "$job"
step="plan";        $PY scripts/plan_event.py "$job" --title "$title" --subtitle "$subtitle"
step="render";      $PY scripts/render_event.py "$job"
if [ "${EVENT_SOCIAL_CLIPS:-1}" = "1" ] && [ "$(cat "work/$job/clips.json")" != "[]" ]; then
  step="social";    $PY scripts/render.py "$job"
fi

case "$(cd "$(dirname "${src%/}")" && pwd)" in
  "$ROOT/inbox") mv "${src%/}" "archive/" ;;
esac
log "event done: out/$job"
echo "out/$job"
