"""Montage step 4: the model looks at the contact sheets and builds the cut -> work/<job>/edit.json

Usage: python3 scripts/plan_shots.py <job-id> [--brief "..."] [--hook "..."]

Unlike the transcript-only steps, the model sees a keyframe of every shot (frames/sheet_NN.jpg) plus
each shot's sharpness, motion and speech. It returns shots in the order to SHOW them (not recording
order), with in/out points, a role, and where the subject sits horizontally (focus_x) so the 9:16 crop
follows the people instead of whatever is in the centre.

edit.json is plain JSON: reorder entries, change in/out or focus_x by hand (or ask Claude Code to),
then re-run render_shots.py. PICKER=none skips the model and keeps the sharpest, steadiest shots.
"""
import argparse
import json
import sys

from common import ROOT, clean_range, env, job_dir, log
from llm import ask_json
from shots import montage_cfg

ROLES = ("wide", "gear", "host", "guest", "speaker", "reaction", "detail", "ending", "other")

PROMPT = """You are cutting a short {format} video (about {seconds} seconds) from the shots below.
{brief}
Each image is a contact sheet: every tile is one shot, labelled "#id  start-time  (length)".
Shot data (times in seconds of the source; blur: higher = blurrier; motion: higher = shakier or busier;
speech: what is said during the shot):
{table}

Editing rules:
- Show the story, not the gear: equipment (tripods, phones, lights, cables) gets at most {gear_max:g} seconds in total.
- Prefer sharp, steady shots where faces are clear. Skip blurry, shaky, cluttered or glare-washed shots.
- A good shape: open on a clean wide shot, a short establishing beat, then close-ups of the people
  talking and reacting, and end on a human moment (a laugh, a handshake, a smile).
- Each piece is {min_shot:g}-{max_shot:g} seconds. Order pieces for the story, not by recording time.
- Pieces must not overlap each other in source time.
- focus_x: where the main subject is across the frame (0 = left edge, 0.5 = centre, 1 = right edge),
  so a vertical crop keeps the people rather than the gear in the middle.
- hook: on-screen opening text, max 7 words. caption: 1-2 sentences for the post. hashtags: 3-5.

Return ONLY one JSON object:
{{"hook": "", "caption": "", "hashtags": [],
  "edit": [{{"shot": 1, "in": 0.0, "out": 4.0, "role": "{roles}", "focus_x": 0.5, "why": "short reason"}}]}}"""


def shot_table(shots):
    rows = []
    for s in shots:
        rows.append(f"#{s['id']}: {s['start']:.1f}-{s['end']:.1f}s take {s['take']}, "
                    f"blur {s['blur'] if s['blur'] is not None else 'n/a'}, "
                    f"motion {s['motion'] if s['motion'] is not None else 'n/a'}"
                    + (f', speech: "{s["speech"]}"' if s.get("speech") else ""))
    return "\n".join(rows)


def validate_edit(obj, shots, cfg):
    """Clean a model-written (or hand-edited) montage edit. Raises ValueError if fewer than 2 usable pieces."""
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    by_id = {s["id"]: s for s in shots}
    lo, hi = float(cfg["min_shot"]), float(cfg["max_shot"])
    out, used = [], []
    for it in obj.get("edit") or []:
        if not isinstance(it, dict):
            continue
        try:
            shot = by_id[int(it.get("shot"))]
        except (TypeError, ValueError, KeyError):
            continue
        rng = clean_range({"start": it.get("in", shot["start"]), "end": it.get("out", shot["end"])})
        if rng is None:
            continue
        a, b = max(rng["start"], shot["start"]), min(rng["end"], shot["end"])  # stay inside the shot
        if b - a > hi:
            b = a + hi
        if b - a < min(lo, shot["end"] - shot["start"]) * 0.9:
            continue
        if any(a < ub and b > ua for ua, ub in used):  # overlaps a piece already in the cut
            continue
        try:
            fx = min(1.0, max(0.0, float(it.get("focus_x", 0.5))))
        except (TypeError, ValueError):
            fx = 0.5
        role = str(it.get("role") or "other").lower()
        out.append({"shot": shot["id"], "in": round(a, 3), "out": round(b, 3),
                    "role": role if role in ROLES else "other", "focus_x": round(fx, 3),
                    "why": str(it.get("why") or "")})
        used.append((a, b))
    if len(out) < 2:
        raise ValueError('"edit" needs at least 2 usable pieces (shot id that exists, in/out inside the shot)')
    tags = obj.get("hashtags") or []
    return {"hook": str(obj.get("hook") or ""), "caption": str(obj.get("caption") or ""),
            "hashtags": [str(t) for t in tags] if isinstance(tags, list) else str(tags).split(),
            "edit": out}


