"""Montage step 3: split the footage into shots the editor can see -> work/<job>/shots.json + frames/

Usage: python3 scripts/shots.py <job-id> [--force]

One low-resolution FFmpeg pass measures, five times a second:
  - scene changes (cuts between takes or camera angles)
  - sharpness (FFmpeg blurdetect: higher = blurrier; skipped on FFmpeg builds without it)
  - motion (average difference between frames: camera shake, walking, fast movement)
Long continuous takes are split into chunks of at most montage.max_shot seconds, so a single
handheld walk-around still offers several pickable moments. Each shot gets a keyframe and the
keyframes are tiled into numbered contact sheets (frames/sheet_NN.jpg) for the model and for you.
"""
import json
import shutil
import subprocess
import sys

from common import brand, duration, job_dir, log, parse_srt
from look import has_filter

ANALYSIS_FPS = 5


def montage_cfg():
    return {"format": "vertical", "seconds": 30, "min_shot": 1.5, "max_shot": 8.0, "gear_max": 3.0,
            "scene_threshold": 0.3, **brand().get("montage", {})}


def parse_metadata(text, key):
    """Parse `metadata=print` output into [(pts_time, value)] for one key."""
    out, t = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("frame:"):
            t = None
            for part in line.split():
                if part.startswith("pts_time:"):
                    t = float(part.split(":", 1)[1])
        elif t is not None and line.startswith(key + "="):
            try:
                out.append((t, float(line.split("=", 1)[1])))
            except ValueError:
                pass
    return out


def cut_times(text):
    """Times where a new scene starts (any frame the scene `select` let through)."""
    times = []
    for line in text.splitlines():
        if line.startswith("frame:"):
            for part in line.split():
                if part.startswith("pts_time:"):
                    times.append(float(part.split(":", 1)[1]))
    return times


