"""Scripture mode: animated verse videos with a short reflection and ways to live it.

Usage:
  python3 scripts/scripture.py new "Proverbs 3:5-6" [--theme "decisions after school"] [--id ep001]
  python3 scripts/scripture.py show <id>
  python3 scripts/scripture.py check [<id> ...]
  python3 scripts/scripture.py render <id> [--draft] [--format vertical|wide|both]
  python3 scripts/scripture.py render --all [--draft]

Episodes live in scripture/episodes/<id>.json. The verse text always comes from the bundled public-domain
KJV (scripture/data/kjv.json.gz), never from the model: `new` asks the model only for the hook, the
reflection, the "live it" points and the post caption. Every new episode starts with "reviewed": false,
and `render` refuses it until a person has read it and set "reviewed": true (or use --draft, which
stamps DRAFT on the video). Animation: the Remotion template in remotion/src/scripture/.
"""
import argparse
import functools
import gzip
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from common import ROOT, brand, duration, env, has_audio, log
from llm import ask_json

SCRIPTURE = ROOT / "scripture"
EPISODES = SCRIPTURE / "episodes"
KJV_PATH = SCRIPTURE / "data" / "kjv.json.gz"
REMOTION = ROOT / "remotion"
FPS = 30

# Common abbreviations -> canonical book name (anything else is matched by unique prefix)
ALIASES = {
    "gen": "Genesis", "ge": "Genesis", "gn": "Genesis", "ex": "Exodus", "exo": "Exodus", "exod": "Exodus",
    "lev": "Leviticus", "lv": "Leviticus", "num": "Numbers", "nm": "Numbers", "deut": "Deuteronomy",
    "dt": "Deuteronomy", "josh": "Joshua", "judg": "Judges", "jdg": "Judges", "ps": "Psalms", "psa": "Psalms",
    "psalm": "Psalms", "pss": "Psalms", "prov": "Proverbs", "pr": "Proverbs", "prv": "Proverbs",
    "eccl": "Ecclesiastes", "ecc": "Ecclesiastes", "qoh": "Ecclesiastes", "song": "Song of Solomon",
    "sos": "Song of Solomon", "songofsongs": "Song of Solomon", "canticles": "Song of Solomon",
    "isa": "Isaiah", "is": "Isaiah", "jer": "Jeremiah", "lam": "Lamentations", "ezek": "Ezekiel",
    "eze": "Ezekiel", "dan": "Daniel", "hos": "Hosea", "obad": "Obadiah", "jon": "Jonah", "mic": "Micah",
    "nah": "Nahum", "hab": "Habakkuk", "zeph": "Zephaniah", "hag": "Haggai", "zech": "Zechariah",
    "mal": "Malachi", "matt": "Matthew", "mt": "Matthew", "mk": "Mark", "mrk": "Mark", "lk": "Luke",
    "luk": "Luke", "jn": "John", "jhn": "John", "rom": "Romans", "ro": "Romans", "gal": "Galatians",
    "eph": "Ephesians", "phil": "Philippians", "php": "Philippians", "col": "Colossians",
    "tit": "Titus", "phlm": "Philemon", "philem": "Philemon", "heb": "Hebrews", "jas": "James",
    "jm": "James", "jud": "Jude", "rev": "Revelation", "re": "Revelation", "apoc": "Revelation",
    "1sam": "1 Samuel", "2sam": "2 Samuel", "1kgs": "1 Kings", "2kgs": "2 Kings", "1ki": "1 Kings",
    "2ki": "2 Kings", "1chr": "1 Chronicles", "2chr": "2 Chronicles", "1cor": "1 Corinthians",
    "2cor": "2 Corinthians", "1thess": "1 Thessalonians", "2thess": "2 Thessalonians", "1th": "1 Thessalonians",
    "2th": "2 Thessalonians", "1tim": "1 Timothy", "2tim": "2 Timothy", "1pet": "1 Peter", "2pet": "2 Peter",
    "1pt": "1 Peter", "2pt": "2 Peter", "1jn": "1 John", "2jn": "2 John", "3jn": "3 John",
}
ORDINALS = {"i": "1", "ii": "2", "iii": "3", "first": "1", "second": "2", "third": "3", "1st": "1", "2nd": "2", "3rd": "3"}


