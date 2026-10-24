#!/usr/bin/env bash
# Step 1: working copy of the source -> work/<job>/tight.mp4
# Streams are copied, not re-encoded, so this takes seconds even for long recordings.
# Pauses are cut later, inside each clip only (render.py, SILENCE_CUT in config/models.env).
# Usage: scripts/prepare.sh <source-video> <job-id>
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

src="$1"; job="$2"
out="work/$job/tight.mp4"
part="work/$job/tight.part.mp4"   # renamed only when complete, so a crash never leaves a half file
mkdir -p "work/$job"

# Re-encode only if the streams can't go into mp4 as they are.
ffmpeg -hide_banner -loglevel error -y -i "$src" -map 0:v:0 -map 0:a:0? -c copy -movflags +faststart "$part" \
  || ffmpeg -hide_banner -loglevel error -y -i "$src" -map 0:v:0 -map 0:a:0? \
       -c:v libx264 -crf 18 -preset veryfast -c:a aac -b:a 192k -movflags +faststart "$part"
mv -f "$part" "$out"
echo "$out"
