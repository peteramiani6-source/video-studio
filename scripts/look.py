"""Picture and sound polish shared by the clip and event renders.

Settings live under "look" in config/brand.json:
  contrast, saturation, brightness, gamma   FFmpeg eq filter (1 / 1 / 0 / 1 = untouched)
  stabilize        "off" | "deshake" (one pass, quick) | "vidstab" (two passes, smoother, like a warp stabilizer)
  stabilize_zoom   vidstab only: % zoom that hides the moving edges (5 is close to a "5% warp")
  wind_filter      true cuts low rumble (wind, traffic, handling noise) below wind_cutoff_hz
"""
import functools
import subprocess

from common import brand

DEFAULTS = {"contrast": 1.0, "saturation": 1.0, "brightness": 0.0, "gamma": 1.0,
            "stabilize": "off", "stabilize_zoom": 5, "wind_filter": False, "wind_cutoff_hz": 100}


def settings():
    return {**DEFAULTS, **brand().get("look", {})}


@functools.lru_cache(maxsize=None)
def has_filter(name):
    try:
        out = subprocess.run(["ffmpeg", "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return False
    return f" {name} " in out


def color_filters(c):
    vals = (float(c["contrast"]), float(c["saturation"]), float(c["brightness"]), float(c["gamma"]))
    if vals == (1.0, 1.0, 0.0, 1.0):
        return []
    return ["eq=contrast={:g}:saturation={:g}:brightness={:g}:gamma={:g}".format(*vals)]


def audio_filters(c):
    return [f"highpass=f={int(c['wind_cutoff_hz'])}"] if c.get("wind_filter") else []


def stabilize_mode(c):
    mode = str(c.get("stabilize") or "off").lower()
    if mode == "vidstab" and not has_filter("vidstabdetect"):
        return "deshake"  # this FFmpeg was built without libvidstab
    return mode if mode in ("deshake", "vidstab") else "off"


def stabilize_filters(c, src, start, dur, fps, workdir, name):
    """Video filters that steady handheld footage. Put them right after fps={fps} on input that was
    opened with the same -ss start -t dur, so both vidstab passes see exactly the same frames.
    vidstab's first pass runs here and leaves <name>.trf in workdir (the render's cwd)."""
    mode = stabilize_mode(c)
    if mode == "off":
        return []
    if mode == "deshake":
        return ["deshake"]
    trf = f"{name}.trf"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                    "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src),
                    "-vf", f"fps={fps},vidstabdetect=shakiness=5:accuracy=15:result={trf}",
                    "-an", "-f", "null", "-"], cwd=workdir, check=True)
    zoom = float(c.get("stabilize_zoom", 5))
    return [f"vidstabtransform=input={trf}:smoothing=15:zoom={zoom:g}:interpol=bicubic",
            "unsharp=5:5:0.6:3:3:0.3"]  # stabilizing softens slightly; this restores some edge detail
