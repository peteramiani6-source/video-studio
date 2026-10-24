#!/usr/bin/env bash
# Scripture mode: animated verse videos ("One Verse, Real Life").
#
#   scripts/scripture.sh new "Proverbs 3:5-6" [--theme "decisions after school"]   draft an episode
#   scripts/scripture.sh show ep001                                                  read it as a script
#   scripts/scripture.sh check                                                       validate all episodes
#   scripts/scripture.sh render ep001 [--draft] [--format vertical|wide|both]        render one
#   scripts/scripture.sh render --all [--draft]                                      render every reviewed episode
#   scripts/scripture.sh voice ep001 [--script]                                      AI voiceover (or lines to record)
#
# Runs scripts/scripture.py with the project's Python, after the right preflight check.
# Renders take the shared job lock, so they wait for any clip/event/montage job to finish.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PATH="$ROOT/.venv/bin:$PATH"
PY=python3; [ -x .venv/bin/python ] && PY=.venv/bin/python

[ $# -ge 1 ] || { sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'; exit 1; }
case "$1" in
  render)
    $PY scripts/doctor.py --quiet --mode scripture || exit 1
    # shellcheck source=scripts/lock.sh
    source scripts/lock.sh; studio_lock ;;
  new)
    $PY scripts/doctor.py --quiet --mode scripture-write || exit 1 ;;
  voice)
    shift
    case " $* " in
      *" --script "*) ;;   # just prints the lines to record
      *) $PY scripts/doctor.py --quiet --mode scripture-voice || exit 1
         # shellcheck source=scripts/lock.sh
         source scripts/lock.sh; studio_lock ;;
    esac
    exec $PY scripts/voice.py "$@" ;;
esac
exec $PY scripts/scripture.py "$@"
