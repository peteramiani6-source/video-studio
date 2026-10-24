#!/usr/bin/env bash
# End-to-end smoke test with real FFmpeg and no models: a generated 40 s video and a fake transcript
# go through prepare -> pick (PICKER=none) -> clip render -> event render (final + draft) -> montage.
# Checks output durations, sizes and audio/video sync. Usage: tests/smoke.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
job="ci-smoke"
rm -rf "work/$job" "out/$job"
mkdir -p "work/$job" logs
src="work/$job/source.mp4"

echo "== generate a 40 s test video"
ffmpeg -hide_banner -loglevel error -y -f lavfi -i testsrc2=size=1280x720:rate=30:duration=40 \
  -f lavfi -i sine=frequency=440:duration=40 -c:v libx264 -preset ultrafast -c:a aac -shortest "$src"

echo "== prepare"
scripts/prepare.sh "$src" "$job"

echo "== fake transcript: a word every 0.5 s, with a 3 s pause at 12-15 s"
python3 - "$job" <<'EOF'
import json, sys
sys.path.insert(0, "scripts")
from common import ROOT, write_srt
wd = ROOT / "work" / sys.argv[1]
words, t = [], 1.0
while t < 39:
    if 12 <= t < 15:
        t = 15.0
        continue
    words.append({"start": round(t, 2), "end": round(t + 0.4, 2), "word": f"w{len(words)}"})
    t += 0.5
segs = [{"start": c[0]["start"], "end": c[-1]["end"], "text": " ".join(w["word"] for w in c)}
        for c in (words[i:i + 8] for i in range(0, len(words), 8))]
write_srt(segs, wd / "transcript.srt")
(wd / "words.json").write_text(json.dumps(words))
EOF

echo "== pick (PICKER=none)"
PICKER=none python3 scripts/pick_clips.py "$job"

echo "== clip render (hook + pause cut)"
cat > "work/$job/clips.json" <<'EOF'
[{"start": 5, "end": 30, "title": "Smoke clip", "hook": "Testing the hook overlay",
  "caption": "c", "hashtags": ["#test"]}]
EOF
python3 scripts/render.py "$job"

echo "== event render (final, then draft)"
cat > "work/$job/plan.json" <<'EOF'
{"title": "CI Smoke", "subtitle": "Test | 2026",
 "segments": [{"start": 1, "end": 10, "label": "Part one", "speaker": "Test Speaker", "role": "Host"},
              {"start": 10, "end": 20, "label": "Part two", "speaker": "Test Speaker", "role": "Host"},
              {"start": 25, "end": 38, "label": "Closing", "speaker": "", "role": ""}],
 "highlights": [{"start": 3, "end": 8}, {"start": 26, "end": 31}],
 "social_clips": [], "youtube": {"title": "CI", "description": "d"}}
EOF
python3 scripts/render_event.py "$job"
python3 scripts/render_event.py "$job" --draft --skip-highlights

echo "== montage (shot analysis, PICKER=none plan, render)"
python3 scripts/shots.py "$job" --force
PICKER=none python3 scripts/plan_shots.py "$job" --hook "Behind the scenes"
python3 scripts/render_shots.py "$job"

echo "== check outputs"
python3 - "$job" <<'EOF'
import sys
sys.path.insert(0, "scripts")
from common import ROOT, probe
od = ROOT / "out" / sys.argv[1]
fails = []

def check(name, want_len, size, tol=0.5):
    p = od / name
    if not p.exists():
        fails.append(f"{name}: missing")
        return
    info = probe(p)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    d = float(info["format"]["duration"])
    msg = f"{name}: {d:.2f}s {v['width']}x{v['height']}"
    if abs(d - want_len) > tol:
        fails.append(f"{msg}, expected ~{want_len}s")
    if (v["width"], v["height"]) != size:
        fails.append(f"{msg}, expected {size[0]}x{size[1]}")
    if a is None:
        fails.append(f"{name}: no audio stream")
    elif abs(float(v["duration"]) - float(a["duration"])) > 0.15:
        fails.append(f"{name}: audio/video out of sync ({v['duration']} vs {a['duration']})")
    print("ok  " if not fails or not fails[-1].startswith(name) else "BAD ", msg)

# 25 s window minus the pause (12.1-14.8 kept as margins) = 22.3 s
check("clip_01_smoke-clip.mp4", 22.3, (1080, 1920), tol=0.3)
# title 4 + 9 + 10 + 13 + end card 3
check("event_full.mp4", 39, (1920, 1080))
check("event_full_draft.mp4", 39, (960, 540))
check("event_highlights.mp4", 13, (1920, 1080))
import json
edit = json.loads((ROOT / "work" / sys.argv[1] / "edit.json").read_text())
check("montage.mp4", sum(p["out"] - p["in"] for p in edit["edit"]), (1080, 1920), tol=0.1)
for f in ("captions.md", "event_full.srt", "youtube.md", "montage.md"):
    if not (od / f).exists():
        fails.append(f"{f}: missing")
if fails:
    sys.exit("FAILED:\n  " + "\n  ".join(fails))
print("smoke test passed")
EOF