def quality_warnings(edit, shots):
    """Flag pieces whose shot measured far blurrier or shakier than the footage's typical shot.
    The model's choice stands (a soft shot can be deliberate); the warning tells you where to look."""
    def median(vals):
        vals = sorted(v for v in vals if v is not None)
        return vals[len(vals) // 2] if vals else None
    by_id = {s["id"]: s for s in shots}
    mb, mm = median(s["blur"] for s in shots), median(s["motion"] for s in shots)
    out = []
    for n, p in enumerate(edit["edit"], 1):
        s = by_id[p["shot"]]
        if mb and s["blur"] is not None and s["blur"] > 2 * mb:
            out.append(f"piece {n} (shot #{s['id']}) looks blurry: blur {s['blur']} vs typical {mb}")
        if mm and s["motion"] is not None and s["motion"] > 2.5 * mm:
            out.append(f"piece {n} (shot #{s['id']}) looks shaky or busy: motion {s['motion']} vs typical {mm}")
    return out


def heuristic_edit(shots, cfg):
    """No model: the sharpest, steadiest shots, one piece each, in recording order, up to the target length."""
    def score(s):
        return (s["blur"] or 0) + 0.3 * (s["motion"] or 0)
    target, hi = float(cfg["seconds"]), float(cfg["max_shot"])
    picked, total = [], 0.0
    for s in sorted(shots, key=score):
        if total >= target:
            break
        length = min(hi, s["end"] - s["start"])
        mid = (s["start"] + s["end"]) / 2
        picked.append({"shot": s["id"], "in": round(mid - length / 2, 3), "out": round(mid + length / 2, 3),
                       "role": "other", "focus_x": 0.5, "why": "sharp and steady (no model)"})
        total += length
    picked.sort(key=lambda p: p["in"])
    return {"hook": "", "caption": "", "hashtags": [], "edit": picked}


def main():
    ap = argparse.ArgumentParser(description="Build a shot-based montage edit (edit.json)")
    ap.add_argument("job")
    ap.add_argument("--brief", default="", help="what the video is, e.g. 'behind the scenes of our garden interview'")
    ap.add_argument("--hook", default="", help="force the opening text instead of letting the model write it")
    args = ap.parse_args()
    wd = job_dir(args.job)
    data = json.loads((wd / "shots.json").read_text())
    shots, cfg = data["shots"], montage_cfg()
    picker = env("PICKER", "claude-code")

    if picker == "none":
        edit = heuristic_edit(shots, cfg)
        log(args.job, f"plan_shots: PICKER=none, kept {len(edit['edit'])} sharpest/steadiest shots")
    else:
        prompt = PROMPT.format(format=cfg["format"], seconds=cfg["seconds"], gear_max=float(cfg["gear_max"]),
                               min_shot=float(cfg["min_shot"]), max_shot=float(cfg["max_shot"]),
                               brief=f"What it is: {args.brief}\n" if args.brief else "",
                               table=shot_table(shots), roles="|".join(ROLES))
        raw_path = wd / "edit_raw.txt"
        raw_path.unlink(missing_ok=True)
        sheets = [wd / s for s in data["sheets"]]
        try:
            edit = ask_json(prompt, "object", lambda o: validate_edit(o, shots, cfg), raw_path, images=sheets)
        except Exception as e:
            log(args.job, f"plan_shots: FAILED ({type(e).__name__}: {e}). Raw replies: {raw_path}")
            sys.exit("plan_shots: no usable edit from the model. Fix the cause and resume, "
                     "or set PICKER=none for an automatic sharpest-shots cut.")
        log(args.job, f"plan_shots: {picker} chose {len(edit['edit'])} pieces: "
                      + ", ".join(f"#{p['shot']} {p['role']}" for p in edit["edit"]))
    for msg in quality_warnings(edit, shots):
        log(args.job, f"plan_shots: WARNING {msg}")
    if args.hook:
        edit["hook"] = args.hook
    edit["format"] = cfg["format"]
    (wd / "edit.json").write_text(json.dumps(edit, indent=2))
    secs = sum(p["out"] - p["in"] for p in edit["edit"])
    log(args.job, f"plan_shots: edit.json written ({secs:.0f}s, {len(edit['edit'])} pieces)"
                  f" -> review it or the contact sheets in {(wd / 'frames').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
