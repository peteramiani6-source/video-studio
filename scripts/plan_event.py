"""Event step 3: the edit decision list -> work/<job>/plan.json (+ clips.json for vertical clips)

Usage: python3 scripts/plan_event.py <job-id> [--title "..."] [--subtitle "..."]

The model's reply is validated (times parsed, broken entries dropped, at least one segment required)
and retried once with the error. If it is still unusable the step fails, rather than silently keeping
the whole event: fix the cause, or set PICKER=none to keep everything between the first and last words.

The model reads the timestamped transcript and decides what stays, what each section is called,
who is speaking (for lower-thirds), the highlight moments and the social clips.
plan.json is plain JSON: review or edit it (or ask Claude Code to), then re-run render_event.py.
"""
import argparse
import json
import sys

from common import clean_range, duration, env, job_dir, log, parse_srt, parse_time
from llm import ask_json
from pick_clips import snap, validate_clips

PROMPT = """You are editing a recorded event into a finished video.

Event: {title}
Details: {subtitle}
Known speakers (use these spellings): {speakers}
Notes from the organiser: {notes}
Recording length: {total:.0f} seconds. {target}

Below is the transcript with timestamps in seconds. Lines marked (no speech ...) are gaps: they may be
music, singing, a performance, applause or just waiting. Keep a gap only if it sits inside a kept section
or the notes say it matters.

Decide:
1. "segments": the parts to KEEP, in time order. Cut setup, mic checks, long waits, housekeeping
   announcements and dead air. Keep every speech, talk, testimony, performance and key moment complete,
   starting at the first word and ending after the last sentence. Give each a short "label" (used as a
   chapter title), and "speaker" + "role" when one person is presenting (empty strings otherwise).
2. "highlights": 6-10 moments of 5-20 seconds each for a 60-120 second highlight reel. Pick strong lines,
   applause, laughter and emotional beats.
3. "social_clips": {clips} self-contained moments of {lo}-{hi} seconds for Reels/TikTok, each with a
   "title", "hook" (max 8 words), "caption" (1-2 sentences) and "hashtags" (3-5).
4. "youtube": a "title" and a "description" (3-5 sentences).

Return ONLY one JSON object:
{{"segments": [{{"start": 0, "end": 0, "label": "", "speaker": "", "role": ""}}],
  "highlights": [{{"start": 0, "end": 0}}],
  "social_clips": [{{"start": 0, "end": 0, "title": "", "hook": "", "caption": "", "hashtags": []}}],
  "youtube": {{"title": "", "description": ""}}}}

Transcript:
{transcript}"""


to_sec = parse_time  # kept for anything importing the old name


def validate_plan(obj, total):
    """Clean a model-written (or hand-edited) plan. Raises ValueError if there is no usable segment."""
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    segs = []
    for it in obj.get("segments") or []:
        c = clean_range(it, total)
        if c is None:
            continue
        for k in ("speaker", "role"):
            c[k] = str(c.get(k) or "").strip()
        c["label"] = str(c.get("label") or "").strip() or "Section"
        segs.append(c)
    if not segs:
        raise ValueError('"segments" has no entry with a usable start and end')
    hl = [c for c in (clean_range(h, total) for h in obj.get("highlights") or []) if c]
    yt = obj.get("youtube") if isinstance(obj.get("youtube"), dict) else {}
    return {"segments": segs, "highlights": [{"start": h["start"], "end": h["end"]} for h in hl],
            "social_clips": validate_clips(obj.get("social_clips") or [], total, allow_empty=True),
            "youtube": {"title": str(yt.get("title") or ""), "description": str(yt.get("description") or "")}}


def transcript_with_gaps(segs, total):
    lines, prev = [], 0.0
    for s in segs:
        if s["start"] - prev > 20:
            lines.append(f"[{prev:.0f}-{s['start']:.0f}] (no speech for {s['start'] - prev:.0f}s)")
        lines.append(f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}")
        prev = s["end"]
    if total - prev > 20:
        lines.append(f"[{prev:.0f}-{total:.0f}] (no speech for {total - prev:.0f}s)")
    return "\n".join(lines)


