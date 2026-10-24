"""Event step 1: gather the recording(s) -> work/<job>/tight.mp4

Usage: python3 scripts/merge.py <video-or-folder> <job-id>

- One file: remuxed as-is (a silent track is added if it has no audio).
- A folder: every video in it is joined in filename order (phones name files by time).
  Mixed phone/camera clips are normalised first: 1920x1080, 30 fps, 48 kHz stereo,
  with vertical clips letterboxed.
- An event.json in the folder (title, speakers, must_keep...) is copied into the job.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

from common import ROOT, brand, has_audio, log

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".m4v", ".webm", ".mts", ".avi"}


def run(cmd):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *cmd], check=True)


def main():
    src, job = Path(sys.argv[1]), sys.argv[2]
    wd = ROOT / "work" / job
    wd.mkdir(parents=True, exist_ok=True)
    out = wd / "tight.mp4"

    if src.is_dir():
        files = sorted(p for p in src.iterdir() if p.suffix.lower() in VIDEO_EXT)
        if (src / "event.json").exists():
            shutil.copy(src / "event.json", wd / "event.json")
    else:
        files = [src]
        side = src.with_suffix(".json")
        if side.exists():
            shutil.copy(side, wd / "event.json")
    if not files:
        sys.exit(f"merge: no video files in {src}")

    if len(files) == 1:
        f = files[0]
        if has_audio(f):
            run(["-i", str(f), "-c", "copy", "-movflags", "+faststart", str(out)])
        else:
            run(["-i", str(f), "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
                 "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-shortest", str(out)])
        log(job, f"merge: single file {f.name}")
        return

    ev = brand().get("event", {})
    W, H, fps = ev.get("width", 1920), ev.get("height", 1080), ev.get("fps", 30)
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={fps},format=yuv420p")
    parts, sources, offset = [], [], 0.0
    norm = wd / "norm"
    norm.mkdir(exist_ok=True)
    for i, f in enumerate(files):
        p = norm / f"part_{i:03d}.mp4"
        audio_in = [] if has_audio(f) else ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        amap = ["-map", "0:v:0", "-map", "0:a:0"] if not audio_in else ["-map", "0:v:0", "-map", "1:a", "-shortest"]
        run(["-i", str(f), *audio_in, *amap, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast",
             "-crf", "18", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", "192k", str(p)])
        from common import duration
        d = duration(p)
        sources.append({"file": f.name, "start": round(offset, 2), "end": round(offset + d, 2)})
        offset += d
        parts.append(p)
        log(job, f"merge: normalised {f.name} ({d:.0f}s)")

    lst = wd / "concat.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts))
    run(["-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", "-movflags", "+faststart", str(out)])
    (wd / "sources.json").write_text(json.dumps(sources, indent=2))
    shutil.rmtree(norm)
    log(job, f"merge: joined {len(files)} files ({offset / 60:.1f} min)")


if __name__ == "__main__":
    main()
