"""Montage step 5: render edit.json -> out/<job>/montage.mp4 + montage.md

Usage: python3 scripts/render_shots.py <job-id> [--draft]

Each piece is cut from the source, steadied and colour-graded (look in brand.json), cropped around its
focus_x for vertical output (or scaled for wide), captioned from the word timestamps, and given short
audio fades so the cuts don't click. The hook shows over the first piece. Pieces are joined in the
order of edit.json, then the loudness is normalised once over the whole montage.
Video and audio are joined separately (H.264 copied, audio as exact-length PCM) and muxed once, so
AAC padding at each cut can't add up and pull the sound out of sync on longer montages.
--draft renders at half resolution into montage_draft.mp4 for a quick look.
"""
import json
import shutil
import subprocess
import sys

import look
from common import brand, has_audio, job_dir, log, out_dir, write_srt
from render import caption_style, hook_filters, word_cues

AFADE = 0.08  # seconds of audio fade at each cut, enough to stop clicks without a noticeable dip


def frame_filter(fmt, W, H, focus_x):
    """Crop/scale for one piece. Vertical: a 9:16 window slid to focus_x across the frame."""
    if fmt == "vertical":
        fx = min(1.0, max(0.0, float(focus_x)))
        return (f"crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})':x='(iw-ow)*{fx:g}':y='(ih-oh)/2',"
                f"scale={W}:{H},setsar=1")
    return f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1"


def ff(args, cwd):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd, check=True)


def main():
    job = sys.argv[1]
    draft = "--draft" in sys.argv
    wd, od = job_dir(job), out_dir(job)
    src = wd / "tight.mp4"
    edit = json.loads((wd / "edit.json").read_text())
    words = json.loads((wd / "words.json").read_text()) if (wd / "words.json").exists() else []
    b = brand()
    lk, cap, vid = look.settings(), b["caption"], b["video"]
    fmt = edit.get("format") or b.get("montage", {}).get("format", "vertical")
    W, H = (b["width"], b["height"]) if fmt == "vertical" else (b["event"]["width"], b["event"]["height"])
    if draft:
        W, H = W // 2 // 2 * 2, H // 2 // 2 * 2
    fps = b["fps"]
    audio = has_audio(src)
    style = caption_style(cap)
    tmp = wd / "montage_parts"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    venc = ["-c:v", "libx264", "-crf", str(vid["crf"] + (6 if draft else 0)),
            "-preset", "veryfast" if draft else vid["preset"], "-pix_fmt", "yuv420p", "-an"]

    vparts, aparts = [], []
    for n, p in enumerate(edit["edit"], 1):
        # snap to the frame grid so each video part and its audio are exactly the same length
        a = round(float(p["in"]) * fps) / fps
        d = max(1, round((float(p["out"]) - float(p["in"])) * fps)) / fps
        z = a + d
        name = f"part_{n:02d}"
        vf = [f"fps={fps}", *look.stabilize_filters(lk, src, a, d, fps, tmp, name), *look.color_filters(lk),
              frame_filter(fmt, W, H, p.get("focus_x", 0.5))]
        if n == 1 and edit.get("hook"):
            vf += hook_filters(edit["hook"], name, tmp, b.get("hook", {}), H, cap["font"])
        cues = word_cues(words, a, z, cap["max_chars_per_line"]) if words else []
        if cues and not draft:
            write_srt(cues, tmp / f"{name}.srt")
            vf.append(f"subtitles={name}.srt:force_style='{style}'")
        ff(["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(src), "-vf", ",".join(vf),
            "-frames:v", str(round(d * fps)), *venc, f"{name}.mp4"], cwd=tmp)
        if audio:
            af = [*look.audio_filters(lk), "aresample=48000", "aformat=channel_layouts=stereo",
                  f"afade=in:st=0:d={AFADE}", f"afade=out:st={max(0, d - AFADE):.3f}:d={AFADE}",
                  f"apad,atrim=0:{d:.6f}"]
            ff(["-ss", f"{a:.3f}", "-t", f"{d:.3f}", "-i", str(src), "-vn", "-af", ",".join(af),
                "-c:a", "pcm_s16le", f"{name}.wav"], cwd=tmp)
        else:  # silent source: silence of the same length keeps every part aligned
            ff(["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo", "-t", f"{d:.6f}", "-c:a", "pcm_s16le",
                f"{name}.wav"], cwd=tmp)
        vparts.append(f"{name}.mp4")
        aparts.append(f"{name}.wav")
        log(job, f"render_shots: {name} #{p['shot']} {p.get('role', '')} ({d:.1f}s)")

    (tmp / "video.txt").write_text("".join(f"file '{x}'\n" for x in vparts))
    (tmp / "audio.txt").write_text("".join(f"file '{x}'\n" for x in aparts))
    final = od / ("montage_draft.mp4" if draft else "montage.mp4")
    loud = "loudnorm=I=-14:TP=-1.5:LRA=11" if vid.get("loudnorm") else "anull"
    ff(["-f", "concat", "-safe", "0", "-i", "video.txt", "-f", "concat", "-safe", "0", "-i", "audio.txt",
        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", loud, "-c:a", "aac", "-ar", "48000",
        "-b:a", vid["audio_bitrate"], "-shortest", "-movflags", "+faststart", str(final)], cwd=tmp)

    if not draft:
        lines = [f"# Montage ({job})", "", f"- Hook: {edit.get('hook', '')}", f"- Caption: {edit.get('caption', '')}",
                 f"- Hashtags: {' '.join(edit.get('hashtags', []))}", "", "## Cut", ""]
        t = 0.0
        for n, p in enumerate(edit["edit"], 1):
            d = p["out"] - p["in"]
            lines.append(f"{n}. {t:5.1f}s  shot #{p['shot']} ({p['in']:.1f}-{p['out']:.1f}s)  {p.get('role', '')}"
                         + (f": {p['why']}" if p.get("why") else ""))
            t += d
        (od / "montage.md").write_text("\n".join(lines) + "\n")
    shutil.rmtree(tmp, ignore_errors=True)
    log(job, f"render_shots: {final.name} ({sum(p['out'] - p['in'] for p in edit['edit']):.0f}s) -> {od}")


if __name__ == "__main__":
    main()