@functools.lru_cache(maxsize=1)
def kjv():
    with gzip.open(KJV_PATH, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    return {b["name"]: b["chapters"] for b in data["books"]}


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def book_name(raw):
    """'prov', 'Proverbs', '1 Cor', 'I John', 'first peter', 'Song of Songs' -> canonical KJV book name."""
    words = raw.strip().split()
    if words and words[0].lower().rstrip(".") in ORDINALS:
        words[0] = ORDINALS[words[0].lower().rstrip(".")]
    key = _norm(" ".join(words))
    if key in ALIASES:
        return ALIASES[key]
    names = list(kjv())
    exact = [n for n in names if _norm(n) == key]
    if exact:
        return exact[0]
    hits = [n for n in names if _norm(n).startswith(key)] if key else []
    if len(hits) == 1:
        return hits[0]
    raise ValueError(f"unknown or ambiguous book {raw!r}" + (f" (could be {', '.join(hits)})" if hits else ""))


REF = re.compile(r"^\s*(?P<book>.+?)\s*(?P<ch>\d+)\s*(?::\s*(?P<v1>\d+)(?:\s*[-–—]\s*(?P<v2>\d+))?)?\s*$")


def parse_ref(ref):
    """'Proverbs 3:5-6' -> ('Proverbs', 3, 5, 6). A whole chapter ('Psalms 23') is allowed if it is short."""
    m = REF.match(ref or "")
    if not m:
        raise ValueError(f"can't read reference {ref!r}; use e.g. 'Proverbs 3:5-6'")
    book = book_name(m["book"])
    ch = int(m["ch"])
    chapters = kjv()[book]
    if not 1 <= ch <= len(chapters):
        raise ValueError(f"{book} has {len(chapters)} chapters, not {ch}")
    n = len(chapters[ch - 1])
    v1 = int(m["v1"]) if m["v1"] else 1
    v2 = int(m["v2"]) if m["v2"] else (v1 if m["v1"] else n)
    if not (1 <= v1 <= v2 <= n):
        raise ValueError(f"{book} {ch} has verses 1-{n}; {ref!r} is outside that")
    return book, ch, v1, v2


def canonical(book, ch, v1, v2):
    return f"{book} {ch}:{v1}" + (f"–{v2}" if v2 != v1 else "")


def verse_text(ref):
    """(canonical reference, exact KJV text) for a reference of up to 8 verses."""
    book, ch, v1, v2 = parse_ref(ref)
    if v2 - v1 + 1 > 8:
        raise ValueError(f"{ref!r} is {v2 - v1 + 1} verses; keep an episode to 8 verses or fewer")
    verses = kjv()[book][ch - 1][v1 - 1:v2]
    return canonical(book, ch, v1, v2), " ".join(v.strip() for v in verses)


# ---------------------------------------------------------------- episode files

def settings():
    return {"series": "One Verse, Real Life", "handle": "", "audience": "young adults",
            "tone": "warm, honest and practical; plain modern English; no preaching or guilt",
            "faith_context": "Christian", "words_per_second": 2.6, "format": "vertical",
            "background": ["#0F1B2D", "#2B3A55"], "accent": "#E8B04B", "text": "#FFFFFF",
            "music_volume": 0.18, "music_volume_no_voice": 0.45, **brand().get("scripture", {})}


LIMITS = {"hook": 70, "reflection": 420, "apply_item": 90, "closing": 90}


def validate_episode(ep, fix_verse=False):
    """Return a list of problems (empty = fine). With fix_verse, fills/refreshes the verse from the KJV."""
    problems = []
    for key in ("id", "reference", "hook", "reflection", "apply"):
        if not ep.get(key):
            problems.append(f'missing "{key}"')
    try:
        ref, text = verse_text(ep.get("reference", ""))
        if fix_verse:
            ep["reference_display"], ep["verse"] = ref, text
        elif ep.get("verse") != text:
            problems.append('"verse" does not match the KJV text for this reference; '
                            'don\'t edit the verse by hand (run `scripture.py check <id> --fix`)')
    except ValueError as e:
        problems.append(str(e))
    if len(ep.get("hook", "")) > LIMITS["hook"]:
        problems.append(f"hook is over {LIMITS['hook']} characters")
    if len(ep.get("reflection", "")) > LIMITS["reflection"]:
        problems.append(f"reflection is over {LIMITS['reflection']} characters")
    apply = ep.get("apply") or []
    if not isinstance(apply, list) or not 1 <= len(apply) <= 3:
        problems.append('"apply" must be a list of 1-3 short points')
    elif any(len(str(a)) > LIMITS["apply_item"] for a in apply):
        problems.append(f"an apply point is over {LIMITS['apply_item']} characters")
    if len(ep.get("closing", "")) > LIMITS["closing"]:
        problems.append(f"closing is over {LIMITS['closing']} characters")
    if ep.get("format", "vertical") not in ("vertical", "wide", "both"):
        problems.append('"format" must be vertical, wide or both')
    for key in ("voiceover", "music"):
        if ep.get(key) and not (SCRIPTURE / ep[key]).exists():
            problems.append(f'{key} file scripture/{ep[key]} not found')
    return problems


def load(eid):
    p = EPISODES / f"{eid}.json"
    if not p.exists():
        sys.exit(f"no episode {p.relative_to(ROOT)}")
    return json.loads(p.read_text())


def save(ep):
    EPISODES.mkdir(parents=True, exist_ok=True)
    (EPISODES / f"{ep['id']}.json").write_text(json.dumps(ep, indent=2, ensure_ascii=False) + "\n")


def next_id():
    nums = [int(m.group(1)) for p in EPISODES.glob("ep*.json") if (m := re.match(r"ep(\d+)", p.stem))]
    return f"ep{(max(nums) + 1 if nums else 1):03d}"


# ---------------------------------------------------------------- writing (model)

PROMPT = """You write short scripture videos for a channel called "{series}".
Audience: {audience}. Faith context: {faith_context}. Tone: {tone}.

The verse (King James Version, quoted exactly; do NOT rewrite or paraphrase it, it is shown as-is):
{reference}: "{verse}"
{theme}
Write the words that go around the verse:
- "hook": the opening line on screen, a real-life situation or question, max {hook} characters. No verse reference.
- "reflection": what the verse means for everyday life today, 2-3 short sentences, max {reflection} characters.
  Stay faithful to what the verse says in context; don't add doctrine it doesn't teach.
- "apply": 2-3 concrete things someone can do this week, each max {item} characters, starting with a verb.
- "closing": one short question that invites a comment, max {closing} characters.
- "caption": the social post caption, 1-2 sentences. "hashtags": 3-5.

Return ONLY one JSON object:
{{"hook": "", "reflection": "", "apply": ["", ""], "closing": "", "caption": "", "hashtags": []}}"""


def cmd_new(args):
    ref, text = verse_text(args.reference)
    eid = args.id or next_id()
    if (EPISODES / f"{eid}.json").exists():
        sys.exit(f"episode {eid} already exists")
    s = settings()
    prompt = PROMPT.format(series=s["series"], audience=s["audience"], faith_context=s["faith_context"],
                           tone=s["tone"], reference=ref, verse=text,
                           theme=f"Angle for this episode: {args.theme}\n" if args.theme else "",
                           hook=LIMITS["hook"], reflection=LIMITS["reflection"], item=LIMITS["apply_item"],
                           closing=LIMITS["closing"])

    def check(o):
        if not isinstance(o, dict):
            raise ValueError("expected a JSON object")
        ep = {"id": eid, "reference": args.reference, "hook": str(o.get("hook", "")).strip(),
              "reflection": str(o.get("reflection", "")).strip(),
              "apply": [str(a).strip() for a in (o.get("apply") or []) if str(a).strip()][:3],
              "closing": str(o.get("closing", "")).strip()}
        bad = [p for p in validate_episode(ep, fix_verse=True) if "voiceover" not in p and "music" not in p]
        if bad:
            raise ValueError("; ".join(bad))
        tags = o.get("hashtags") or []
        ep.update({"caption": str(o.get("caption", "")).strip(),
                   "hashtags": [str(t) for t in tags] if isinstance(tags, list) else str(tags).split()})
        return ep

    if env("PICKER", "claude-code") == "none":
        sys.exit("scripture new needs a model (PICKER is none); write scripture/episodes/<id>.json by hand instead")
    ep = ask_json(prompt, "object", check)
    ep.update({"format": s["format"], "voiceover": "", "music": "", "reviewed": False,
               "theme": args.theme or ""})
    ordered = {k: ep[k] for k in ("id", "reference", "reference_display", "verse", "hook", "reflection", "apply",
                                  "closing", "caption", "hashtags", "format", "voiceover", "music", "theme",
                                  "reviewed")}
    save(ordered)
    print(f"scripture/episodes/{eid}.json written. Read it, fix anything, then set \"reviewed\": true.\n")
    show(ordered)


def show(ep):
    print(f"[{ep['id']}] {ep.get('reference_display', ep['reference'])}  "
          f"({'reviewed' if ep.get('reviewed') else 'NOT REVIEWED'})\n")
    print(f"HOOK        {ep.get('hook', '')}")
    print(f"VERSE       \"{ep.get('verse', '')}\"")
    print(f"REFLECTION  {ep.get('reflection', '')}")
    for i, a in enumerate(ep.get("apply", []), 1):
        print(f"LIVE IT {i}   {a}")
    print(f"CLOSING     {ep.get('closing', '')}")
    print(f"CAPTION     {ep.get('caption', '')} {' '.join(ep.get('hashtags', []))}")


# ---------------------------------------------------------------- timing + render

def words(s):
    return len(str(s).split())


def plan_scenes(ep, s, vo_seconds=None):
    """Scene list with frame counts. Reading-speed based; with a voiceover, stretched to its length."""
    wps = float(s["words_per_second"])
    secs = [("hook", max(2.2, words(ep["hook"]) / wps + 0.8)),
            ("verse", max(4.0, words(ep["verse"]) / (wps * 0.85) + 2.0)),   # slower: it's read with care
            ("reflection", max(3.5, words(ep["reflection"]) / wps + 1.2)),
            ("apply", sum(max(2.2, words(a) / wps + 0.9) for a in ep["apply"]) + 0.8),
            ("end", 3.0)]
    total = sum(t for _, t in secs)
    if vo_seconds:
        scale = (vo_seconds + 0.6) / total
        secs = [(k, t * scale) for k, t in secs]
    return [{"type": k, "frames": max(15, round(t * FPS))} for k, t in secs]


def browser():
    """A Chrome/Chromium for Remotion: REMOTION_BROWSER, else let Remotion download its own."""
    return env("REMOTION_BROWSER") or ""


def build_props(ep, s, fmt, draft):
    vo = SCRIPTURE / ep["voiceover"] if ep.get("voiceover") else None
    music = SCRIPTURE / ep["music"] if ep.get("music") else None
    vo_seconds = duration(vo) if vo and has_audio(vo) else None
    scenes = plan_scenes(ep, s, vo_seconds)
    # audio is served to the browser from remotion/public/jobs/<id>/
    pub = REMOTION / "public" / "jobs" / ep["id"]
    shutil.rmtree(pub, ignore_errors=True)
    pub.mkdir(parents=True)
    rel = {}
    for key, src in (("voiceover", vo), ("music", music)):
        if src:
            shutil.copy(src, pub / f"{key}{src.suffix}")
            rel[key] = f"jobs/{ep['id']}/{key}{src.suffix}"
    w, h = (1080, 1920) if fmt == "vertical" else (1920, 1080)
    apply_frames = scenes[3]["frames"]
    weights = [max(2.2, words(a) / float(s["words_per_second"]) + 0.9) for a in ep["apply"]]
    return {
        "width": w, "height": h, "fps": FPS, "draft": bool(draft),
        "brand": {"series": s["series"], "handle": s["handle"], "background": s["background"],
                  "accent": s["accent"], "text": s["text"]},
        "hook": ep["hook"], "reference": ep.get("reference_display") or verse_text(ep["reference"])[0],
        "verse": ep["verse"], "reflection": ep["reflection"], "closing": ep.get("closing", ""),
        "apply": ep["apply"],
        "applyStarts": [round((apply_frames - 0.8 * FPS) * sum(weights[:i]) / sum(weights)) for i in range(len(weights))],
        "scenes": scenes,
        "voiceover": rel.get("voiceover", ""), "music": rel.get("music", ""),
        "musicVolume": float(s["music_volume"] if rel.get("voiceover") else s["music_volume_no_voice"]),
    }


def render_one(ep, fmt, draft):
    s = settings()
    props = build_props(ep, s, fmt, draft)
    od = ROOT / "out" / "scripture" / ep["id"]
    od.mkdir(parents=True, exist_ok=True)
    wd = ROOT / "work" / f"scripture-{ep['id']}"
    wd.mkdir(parents=True, exist_ok=True)
    props_path = wd / f"props_{fmt}.json"
    props_path.write_text(json.dumps(props, indent=2, ensure_ascii=False))
    name = f"{ep['id']}_{fmt}{'_draft' if draft else ''}.mp4"
    raw = wd / f"raw_{name}"
    cmd = ["npx", "remotion", "render", "src/index.ts", "ScriptureEpisode", str(raw), f"--props={props_path}",
           "--log=error"]
    if draft:
        cmd += ["--scale=0.5"]
    if browser():
        cmd += [f"--browser-executable={browser()}"]
    subprocess.run(cmd, cwd=REMOTION, check=True)
    final = od / name
    # loudness pass (video copied); a silent episode just gets copied
    if has_audio(raw):
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-c:v", "copy",
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(final)], check=True)
        raw.unlink()
    else:
        raw.replace(final)
    shutil.rmtree(REMOTION / "public" / "jobs" / ep["id"], ignore_errors=True)
    secs = sum(sc["frames"] for sc in props["scenes"]) / FPS
    log(f"scripture-{ep['id']}", f"render: {final.relative_to(ROOT)} ({secs:.1f}s, {fmt}{', draft' if draft else ''})")
    (od / "post.md").write_text(
        f"# {ep['id']}: {props['reference']}\n\n{ep.get('caption', '')}\n\n{' '.join(ep.get('hashtags', []))}\n\n"
        f"> \"{ep['verse']}\" ({props['reference']}, KJV)\n")
    return final


