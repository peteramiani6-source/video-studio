"""Preflight: check that the tools and models chosen in config/models.env are actually usable.

Usage: python3 scripts/doctor.py [--quiet]
Run by setup.sh, run.sh and event.sh before any work starts, so a missing login, key or
library fails in seconds with a clear fix instead of halfway through a long job.
--quiet prints only problems. Exit code 1 if anything required is missing.
"""
import importlib.util
import json
import shutil
import subprocess
import sys

from common import ROOT, env

problems, warnings, oks = [], [], []


def has_module(name):
    try:
        return importlib.util.find_spec(name) is not None
    except ModuleNotFoundError:  # parent package missing, e.g. "google" for google.genai
        return False


def need(ok, label, fix):
    (oks if ok else problems).append(label if ok else f"{label}: {fix}")


def want(ok, label, fix):
    (oks if ok else warnings).append(label if ok else f"{label}: {fix}")


def main():
    quiet = "--quiet" in sys.argv

    # FFmpeg and the filters the renders rely on
    ff = shutil.which("ffmpeg")
    need(ff and shutil.which("ffprobe"), "ffmpeg + ffprobe", "install with `sudo apt install ffmpeg`")
    if ff:
        filters = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
        need(" subtitles " in filters, "ffmpeg libass (captions)", "this ffmpeg build lacks libass; install the distro ffmpeg")
        need(" drawtext " in filters, "ffmpeg drawtext (hooks, titles, lower-thirds)",
             "this ffmpeg build lacks libfreetype; install the distro ffmpeg")
    want(shutil.which("fc-match"), "fontconfig", "`sudo apt install fontconfig fonts-dejavu-core` for reliable fonts")

    # Config files parse
    for f in ("config/brand.json",):
        try:
            json.loads((ROOT / f).read_text())
            oks.append(f)
        except (OSError, ValueError) as e:
            problems.append(f"{f}: not valid JSON ({e})")
    try:
        lo, hi = float(env("CLIP_MIN", 25)), float(env("CLIP_MAX", 60))
        need(0 < lo < hi, "clip lengths", f"CLIP_MIN ({lo}) must be below CLIP_MAX ({hi})")
    except ValueError:
        problems.append("clip lengths: CLIP_MIN / CLIP_MAX must be numbers")

    # Transcription
    stt = env("STT", "local")
    if stt == "local":
        need(has_module("faster_whisper"), "STT=local (faster-whisper)",
             "run ./setup.sh (or .venv/bin/pip install faster-whisper)")
    elif stt == "groq":
        need(bool(env("GROQ_API_KEY")), "STT=groq key", "add GROQ_API_KEY to .env")
        need(has_module("requests"), "STT=groq (requests)", "run ./setup.sh")
    else:
        problems.append(f"STT={stt}: use local or groq")

    # Editing decisions
    picker = env("PICKER", "claude-code")
    if picker == "claude-code":
        need(shutil.which("claude"), "PICKER=claude-code (Claude Code CLI)",
             "install Claude Code, then run `claude` once to log in")
    elif picker == "claude":
        need(bool(env("ANTHROPIC_API_KEY")), "PICKER=claude key", "add ANTHROPIC_API_KEY to .env (API billing)")
        need(has_module("anthropic"), "PICKER=claude (anthropic)", "run ./setup.sh")
    elif picker == "gemini":
        need(bool(env("GEMINI_API_KEY") or env("GOOGLE_API_KEY")), "PICKER=gemini key", "add GEMINI_API_KEY to .env")
        need(has_module("google.genai"), "PICKER=gemini (google-genai)", "run ./setup.sh")
    elif picker == "none":
        warnings.append("PICKER=none: no model, clips are evenly spaced and events are kept whole")
    else:
        problems.append(f"PICKER={picker}: use claude-code, claude, gemini or none")

    if not quiet:
        for o in oks:
            print(f"  ok    {o}")
    for w in warnings:
        print(f"  warn  {w}", file=sys.stderr)
    for p in problems:
        print(f"  FAIL  {p}", file=sys.stderr)
    if problems:
        sys.exit(f"doctor: {len(problems)} problem(s), fix them and try again")


if __name__ == "__main__":
    main()
