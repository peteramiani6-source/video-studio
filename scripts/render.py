"""Step 4: cut, drop pauses, reframe to 9:16, burn hook + captions -> out/<job>/clip_NN_<slug>.mp4 + captions.md

Usage: python3 scripts/render.py <job-id> [--only N]
Captions use word timestamps (words.json) for short punchy lines; falls back to transcript.srt.
"""
import json
import re
import subprocess
import sys
import textwrap

from common import brand, env, fontfile, has_audio, job_dir, log, out_dir, parse_srt, write_srt
import look


def ass_color(hex_rgb):
    h = hex_rgb.lstrip("#")
    return f"&H00{h[4:6]}{h[2:4]}{h[0:2]}".upper()


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "clip"


def word_cues(words, start, end, max_chars):
    cues, cur = [], []
    for w in words:
        if w["start"] < start or w["end"] > end:
            continue
        text = " ".join(x["word"] for x in cur + [w])
        if cur and (len(text) > max_chars or w["start"] - cur[-1]["end"] > 0.6):
            cues.append(cur)
            cur = []
        cur.append(w)
    if cur:
        cues.append(cur)
    return [{"start": c[0]["start"] - start, "end": c[-1]["end"] - start,
             "text": " ".join(x["word"] for x in c)} for c in cues]


def hook_filters(hook, name, wd, cfg, H, font):
    """drawtext filters showing the hook in the opening seconds, one centred line per filter.
    anchor "bottom" puts the last line's bottom at y (fraction of the height), just above the captions;
    "top" puts the first line's top there. Shadow + outline keep it readable on busy backgrounds
    (leaves, crowds) without a box; set "box": true for the old boxed look.
    Text goes through files (relative to cwd=wd) so quotes and colons need no escaping."""
    if not hook or not cfg.get("enabled", True):
        return []
    secs, size = float(cfg.get("seconds", 1.5)), int(cfg.get("font_size", 84))
    ff = fontfile(font, bold=True)
    fnt = f"fontfile='{ff}'" if ff else f"font='{font}'"
    hexc = lambda key, default: "0x" + str(cfg.get(key, default)).lstrip("#")
    style = []
    if cfg.get("box", False):
        style.append(f"box=1:boxcolor={hexc('box_color', '#000000')}@{cfg.get('box_opacity', 0.6)}:boxborderw=16")
    if int(cfg.get("outline", 3)):
        style.append(f"borderw={int(cfg.get('outline', 3))}:bordercolor={hexc('outline_color', '#000000')}")
    if int(cfg.get("shadow", 5)):
        sh = int(cfg.get("shadow", 5))
        style.append(f"shadowx={sh}:shadowy={sh}:shadowcolor={hexc('shadow_color', '#000000')}@0.7")
    fade = min(0.3, secs / 4)
    alpha = f"alpha='if(lt(t,{secs - fade:.3f}),1,max(0,({secs}-t)/{fade:.3f}))'"
    lines = textwrap.wrap(hook, int(cfg.get("max_chars_per_line", 16)))
    step, base = size * 1.35, H * float(cfg.get("y", 0.61))
    top = base - len(lines) * step if cfg.get("anchor", "bottom") == "bottom" else base
    out = []
    for k, line in enumerate(lines):
        tf = f"{name}_hook_{k}.txt"
        (wd / tf).write_text(line)
        out.append(f"drawtext={fnt}:textfile={tf}:expansion=none:fontsize={size}:"
                   f"fontcolor={hexc('color', '#FFFFFF')}:" + "".join(x + ":" for x in style) +
                   f"x=(w-text_w)/2:y={int(top + k * step)}:{alpha}:enable='lt(t,{secs})'")
    return out


def segment_cues(segs, start, end):
    return [{"start": max(0, s["start"] - start), "end": min(end, s["end"]) - start, "text": s["text"]}
            for s in segs if s["end"] > start and s["start"] < end]


def keep_ranges(words, start, end, min_gap, margin, fps):
    """Clip-relative (a, b) ranges to keep: pauses between words longer than min_gap are cut,
    keeping margin seconds on each side. Bounds snap to the frame grid so audio and video stay in sync."""
    ws = [w for w in words if w["start"] >= start and w["end"] <= end]
    ranges, a = [], start
    for prev, w in zip(ws, ws[1:]):
        if w["start"] - prev["end"] > min_gap:
            ranges.append((a, prev["end"] + margin))
            a = w["start"] - margin
    ranges.append((a, end))
    snap = lambda x: round((x - start) * fps) / fps
    return [(snap(a), snap(b)) for a, b in ranges if snap(b) > snap(a)]


def remap(t, ranges):
    """Clip-relative source time -> time in the cut clip (times inside a cut land on the next kept range)."""
    off = 0.0
    for a, b in ranges:
        if t < a:
            return off
        if t <= b:
            return off + t - a
        off += b - a
    return off


