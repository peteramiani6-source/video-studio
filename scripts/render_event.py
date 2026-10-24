"""Event step 4: render the finished event video from plan.json

Usage: python3 scripts/render_event.py <job-id> [--skip-highlights] [--draft]

--draft renders a fast half-resolution preview (event_full_draft.mp4, event_highlights_draft.mp4)
for checking the edit; the final files are left alone. Re-run without --draft for the real thing.

Outputs in out/<job>/:
  event_full.mp4        title card -> kept segments (fades, lower-thirds) -> end card, loudness-normalised
  event_highlights.mp4  60-120 s highlight reel
  event_full.srt        subtitles re-timed to the edited video (upload alongside to YouTube)
  youtube.md            title, description and chapters, ready to paste
"""
import json
import shutil
import subprocess
import sys

from common import ROOT, brand, duration, fontfile, job_dir, log, out_dir, parse_srt, write_srt
import look

JOIN_GAP = 0.25  # segments closer than this in the source are one continuous take: no fade between them


def hexc(c):
    return "0x" + c.lstrip("#")


def ff(args, cwd):
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd, check=True)


class Renderer:
    def __init__(self, job, draft=False):
        self.job, self.wd, self.od = job, job_dir(job), out_dir(job)
        self.tmp = self.wd / "parts"
        shutil.rmtree(self.tmp, ignore_errors=True)
        self.tmp.mkdir()
        self.src = self.wd / "tight.mp4"
        self.plan = json.loads((self.wd / "plan.json").read_text())
        b = brand()
        self.ev, self.vid = b["event"], b["video"]
        self.W, self.H, self.fps = self.ev["width"], self.ev["height"], self.ev["fps"]
        e, v = self.ev, self.vid
        preset, crf, abr = e.get("preset", v["preset"]), e.get("crf", v["crf"]), e.get("audio_bitrate", "192k")
        self.suffix = ""
        if draft:  # half size, fastest encode: for checking cuts, names and timing, not for publishing
            self.W, self.H = self.W // 4 * 2, self.H // 4 * 2
            preset, crf, abr, self.suffix = "ultrafast", 30, "96k", "_draft"
        self.k = self.H / 1080  # text and logo sizes below are designed at 1080p
        self.enc = ["-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-ar", "48000", "-ac", "2", "-b:a", abr]
        self.font = fontfile(self.ev["font"])
        self.font_b = fontfile(self.ev["font"], bold=True) or self.font
        self.logo = ROOT / "assets" / "logo.png"
        self.music = ROOT / "assets" / "intro_music.mp3"
        self.n = 0

    def text(self, name, s):
        p = self.tmp / f"{name}.txt"
        p.write_text(s)
        return p.name  # drawtext reads it relative to cwd=self.tmp: no escaping problems

    def px(self, n):
        return int(round(n * self.k))

    def dt(self, textfile, size, color, x, y, bold=False, extra=""):
        f = self.font_b if bold else self.font
        return (f"drawtext=fontfile='{f}':textfile={textfile}:expansion=none:fontsize={self.px(size)}:"
                f"fontcolor={hexc(color)}:x={x}:y={y}{extra}")

    def card(self, name, line1, line2, seconds):
        """Solid-colour card with centred text, optional logo and intro music."""
        e = self.ev
        out = self.tmp / f"{name}.mp4"
        filters = [f"color=c={hexc(e['title_bg'])}:s={self.W}x{self.H}:r={self.fps}:d={seconds}[bg]"]
        chain = "[bg]"
        inputs = ["-f", "lavfi", "-i", f"color=c=black:s=16x16:d={seconds}"]  # placeholder input 0
        idx = 1
        if self.logo.exists():
            inputs += ["-i", str(self.logo)]
            filters.append(f"[{idx}:v]scale={self.px(360)}:-1[logo]")
            filters.append(f"{chain}[logo]overlay=(W-w)/2:H*0.18[v1]")
            chain = "[v1]"
            idx += 1
        draws = [self.dt(self.text(f"{name}_1", line1), 76, e["text_color"], "(w-text_w)/2", "(h-text_h)/2", True)]
        if line2:
            draws.append(self.dt(self.text(f"{name}_2", line2), 40, e["accent"], "(w-text_w)/2", f"(h/2)+{self.px(70)}"))
        fade = e["fade_seconds"] * 2
        filters.append(f"{chain}{','.join(draws)},fade=in:st=0:d={fade},fade=out:st={seconds - fade}:d={fade},"
                       f"format=yuv420p[v]")
        if self.music.exists() and name == "title":
            inputs += ["-i", str(self.music)]
            filters.append(f"[{idx}:a]atrim=0:{seconds},afade=out:st={seconds - 1}:d=1,"
                           f"aformat=sample_rates=48000:channel_layouts=stereo[a]")
        else:
            filters.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{seconds}[a]")
        ff([*inputs, "-filter_complex", ";".join(filters), "-map", "[v]", "-map", "[a]",
            "-t", str(seconds), *self.enc, str(out)], cwd=self.tmp)
        return out

    def segment(self, seg, lower_third=None, fade=None, fade_in=True, fade_out=True):
        e = self.ev
        fade = e["fade_seconds"] if fade is None else fade
        self.n += 1
        out = self.tmp / f"seg_{self.n:03d}.mp4"
        s, d = float(seg["start"]), float(seg["end"]) - float(seg["start"])
        lk = look.settings()
        stab = look.stabilize_filters(lk, self.src, s, d, self.fps, self.tmp, out.stem)
        vf = [f"fps={self.fps}", *stab, *look.color_filters(lk),
              f"scale={self.W}:{self.H}:force_original_aspect_ratio=decrease",
              f"pad={self.W}:{self.H}:(ow-iw)/2:(oh-ih)/2", "setsar=1"]
        af = look.audio_filters(lk)
        if fade_in and fade:
            vf.append(f"fade=in:st=0:d={fade}")
            af.append(f"afade=in:st=0:d={fade}")
        if fade_out and fade:
            vf.append(f"fade=out:st={max(0, d - fade):.3f}:d={fade}")
            af.append(f"afade=out:st={max(0, d - fade):.3f}:d={fade}")
        if lower_third:
            name, role = lower_third
            t0, t1 = 1.0, 1.0 + e["lower_third_seconds"]
            en = f":enable='between(t,{t0},{t1})'"
            box = f":box=1:boxcolor=black@0.6:boxborderw={self.px(18)}"
            x = str(self.px(90))
            vf.append(self.dt(self.text(f"lt{self.n}_name", name), 46, e["text_color"], x, f"h-{self.px(230)}",
                              True, box + en))
            if role:
                vf.append(self.dt(self.text(f"lt{self.n}_role", role), 32, e["accent"], x, f"h-{self.px(150)}",
                                  False, box + en))
        ff(["-ss", f"{s:.3f}", "-i", str(self.src), "-t", f"{d:.3f}", "-vf", ",".join(vf),
            "-af", ",".join(af) or "anull", *self.enc, str(out)], cwd=self.tmp)
        return out

    def concat(self, parts, final):
        lst = self.tmp / f"{final.stem}.txt"
        lst.write_text("".join(f"file '{p.name}'\n" for p in parts))
        joined = self.tmp / f"{final.stem}_joined.mp4"
        ff(["-f", "concat", "-safe", "0", "-i", lst.name, "-c", "copy", joined.name], cwd=self.tmp)
        ff(["-i", joined.name, "-c:v", "copy",
            "-af", f"loudnorm=I={self.ev['loudness_lufs']}:TP=-1.5:LRA=11",
            "-c:a", "aac", "-ar", "48000", "-b:a", self.enc[-1], "-movflags", "+faststart", str(final)], cwd=self.tmp)

    def full(self):
        p, e = self.plan, self.ev
        parts, timeline, t = [], [], 0.0
        if p.get("title"):
            parts.append(self.card("title", p["title"], p.get("subtitle", ""), e["title_seconds"]))
            t = duration(parts[-1])
        last_speaker = None
        segs = p["segments"]
        # joined[i]: segment i carries straight on from segment i-1 in the source (e.g. one talk split
        # into two chapters), so that cut gets no fade-out/fade-in dip
        joined = [i > 0 and 0 <= float(segs[i]["start"]) - float(segs[i - 1]["end"]) < JOIN_GAP
                  for i in range(len(segs))]
        for i, seg in enumerate(segs):
            spk = (seg.get("speaker") or "").strip()
            lt = (spk, (seg.get("role") or "").strip()) if spk and spk != last_speaker else None
            last_speaker = spk or last_speaker
            nxt_joined = i + 1 < len(segs) and joined[i + 1]
            part = self.segment(seg, lt, fade_in=not joined[i], fade_out=not nxt_joined)
            parts.append(part)
            d = duration(part)
            timeline.append({"src_start": seg["start"], "src_end": seg["end"], "out_start": t,
                             "label": seg.get("label") or "Section"})
            t += d
            log(self.job, f"render_event: {seg.get('label', 'segment')} ({d:.0f}s)")
        if e.get("end_text"):
            parts.append(self.card("end", e["end_text"], p.get("title", ""), e["end_seconds"]))
        self.final = self.od / f"event_full{self.suffix}.mp4"
        self.concat(parts, self.final)
        log(self.job, f"render_event: {self.final.name} ({duration(self.final) / 60:.1f} min)")
        return timeline

    def highlights(self):
        hl = self.plan.get("highlights") or []
        if not hl:
            log(self.job, "render_event: no highlights in plan, skipping reel")
            return
        parts = []
        if self.plan.get("title"):
            parts.append(self.card("title", self.plan["title"], self.plan.get("subtitle", ""), 3))
        parts += [self.segment(h, fade=0.25) for h in hl]
        final = self.od / f"event_highlights{self.suffix}.mp4"
        self.concat(parts, final)
        log(self.job, f"render_event: {final.name} ({duration(final):.0f}s)")

    def subtitles_and_chapters(self, timeline):
        segs = parse_srt((self.wd / "transcript.srt").read_text())
        cues = []
        for tl in timeline:
            for s in segs:
                mid = (s["start"] + s["end"]) / 2  # each line belongs to the section holding its midpoint
                if not (tl["src_start"] <= mid < tl["src_end"]):
                    continue
                a = max(s["start"], tl["src_start"]) - tl["src_start"] + tl["out_start"]
                b = min(s["end"], tl["src_end"]) - tl["src_start"] + tl["out_start"]
                cues.append({"start": a, "end": b, "text": s["text"]})
        write_srt(cues, self.od / "event_full.srt")

        chapters = [(0.0, "Intro")] if timeline and timeline[0]["out_start"] > 0 else []
        for tl in timeline:
            if chapters and chapters[-1][1] == tl["label"]:
                continue
            if chapters and tl["out_start"] - chapters[-1][0] < 10:  # YouTube needs 10 s+ per chapter
                continue
            chapters.append((tl["out_start"] if chapters else 0.0, tl["label"]))
        total = duration(self.final)
        while len(chapters) > 1 and total - chapters[-1][0] < 10:  # last chapter must be 10 s+ too
            chapters.pop()
        yt = self.plan.get("youtube", {})
        lines = [f"# {yt.get('title') or self.plan.get('title', '')}", "", yt.get("description", ""), "",
                 "## Chapters (paste into the YouTube description)", ""]
        lines += [f"{self.yt_ts(t)} {label}" for t, label in chapters]
        (self.od / "youtube.md").write_text("\n".join(lines) + "\n")

    @staticmethod
    def yt_ts(t):
        t = int(t)
        h, r = divmod(t, 3600)
        m, s = divmod(r, 60)
        return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def main():
    job = sys.argv[1]
    draft = "--draft" in sys.argv
    r = Renderer(job, draft=draft)
    timeline = r.full()
    if not draft:  # timings match the final edit; written with it so a draft never looks "done"
        r.subtitles_and_chapters(timeline)
    if "--skip-highlights" not in sys.argv:
        r.highlights()
    shutil.rmtree(r.tmp, ignore_errors=True)
    log(job, f"render_event: done -> {r.od}")


if __name__ == "__main__":
    main()
