"""Step 3: choose the strongest moments -> work/<job>/clips.json

Usage: python3 scripts/pick_clips.py <job-id>
PICKER=claude-code | claude | gemini | none. Model output is validated: clamped to the video,
snapped to sentence boundaries, length-limited and de-overlapped.
"""
import json
import sys

from common import duration, env, job_dir, log, parse_srt
from llm import ask, extract_json

PROMPT = """You are a short-form video editor. Below is a timestamped transcript (seconds).
Pick the {n} strongest self-contained moments for Instagram Reels / TikTok / Shorts.

Rules:
- Each clip is {lo}-{hi} seconds long and makes sense with no context.
- Start on the first word of a sentence, end on a completed thought.
- Prefer a strong opening line, a clear insight, a story beat, humour or a surprising claim.
- No overlapping clips.

Return ONLY a JSON array, no prose, no code fences:
[{{"start": 12.4, "end": 51.0, "title": "short title",
   "hook": "on-screen hook, max 8 words",
   "caption": "post caption, 1-2 sentences",
   "hashtags": ["#tag1", "#tag2", "#tag3"]}}]

Transcript:
{transcript}"""


def evenly_spaced(total, n, lo, hi):
    k = max(1, min(n, int(total // lo)))  # only as many clips as actually fit
    step = total / k
    length = min(hi, step)
    return [{"start": i * step, "end": min(total, i * step + length), "title": f"Clip {i + 1}",
             "hook": "", "caption": "", "hashtags": []} for i in range(k)]


def snap(clips, segs, total, lo, hi):
    starts = [s["start"] for s in segs]
    ends = [s["end"] for s in segs]
    out = []
    for c in sorted(clips, key=lambda c: float(c["start"])):
        s = min(starts, key=lambda x: abs(x - float(c["start"])))
        e_candidates = [x for x in ends if lo <= x - s <= hi] or [min(total, s + hi)]
        e = min(e_candidates, key=lambda x: abs(x - float(c["end"])))
        s, e = max(0.0, s), min(total, e)
        if out and s < out[-1]["end"]:  # overlap: move start to the next sentence after the previous clip
            later = [x for x in starts if x >= out[-1]["end"]]
            if not later:
                continue
            s = later[0]
        if e - s < min(lo, total) * 0.8:
            continue
        out.append({**c, "start": round(s, 2), "end": round(e, 2)})
    return out


def main():
    job = sys.argv[1]
    wd = job_dir(job)
    segs = parse_srt((wd / "transcript.srt").read_text())
    total = duration(wd / "tight.mp4")
    n, lo, hi = int(env("CLIP_COUNT", 4)), float(env("CLIP_MIN", 25)), float(env("CLIP_MAX", 60))
    picker = env("PICKER", "claude-code")

    transcript = "\n".join(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}" for s in segs)
    prompt = PROMPT.format(n=n, lo=int(lo), hi=int(hi), transcript=transcript)

    clips = None
    if picker != "none":
        try:
            raw = ask(prompt)
            (wd / "picker_raw.txt").write_text(raw)
            clips = extract_json(raw)
            log(job, f"pick: {picker} proposed {len(clips)} clips")
        except Exception as e:  # unattended runs fall back rather than stall
            log(job, f"pick: WARNING {picker} failed ({type(e).__name__}: {e}); using evenly spaced clips")
    if clips is None:
        clips = evenly_spaced(total, n, lo, hi)

    clips = snap(clips, segs, total, lo, hi)[:n]
    if not clips:
        sys.exit("pick: no valid clips (video shorter than CLIP_MIN?)")
    (wd / "clips.json").write_text(json.dumps(clips, indent=2))
    log(job, "pick: " + ", ".join(f"{c['start']:.0f}-{c['end']:.0f}s" for c in clips))


if __name__ == "__main__":
    main()