def clean_ranges(items, total, min_len, pad=0.4):
    out = []
    for it in sorted(items, key=lambda x: float(x["start"])):
        s = max(0.0, float(it["start"]) - pad)
        e = min(total, float(it["end"]) + pad)
        if out and s < out[-1]["end"]:
            if it.get("label", "") == out[-1].get("label", ""):  # same section: merge
                out[-1]["end"] = max(out[-1]["end"], e)
                continue
            s = out[-1]["end"]  # different section: start where the previous one ends
        if e - s < min_len:
            continue
        out.append({**it, "start": round(s, 2), "end": round(e, 2)})
    return out


def main():
    ap = argparse.ArgumentParser(description="Write the event edit (plan.json) from the transcript")
    ap.add_argument("job")
    ap.add_argument("--title", default="")
    ap.add_argument("--subtitle", default="")
    args = ap.parse_args()
    job = args.job
    wd = job_dir(job)
    total = duration(wd / "tight.mp4")
    segs = parse_srt((wd / "transcript.srt").read_text())
    ev = json.loads((wd / "event.json").read_text()) if (wd / "event.json").exists() else {}
    title = args.title or ev.get("title", "")
    subtitle = args.subtitle or ev.get("subtitle", "")
    lo, hi = float(env("CLIP_MIN", 25)), float(env("CLIP_MAX", 60))
    n_clips = int(env("EVENT_CLIP_COUNT", 5))
    target = (f"Target length of the full edit: about {ev['target_minutes']} minutes; keep the most important parts."
              if ev.get("target_minutes") else "Keep all substantive content; only remove dead time.")

    plan = None
    if env("PICKER", "claude-code") != "none":
        prompt = PROMPT.format(title=title or "(not given)", subtitle=subtitle or "(not given)",
                               speakers=", ".join(ev.get("speakers", [])) or "(not given)",
                               notes=ev.get("notes", "(none)"), total=total, target=target,
                               clips=n_clips, lo=int(lo), hi=int(hi),
                               transcript=transcript_with_gaps(segs, total))
        raw_path = wd / "plan_raw.txt"
        raw_path.unlink(missing_ok=True)
        try:
            plan = ask_json(prompt, "object", lambda o: validate_plan(o, total), raw_path)
        except Exception as e:
            log(job, f"plan: FAILED ({type(e).__name__}: {e}). Raw replies: {raw_path}")
            sys.exit("plan: no usable edit from the model. Fix the cause (login, PICKER in config/models.env) "
                     "and resume, or set PICKER=none to keep the whole event.")
        log(job, f"plan: model returned {len(plan['segments'])} segments")
    if plan is None:  # fallback: trim the dead time before the first and after the last words
        first = max(0.0, segs[0]["start"] - 2) if segs else 0.0
        last = min(total, segs[-1]["end"] + 2) if segs else total
        plan = {"segments": [{"start": first, "end": last, "label": "Full event", "speaker": "", "role": ""}],
                "highlights": [], "social_clips": [], "youtube": {"title": title, "description": ""}}

    # organiser's must_keep ranges always survive
    for rng in ev.get("must_keep", []):
        try:
            a, b = rng
            plan["segments"].append({"start": parse_time(a), "end": parse_time(b), "label": "Performance",
                                     "speaker": "", "role": ""})
        except (ValueError, TypeError):
            sys.exit(f'plan: event.json must_keep entry {rng!r} is not ["start", "end"], e.g. ["00:42:10", "00:47:30"]')

    plan["title"], plan["subtitle"] = title, subtitle
    plan["segments"] = clean_ranges(plan["segments"], total, 3.0)
    plan["highlights"] = [h for h in clean_ranges(plan.get("highlights", []), total, 3.0, pad=0.2)
                          if h["end"] - h["start"] <= 25]
    clips = snap(plan.get("social_clips", []), segs, total, lo, hi)[:n_clips] if segs else []
    plan["social_clips"] = clips

    (wd / "plan.json").write_text(json.dumps(plan, indent=2))
    (wd / "clips.json").write_text(json.dumps(clips, indent=2))
    kept = sum(s["end"] - s["start"] for s in plan["segments"])
    log(job, f"plan: keeping {len(plan['segments'])} segments, {kept / 60:.1f} of {total / 60:.1f} min; "
             f"{len(plan['highlights'])} highlights; {len(clips)} social clips")


if __name__ == "__main__":
    main()