def cmd_render(args):
    ids = sorted(p.stem for p in EPISODES.glob("*.json")) if args.all else args.ids
    if not ids:
        sys.exit("nothing to render: give episode ids or --all")
    if not (REMOTION / "node_modules").exists():
        sys.exit("remotion/node_modules missing: run `npm ci` in remotion/ (setup.sh does this)")
    done, skipped = 0, []
    for eid in ids:
        ep = load(eid)
        problems = validate_episode(ep)
        if problems:
            skipped.append(f"{eid}: " + "; ".join(problems))
            continue
        if not ep.get("reviewed") and not args.draft:
            skipped.append(f"{eid}: not reviewed yet (set \"reviewed\": true after reading it, or use --draft)")
            continue
        fmt = args.format or ep.get("format", "vertical")
        for f in (("vertical", "wide") if fmt == "both" else (fmt,)):
            if args.all and not args.force and (ROOT / "out" / "scripture" / eid / f"{eid}_{f}.mp4").exists() \
                    and not args.draft:
                continue  # --all renders only what's missing; --force re-renders everything
            render_one(ep, f, args.draft)
            done += 1
    for msg in skipped:
        print(f"skipped {msg}", file=sys.stderr)
    print(f"rendered {done} video(s); skipped {len(skipped)} episode(s)")
    if skipped and not done:
        sys.exit(1)


