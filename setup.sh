#!/usr/bin/env bash
# One-time setup: folders, Python venv, dependency checks.
set -euo pipefail
cd "$(dirname "$0")"

mkdir -p inbox work out archive logs assets
touch inbox/.gitkeep
chmod +x scripts/*.sh setup.sh
[ -f .env ] || cp .env.example .env

ok()   { printf '  \033[32mok\033[0m   %s\n' "$1"; }
miss() { printf '  \033[33mmiss\033[0m %s\n' "$1"; }

echo "Checking tools:"
command -v ffmpeg >/dev/null && ok ffmpeg || miss "ffmpeg (apt install ffmpeg / brew install ffmpeg)"
ffmpeg -hide_banner -filters 2>/dev/null | grep -q " subtitles " && ok "ffmpeg libass (captions)" \
  || miss "ffmpeg built without libass, captions will fail"
command -v claude >/dev/null && ok "claude (Claude Code)" || miss "claude: npm install -g @anthropic-ai/claude-code"
if command -v inotifywait >/dev/null || command -v fswatch >/dev/null; then ok "file watcher"
else miss "inotify-tools (Linux) or fswatch (macOS), the watcher will fall back to polling"; fi

echo "Creating Python venv:"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
ok "python deps installed in .venv"

echo "Animation (Remotion, for scripture mode):"
if command -v npm >/dev/null; then
  (cd remotion && npm ci --no-audit --no-fund --loglevel=error) && ok "remotion/node_modules installed"
else
  miss "Node.js/npm: needed only for scripture mode (sudo apt install nodejs npm)"
fi

echo "Voice (Kokoro, for scripture voiceovers):"
mkdir -p models/kokoro
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  if [ ! -s "models/kokoro/$f" ]; then
    curl -fsSL -o "models/kokoro/$f.part" \
      "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f" \
      && mv "models/kokoro/$f.part" "models/kokoro/$f" || { rm -f "models/kokoro/$f.part"; miss "download of $f failed; re-run setup.sh"; }
  fi
done
[ -s models/kokoro/voices-v1.0.bin ] && [ -s models/kokoro/kokoro-v1.0.int8.onnx ] && ok "Kokoro voice model in models/kokoro/"

echo "Checking the configured models (config/models.env):"
.venv/bin/python scripts/doctor.py || echo "  fix the FAIL lines above, then run: .venv/bin/python scripts/doctor.py"

cat <<'EOF'

Next:
  1. Run `claude` once and log in with your Claude subscription (no API key needed)
  2. Edit an event:      scripts/event.sh "inbox/<folder-or-file>" "Title" "Date | Venue"
     Clips from a talk:  scripts/run.sh inbox/<your-video>.mp4
     Resume a failed event: scripts/event.sh --resume <job-id>
     Montage:            scripts/montage.sh "inbox/<folder>" "what it is"
     Scripture episode:  scripts/scripture.sh new "Proverbs 3:5-6"
  3. Run in background:  scripts/watch.sh            (or MODE=direct scripts/watch.sh)
  4. Always-on (Linux):  see deploy/video-studio.service

Optional community skills (read each SKILL.md before installing):
  npx skills add https://github.com/affaan-m/everything-claude-code --skill video-editing
  npx skills add remotion
EOF