def main():
    job = sys.argv[1]
    only = int(sys.argv[sys.argv.index("--only") + 1]) if "--only" in sys.argv else None
    wd, od = job_dir(job), out_dir(job)
    src = wd / "tight.mp4"
    clips = json.loads((wd / "clips.json").read_text())
    words = json.loads((wd / "words.json").read_text()) if (wd / "words.json").exists() else []
    segs = parse_srt((wd / "transcript.srt").read_text())
    b = brand()
    cap, vid = b["caption"], b["video"]
    W, H = b["width"], b["height"]

    style = ",".join([
        f"FontName={cap['font']}", f"FontSize={cap['font_size']}", f"Bold={1 if cap.get('bold') else 0}",
        f"PrimaryColour={ass_color(cap['primary_color'])}", f"OutlineColour={ass_color(cap['outline_color'])}",
        "BorderStyle=1", f"Outline={cap['outline']}", f"Shadow={cap['shadow']}",
        "Alignment=2", f"MarginV={cap['margin_v']}"])
    fps = b["fps"]
    vf = (f"crop=w='min(iw,ih*{W}/{H})':h='min(ih,iw*{H}/{W})',"
          f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1")
    audio = has_audio(src)
    lk = look.settings()
    cut = env("SILENCE_CUT", "1") == "1" and bool(words) and audio
    min_gap = float(env("SILENCE_MIN_GAP", 0.8))
    margin = float(str(env("SILENCE_MARGIN", 0.2)).rstrip("sec"))  # tolerates the old "0.2sec" form

    notes = [f"# {job}\n"]
    for i, c in enumerate(clips, 1):
        if only and i != only:
            continue
        start, end = float(c["start"]), float(c["end"])
        name = f"clip_{i:02d}_{slugify(c.get('title', ''))}"
        ranges = keep_ranges(words, start, end, min_gap, margin, fps) if cut else [(0.0, end - start)]
        length = sum(b_ - a for a, b_ in ranges)
        if words:
            moved = [{**w, "start": remap(w["start"] - start, ranges), "end": remap(w["end"] - start, ranges)}
                     for w in words if w["start"] >= start and w["end"] <= end]
            cues = word_cues(moved, 0.0, length + 0.01, cap["max_chars_per_line"])
        else:
            cues = segment_cues(segs, start, end)
        srt = f"{name}.srt"
        write_srt(cues, wd / srt)
        hook = hook_filters(c.get("hook", ""), name, wd, b.get("hook", {}), H, cap["font"])

        # Polish (stabilize, colour) on the clip window, then each kept range is trimmed from one split
        stab = look.stabilize_filters(lk, src, start, end - start, fps, wd, name)
        pre = ",".join([f"fps={fps}", *stab, *look.color_filters(lk)])
        k = len(ranges)
        graph = [f"[0:v]{pre},split={k}" + "".join(f"[s{j}]" for j in range(k))]
        graph += [f"[s{j}]trim=start={a:.3f}:end={b_:.3f},setpts=PTS-STARTPTS[v{j}]"
                  for j, (a, b_) in enumerate(ranges)]
        if audio:
            graph.append(f"[0:a]asplit={k}" + "".join(f"[r{j}]" for j in range(k)))
            graph += [f"[r{j}]atrim=start={a:.3f}:end={b_:.3f},asetpts=PTS-STARTPTS[a{j}]"
                      for j, (a, b_) in enumerate(ranges)]
            graph.append("".join(f"[v{j}][a{j}]" for j in range(k)) + f"concat=n={k}:v=1:a=1[vc][ac]")
            afx = [*look.audio_filters(lk), *(["loudnorm=I=-14:TP=-1.5:LRA=11"] if vid.get("loudnorm") else [])]
            graph.append("[ac]" + (",".join(afx) or "anull") + "[a]")
        else:
            graph.append("".join(f"[v{j}]" for j in range(k)) + f"concat=n={k}:v=1:a=0[vc]")
        subs = [f"subtitles={srt}:force_style='{style}'"] if cues else []  # libass can't open an empty SRT
        graph.append("[vc]" + ",".join([vf, *hook, *subs]) + "[v]")

        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
               "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}", "-i", str(src),
               "-filter_complex", ";".join(graph), "-map", "[v]",
               "-c:v", "libx264", "-crf", str(vid["crf"]), "-preset", vid["preset"], "-pix_fmt", "yuv420p"]
        if audio:
            cmd += ["-map", "[a]", "-c:a", "aac", "-b:a", vid["audio_bitrate"]]
        cmd += ["-movflags", "+faststart", str(od / f"{name}.mp4")]
        subprocess.run(cmd, cwd=wd, check=True)  # cwd=wd keeps the subtitles path unescaped
        trimmed = f", {end - start - length:.1f}s of pauses cut" if k > 1 else ""
        log(job, f"render: {name}.mp4 ({length:.0f}s{trimmed})")

        notes.append(f"## {i}. {c.get('title', name)}\n"
                     f"- File: `{name}.mp4`  ({start:.1f}s to {end:.1f}s)\n"
                     f"- Hook: {c.get('hook', '')}\n"
                     f"- Caption: {c.get('caption', '')}\n"
                     f"- Hashtags: {' '.join(c.get('hashtags', []))}\n")

    if not only:
        (od / "captions.md").write_text("\n".join(notes))
    log(job, f"render: done -> {od}")


if __name__ == "__main__":
    main()