def cmd_check(args):
    ids = args.ids or sorted(p.stem for p in EPISODES.glob("*.json"))
    bad = 0
    for eid in ids:
        ep = load(eid)
        if args.fix:
            validate_episode(ep, fix_verse=True)
            save(ep)
        problems = validate_episode(ep)
        state = "ok" if not problems else "PROBLEMS"
        print(f"{eid}: {state}{'' if ep.get('reviewed') else ' (not reviewed)'}")
        for p in problems:
            print(f"   - {p}")
        bad += bool(problems)
    sys.exit(1 if bad else 0)


def main():
    ap = argparse.ArgumentParser(description="Scripture mode: animated verse episodes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("new", help="draft a new episode (the model writes the words around the verse)")
    n.add_argument("reference")
    n.add_argument("--theme", default="")
    n.add_argument("--id", default="")
    sh = sub.add_parser("show", help="print an episode as a readable script")
    sh.add_argument("id")
    c = sub.add_parser("check", help="validate episodes (verse matches KJV, lengths, files)")
    c.add_argument("ids", nargs="*")
    c.add_argument("--fix", action="store_true", help="refresh the verse text from the KJV")
    r = sub.add_parser("render", help="render episodes with Remotion")
    r.add_argument("ids", nargs="*")
    r.add_argument("--all", action="store_true")
    r.add_argument("--draft", action="store_true", help="half resolution, DRAFT stamp, allowed before review")
    r.add_argument("--format", choices=("vertical", "wide", "both"))
    r.add_argument("--force", action="store_true", help="with --all, re-render episodes that already have output")
    args = ap.parse_args()
    if args.cmd == "new":
        cmd_new(args)
    elif args.cmd == "show":
        show(load(args.id))
    elif args.cmd == "check":
        cmd_check(args)
    else:
        cmd_render(args)


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    main()