def split_shots(cuts, total, max_shot, min_len=0.5):
    """Scene cuts -> [(start, end)], dropping slivers shorter than min_len and chunking long takes
    into equal pieces no longer than max_shot. Each piece remembers its take number."""
    bounds = [0.0] + sorted(t for t in cuts if min_len <= t <= total - min_len) + [total]
    takes = []
    for a, b in zip(bounds, bounds[1:]):
        if b - a < min_len and takes:
            takes[-1] = (takes[-1][0], b)  # merge a sliver into the previous take
        elif b > a:
            takes.append((a, b))
    shots = []
    for take, (a, b) in enumerate(takes, 1):
        n = max(1, int(-(-(b - a) // max_shot)))  # ceil
        step = (b - a) / n
        shots += [{"take": take, "start": round(a + i * step, 3), "end": round(a + (i + 1) * step, 3)} for i in range(n)]
    return shots


def mean_in(samples, a, b):
    vals = [v for t, v in samples if a <= t < b]
    return round(sum(vals) / len(vals), 2) if vals else None


def analyse(src, wd, threshold):
    """One pass at low resolution; returns (cut times, blur samples, motion samples)."""
    blur = has_filter("blurdetect")
    branches = 3 if blur else 2
    graph = [f"[0:v]fps={ANALYSIS_FPS},scale=480:-2,format=gray,split={branches}[sc][mo]" + ("[bl]" if blur else ""),
             f"[sc]select='gt(scene,{threshold})',metadata=mode=print:file=scenes.txt,nullsink",
             "[mo]tblend=all_mode=difference,signalstats,"
             "metadata=mode=print:key=lavfi.signalstats.YAVG:file=motion.txt[out]"]
    if blur:
        graph.insert(2, "[bl]blurdetect,metadata=mode=print:key=lavfi.blur:file=blur.txt,nullsink")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(src),
                    "-filter_complex", ";".join(graph), "-map", "[out]", "-f", "null", "-"], cwd=wd, check=True)
    read = lambda f: (wd / f).read_text() if (wd / f).exists() else ""
    cuts = cut_times(read("scenes.txt"))
    blur_s = parse_metadata(read("blur.txt"), "lavfi.blur")
    motion_s = parse_metadata(read("motion.txt"), "lavfi.signalstats.YAVG")
    for f in ("scenes.txt", "blur.txt", "motion.txt"):
        (wd / f).unlink(missing_ok=True)
    return cuts, blur_s, motion_s


def keyframes_and_sheets(src, wd, shots, cols=4, rows=3):
    fd = wd / "frames"
    shutil.rmtree(fd, ignore_errors=True)
    fd.mkdir()
    for s in shots:
        mid = (s["start"] + s["end"]) / 2
        label = fd / f"label_{s['id']:03d}.txt"
        m, sec = divmod(int(s["start"]), 60)
        label.write_text(f"#{s['id']}  {m}:{sec:02d}  ({s['end'] - s['start']:.0f}s)")
        frame = f"shot_{s['id']:03d}.jpg"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{mid:.3f}", "-i", str(src),
                        "-frames:v", "1", "-vf", "scale=480:-2", "-q:v", "4", frame], cwd=fd, check=True)
        s["frame"] = f"frames/{frame}"
        # numbered copy for the contact sheet (number + time burned into the corner)
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", frame,
                        "-vf", f"scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2,"
                               f"drawtext=textfile={label.name}:expansion=none:fontsize=22:fontcolor=white:"
                               f"box=1:boxcolor=black@0.65:boxborderw=6:x=8:y=8",
                        "-q:v", "4", f"tile_{s['id']:03d}.jpg"], cwd=fd, check=True)
    per = cols * rows
    sheets = []
    for k in range(0, len(shots), per):
        name = f"sheet_{k // per + 1:02d}.jpg"
        # ids are 1..N in order, so each sheet is an image sequence starting at its first id;
        # tile flushes a part-filled last sheet at the end of the input
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-framerate", "1",
                        "-start_number", str(shots[k]["id"]), "-i", "tile_%03d.jpg",
                        "-frames:v", "1",
                        "-vf", f"select='lt(n,{per})',tile={cols}x{rows}:padding=6:margin=6:color=0x202020",
                        "-q:v", "3", name], cwd=fd, check=True)
        sheets.append(f"frames/{name}")
    for f in fd.glob("tile_*.jpg"):
        f.unlink()
    for f in fd.glob("label_*.txt"):
        f.unlink()
    return sheets


def main():
    job = sys.argv[1]
    wd = job_dir(job)
    if (wd / "shots.json").exists() and "--force" not in sys.argv:
        log(job, "shots: shots.json exists, skipping (use --force to redo)")
        return
    cfg = montage_cfg()
    src = wd / "tight.mp4"
    total = duration(src)
    cuts, blur_s, motion_s = analyse(src, wd, float(cfg["scene_threshold"]))
    shots = split_shots(cuts, total, float(cfg["max_shot"]))
    segs = parse_srt((wd / "transcript.srt").read_text()) if (wd / "transcript.srt").exists() else []
    for i, s in enumerate(shots, 1):
        s["id"] = i
        s["blur"] = mean_in(blur_s, s["start"], s["end"])
        s["motion"] = mean_in(motion_s, s["start"], s["end"])
        s["speech"] = " ".join(c["text"] for c in segs if c["end"] > s["start"] and c["start"] < s["end"])[:300]
    if len(shots) > 72:
        log(job, f"shots: WARNING {len(shots)} shots; montage mode is meant for short footage (a few minutes)")
    sheets = keyframes_and_sheets(src, wd, shots)
    (wd / "shots.json").write_text(json.dumps({"total": total, "sheets": sheets, "shots": shots}, indent=2))
    log(job, f"shots: {len(cuts)} cuts -> {len(shots)} shots, {len(sheets)} contact sheet(s)"
             + ("" if blur_s else " (no blurdetect in this ffmpeg: sharpness not measured)"))


if __name__ == "__main__":
    main()
