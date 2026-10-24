#!/usr/bin/env bash
# Watch inbox/ and process each new video, one at a time.
#   MODE=auto    (default) runs scripts/run.sh straight; Claude Code is called only if a step fails,
#                to fix the cause and resume the job. Successful runs spend no tokens.
#   MODE=claude  Claude Code runs the video-edit skill headless for every file
#   MODE=direct  runs scripts/run.sh straight, never calls Claude Code
# Uses inotifywait (Linux), fswatch (macOS), or polling as a fallback.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
MODE="${MODE:-auto}"
mkdir -p inbox logs
touch logs/failed.txt

log() { echo "$(date '+%F %T') [watch] $*" | tee -a logs/pipeline.log; }

is_video() { case "$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')" in *.mp4|*.mov|*.mkv|*.m4v|*.webm) return 0;; *) return 1;; esac; }

wait_stable() {  # wait until the file stops growing (copy/upload finished)
  local f="$1" a b
  while :; do
    a=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f"); sleep 3
    b=$(stat -c %s "$f" 2>/dev/null || stat -f %z "$f")
    [ "$a" = "$b" ] && return 0
  done
}

process() {
  local name="$1" f="inbox/$1"
  [ -f "$f" ] && is_video "$name" || return 0
  grep -qxF "$name" logs/failed.txt && return 0   # skip known failures; delete the line to retry
  wait_stable "$f"
  log "processing $name (MODE=$MODE)"
  if [ "$MODE" = "claude" ]; then
    claude -p "A new recording is at inbox/$name. Use the video-edit skill to process it with scripts/run.sh. If a step fails, read logs/pipeline.log, fix the cause and re-run only that step. Finish by listing the files in the output folder." \
      --allowedTools "Bash,Read,Edit,Write,Glob,Grep" >>logs/pipeline.log 2>&1 \
      || { log "claude run failed for $name"; echo "$name" >> logs/failed.txt; }
  elif [ "$MODE" = "auto" ]; then
    local jf job
    jf="$(mktemp)"
    if JOB_FILE="$jf" scripts/run.sh "$f"; then rm -f "$jf"; return 0; fi
    job="$(cat "$jf" 2>/dev/null)"; rm -f "$jf"
    if [ -z "$job" ] || ! command -v claude >/dev/null 2>&1; then
      log "run.sh failed for $name (no Claude Code fallback)"; return 0
    fi
    log "run.sh failed for $name, asking Claude Code to fix job $job"
    claude -p "scripts/run.sh failed on inbox/$name (job $job). Use the video-edit skill. Read logs/pipeline.log to find the failed step, fix the cause, then resume with: scripts/run.sh inbox/$name $job . Finish by listing the files in out/$job." \
      --allowedTools "Bash,Read,Edit,Write,Glob,Grep" >>logs/pipeline.log 2>&1 \
      || log "claude fix failed for $name"
  else
    scripts/run.sh "$f" || log "run.sh failed for $name"
  fi
}

log "watching inbox/ (MODE=$MODE)"
for f in inbox/*; do [ -f "$f" ] && process "$(basename "$f")"; done   # backlog first

# inotify never fires for files written from the Windows side of WSL (/mnt/c/...), so poll there.
case "$ROOT" in /mnt/*) POLL=1 ;; esac

if [ "${POLL:-0}" = "1" ]; then
  log "polling inbox/ every 15s"
  while sleep 15; do for f in inbox/*; do [ -f "$f" ] && process "$(basename "$f")"; done; done
elif command -v inotifywait >/dev/null 2>&1; then
  inotifywait -m -q -e close_write -e moved_to --format '%f' inbox | while read -r name; do process "$name"; done
elif command -v fswatch >/dev/null 2>&1; then
  fswatch -0 --event Created --event MovedTo inbox | while read -r -d '' path; do process "$(basename "$path")"; done
else
  log "inotifywait/fswatch not found, polling every 15s"
  while sleep 15; do for f in inbox/*; do [ -f "$f" ] && process "$(basename "$f")"; done; done
fi
