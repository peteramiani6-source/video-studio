"""Shared helpers: paths, env loading, logging, SRT I/O, ffprobe."""
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_env():
    """Load .env then config/models.env without overriding variables already set."""
    for f in (ROOT / ".env", ROOT / "config" / "models.env"):
        if not f.exists():
            continue
        for line in f.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = re.split(r"\s+#", val, maxsplit=1)[0].strip().strip('"').strip("'")
            if val:
                os.environ.setdefault(key.strip(), val)


load_env()


def env(key, default=None):
    return os.environ.get(key, default)


def job_dir(job):
    d = ROOT / "work" / job
    if not d.exists():
        sys.exit(f"job not found: {d}")
    return d


def out_dir(job):
    d = ROOT / "out" / job
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(job, msg):
    (ROOT / "logs").mkdir(exist_ok=True)
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} [{job}] {msg}"
    print(line, flush=True)
    with open(ROOT / "logs" / "pipeline.log", "a") as fh:
        fh.write(line + "\n")


def brand():
    return json.loads((ROOT / "config" / "brand.json").read_text())


def fontfile(name, bold=False):
    """Resolve a font name to a file path for ffmpeg drawtext ("" if fontconfig is missing)."""
    q = f"{name}:bold" if bold else name
    try:
        return subprocess.run(["fc-match", "-f", "%{file}", q], capture_output=True, text=True).stdout.strip()
    except FileNotFoundError:
        return ""


# ---------- time + SRT ----------

def fmt_ts(sec):
    sec = max(0.0, sec)
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_ts(ts):
    h, m, rest = ts.strip().replace(".", ",").split(":")
    s, ms = rest.split(",")
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000


def parse_srt(text):
    cues = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        for i, l in enumerate(lines):
            if "-->" in l:
                a, b = l.split("-->")
                cues.append({"start": parse_ts(a), "end": parse_ts(b),
                             "text": " ".join(lines[i + 1:]).strip()})
                break
    return cues


def write_srt(cues, path):
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{fmt_ts(c['start'])} --> {fmt_ts(c['end'])}\n{c['text']}\n")
    Path(path).write_text("\n".join(out))


# ---------- ffprobe ----------

def probe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json",
                        "-show_format", "-show_streams", str(path)],
                       capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


def duration(path):
    return float(probe(path)["format"]["duration"])


def has_audio(path):
    return any(s.get("codec_type") == "audio" for s in probe(path)["streams"])
