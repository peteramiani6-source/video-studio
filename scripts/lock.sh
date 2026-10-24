# shellcheck shell=bash
# Sourced by run.sh and event.sh: only one heavy job runs at a time.
# Protects the shared logs/failed.txt and keeps two transcriptions from fighting over a CPU-only machine.
# A second job waits (and says so) instead of failing. Released automatically when the script exits.
studio_lock() {
  mkdir -p logs
  if ! command -v flock >/dev/null 2>&1; then
    return 0  # macOS has no flock; jobs still get separate work/out folders
  fi
  exec 9>logs/.studio.lock
  if ! flock -n 9; then
    echo "another video job is running, this one will start when it finishes..." >&2
    flock 9
  fi
}
