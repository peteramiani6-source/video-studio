"""Voiceover for scripture episodes: an AI narrator and character voice, timed scene by scene.

Usage (normally through scripts/scripture.sh):
  python3 scripts/voice.py <id>            generate scripture/audio/<id>_ai.wav and set it as the episode's voiceover
  python3 scripts/voice.py <id> --script   print the lines to read, for recording your own voiceover
  python3 scripts/voice.py --voices        list the voices

How it works: every line (skit lines in the character's voice; hook, verse, reflection, "live it" points
and closing question in the narrator's voice) is spoken separately. Each scene then lasts as long as its
speech, and the lines are placed at exact frame positions, so the verse appears while it is being read.
The timing goes next to the audio as <id>_ai.json, with a fingerprint of the script: if the words change
later, `check` and `render` say the voiceover is out of date instead of rendering it out of sync.

Speech engine: TTS in config/models.env. kokoro = Kokoro-82M (Apache 2.0), runs on the CPU, free, offline
after setup.sh downloads it (~120 MB into models/kokoro/). The verse is read exactly as the KJV has it;
only the reference is turned into words ("Philippians chapter 4, verses 6 to 7").

The character's mouth follows the loudness of the voiceover during talking beats (scripture.py does
this at render time, so it works for your own recordings too).
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys

try:
    import numpy as np  # only needed to generate a voice or follow it with the mouth
except ImportError:  # pragma: no cover
    np = None

from common import ROOT, env, log

SCRIPTURE = ROOT / "scripture"
MODELS = ROOT / "models" / "kokoro"
MODEL_FILES = ("kokoro-v1.0.int8.onnx", "voices-v1.0.bin")
FPS = 30
SR = 24000

# seconds of air around each line (lead before, tail after)
PAD = {"skit": (0.15, 0.3), "hook": (0.3, 0.5), "verse": (0.7, 1.3), "reflection": (0.4, 0.6),
       "apply": (0.3, 0.8), "end": (0.5, 1.6)}
GAP = 0.35  # between lines inside a scene


def tts_settings():
    return {"engine": env("TTS", "kokoro"), "narrator": env("TTS_NARRATOR", "am_michael"),
            "character": env("TTS_CHARACTER", "am_puck"), "speed": float(env("TTS_SPEED", 1.0)),
            "verse_speed": float(env("TTS_VERSE_SPEED", 0.9))}


# ---------------------------------------------------------------- the script

ORD = {"1": "First", "2": "Second", "3": "Third"}


def spoken_reference(display):
    """'Philippians 4:6–7' -> 'Philippians chapter 4, verses 6 to 7'. Only for speech; the screen keeps the reference."""
    m = re.match(r"^(?:(\d)\s+)?(.+?)\s+(\d+)(?::(\d+)(?:\s*[-–—]\s*(\d+))?)?$", display.strip())
    if not m:
        return display
    num, book, ch, v1, v2 = m.groups()
    book = f"{ORD[num]} {book}" if num else book
    if book == "Psalms":
        book = "Psalm"
    if not v1:
        return f"{book} {ch}" if book == "Psalm" else f"{book} chapter {ch}"
    if v2:
        return f"{book} chapter {ch}, verses {v1} to {v2}"
    return f"{book} chapter {ch}, verse {v1}"


def say_text(beat):
    """What the character says out loud in a skit beat: `say`, else the caption if the beat is a talking one."""
    t = str(beat.get("say") or (beat.get("caption", "") if beat.get("talk") else "")).strip()
    if t.isupper():  # ALL-CAPS captions would be read as letters
        t = t.capitalize()
    return t.replace("...", "…")


def lines(ep, s):
    """Every spoken line, in order: dicts with scene type, skit index, voice and text."""
    out = []
    skit = ep.get("skit") or []
    for i, b in enumerate(skit):
        out.append({"scene": "skit", "index": i, "who": "character", "text": say_text(b)})
    if not skit:
        out.append({"scene": "hook", "who": "narrator", "text": ep["hook"]})
    ref = ep.get("reference_display") or ep["reference"]
    out.append({"scene": "verse", "who": "narrator", "text": spoken_reference(ref) + ".", "part": "reference"})
    out.append({"scene": "verse", "who": "narrator", "text": ep["verse"], "part": "verse", "slow": True})
    out.append({"scene": "reflection", "who": "narrator", "text": ep["reflection"]})
    out.append({"scene": "apply", "who": "narrator", "text": "Live it this week.", "part": "title"})
    for i, a in enumerate(ep["apply"]):
        out.append({"scene": "apply", "who": "narrator", "text": a.rstrip(".") + ".", "part": "item", "item": i})
    if ep.get("closing"):
        out.append({"scene": "end", "who": "narrator", "text": ep["closing"]})
    return out


def fingerprint(ep, s=None):
    """Changes whenever anything that affects the voiceover or its timing changes."""
    s = s or tts_settings()
    data = {"lines": [(ln["who"], ln["text"]) for ln in lines(ep, s)],
            "beats": [float(b.get("seconds", 2)) for b in ep.get("skit") or []],
            "voices": [s["narrator"], s["character"], s["speed"], s["verse_speed"]], "v": 1}
    return hashlib.sha1(json.dumps(data, ensure_ascii=False).encode()).hexdigest()[:16]


def timing_path(voiceover):
    return (SCRIPTURE / voiceover).with_suffix(".json")


def timing_for(ep):
    """The saved timing for the episode's voiceover, or None for your own recording.
    Raises ValueError if it was generated from a different script (out of date)."""
    if not ep.get("voiceover"):
        return None
    p = timing_path(ep["voiceover"])
    if not p.exists():
        return None
    t = json.loads(p.read_text())
    if t.get("fingerprint") != fingerprint(ep):
        raise ValueError(f"voiceover scripture/{ep['voiceover']} is out of date with the script "
                         f"(words, skit timing or voices changed): run `scripts/scripture.sh voice {ep['id']}`")
    return t


# ---------------------------------------------------------------- speech

class Kokoro:
    def __init__(self):
        missing = [f for f in MODEL_FILES if not (MODELS / f).exists()]
        if missing:
            sys.exit(f"Kokoro model files missing in models/kokoro/ ({', '.join(missing)}): run ./setup.sh")
        try:
            from kokoro_onnx import Kokoro as K
        except ImportError:
            sys.exit("kokoro-onnx is not installed: run ./setup.sh (or .venv/bin/pip install kokoro-onnx soundfile)")
        self.k = K(str(MODELS / MODEL_FILES[0]), str(MODELS / MODEL_FILES[1]))

    def voices(self):
        return sorted(self.k.get_voices())

    def say(self, text, voice, speed):
        lang = "en-gb" if voice.startswith("b") else "en-us"
        audio, sr = self.k.create(text, voice=voice, speed=speed, lang=lang)
        audio = np.asarray(audio, dtype=np.float32)
        if sr != SR:
            raise RuntimeError(f"unexpected sample rate {sr}")
        return trim(audio)


def trim(a, thresh=0.01):
    """Cut leading/trailing silence so the padding is ours, not the engine's."""
    idx = np.where(np.abs(a) > thresh)[0]
    if not len(idx):
        return a[:0]
    return a[max(0, idx[0] - 240): idx[-1] + 480]


def engine():
    name = tts_settings()["engine"]
    if name == "kokoro":
        return Kokoro()
    sys.exit(f"TTS={name}: voice generation needs TTS=kokoro in config/models.env "
             "(or record your own voiceover: scripts/scripture.sh voice <id> --script)")


def synth_cached(eng, text, voice, speed, cache):
    key = hashlib.sha1(f"{voice}|{speed}|{text}".encode()).hexdigest()[:16]
    f = cache / f"{key}.npy"
    if f.exists():
        return np.load(f)
    a = eng.say(text, voice, speed)
    np.save(f, a)
    return a


# ---------------------------------------------------------------- timing + mix

def frames(sec):
    return max(1, round(sec * FPS))


def layout(ep, clips):
    """Scene lengths (frames) and where each line starts (frame), from the spoken lengths.
    clips: list parallel to lines(ep) with seconds of speech each."""
    ls = lines(ep, tts_settings())
    skit = ep.get("skit") or []
    order = [("skit", i) for i in range(len(skit))] or [("hook", None)]
    order += [("verse", None), ("reflection", None), ("apply", None), ("end", None)]
    scenes, starts, extra = [], [None] * len(ls), {"apply_starts": [], "verse_span": None}
    t0 = 0  # frame where the current scene starts
    for kind, idx in order:
        mine = [j for j, ln in enumerate(ls) if ln["scene"] == kind and ln.get("index") == idx]
        lead, tail = PAD[kind]
        t = lead
        for n, j in enumerate(mine):
            if clips[j] <= 0:
                continue
            starts[j] = t0 + frames(t)
            if ls[j].get("part") == "verse":
                extra["verse_span"] = [frames(t), frames(t + clips[j])]
            if ls[j].get("part") == "item":
                extra["apply_starts"].append(frames(t))
            t += clips[j] + (GAP if n < len(mine) - 1 else 0)
        length = t + tail
        if kind == "skit":
            length = max(length, float(skit[idx].get("seconds", 2)))  # silent beats keep their written length
        if kind == "end":
            length = max(length, 3.5 if skit else 3.0)
        n = frames(length)
        sc = {"type": kind, "frames": max(15, n)}
        if idx is not None:
            sc["index"] = idx
        scenes.append(sc)
        t0 += sc["frames"]
    return scenes, starts, extra


def mix(audios, starts, total_frames):
    out = np.zeros(int(total_frames / FPS * SR) + SR, dtype=np.float32)
    for a, st in zip(audios, starts):
        if st is None or not len(a):
            continue
        i = int(st / FPS * SR)
        out[i:i + len(a)] += a[: len(out) - i]
    peak = float(np.max(np.abs(out))) or 1.0
    return out * min(1.0, 0.89 / peak)


def write_wav(path, audio):
    import wave
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def generate(ep):
    s = tts_settings()
    eng = engine()
    cache = ROOT / "work" / f"scripture-{ep['id']}" / "voice"
    cache.mkdir(parents=True, exist_ok=True)
    ls = lines(ep, s)
    audios = []
    for ln in ls:
        if not ln["text"]:
            audios.append(np.zeros(0, dtype=np.float32))
            continue
        voice = s["character"] if ln["who"] == "character" else s["narrator"]
        speed = s["verse_speed"] if ln.get("slow") else s["speed"]
        print(f"  {ln['who']:9} {ln['text'][:70]}{'…' if len(ln['text']) > 70 else ''}")
        audios.append(synth_cached(eng, ln["text"], voice, speed, cache))
    clips = [len(a) / SR for a in audios]
    scenes, starts, extra = layout(ep, clips)
    total = sum(sc["frames"] for sc in scenes)
    (SCRIPTURE / "audio").mkdir(parents=True, exist_ok=True)
    rel = f"audio/{ep['id']}_ai.wav"
    write_wav(SCRIPTURE / rel, mix(audios, starts, total))
    timing = {"fingerprint": fingerprint(ep, s), "voices": {"narrator": s["narrator"], "character": s["character"]},
              "scenes": scenes, "verse_span": extra["verse_span"], "apply_starts": extra["apply_starts"],
              "seconds": round(total / FPS, 2)}
    timing_path(rel).write_text(json.dumps(timing, indent=2) + "\n")
    return rel, timing


# ---------------------------------------------------------------- lip sync

def decode(path, sr=16000):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr


def mouth_levels(samples, sr, total_frames):
    """Per video frame: 0 = closed, 1 = half open, 2 = open, from the loudness of the speech."""
    hop = sr / FPS
    rms = np.array([np.sqrt(np.mean(samples[int(i * hop): int((i + 1) * hop)] ** 2) or 0.0)
                    if int(i * hop) < len(samples) else 0.0 for i in range(total_frames)])
    voiced = rms[rms > 0.005]
    ref = float(np.percentile(voiced, 90)) if len(voiced) else 1.0
    lv = rms / (ref or 1.0)
    out = np.where(lv > 0.5, 2, np.where(lv > 0.15, 1, 0))
    # no single-frame flicker
    for i in range(1, total_frames - 1):
        if out[i] != out[i - 1] and out[i] != out[i + 1]:
            out[i] = out[i - 1]
    return out


def mouth_track(path, scenes, skit):
    """Levels for the whole video, non-zero only during talking skit beats (narration never moves the mouth)."""
    total = sum(sc["frames"] for sc in scenes)
    samples, sr = decode(path)
    lv = mouth_levels(samples, sr, total)
    track = np.zeros(total, dtype=int)
    t = 0
    for sc in scenes:
        if sc["type"] == "skit" and skit[sc["index"]].get("talk"):
            track[t:t + sc["frames"]] = lv[t:t + sc["frames"]]
        t += sc["frames"]
    return [int(x) for x in track]


# ---------------------------------------------------------------- CLI

def recording_script(ep):
    s = tts_settings()
    print(f"[{ep['id']}] Record in one take, in this order. Leave a short breath between lines.\n")
    for ln in lines(ep, s):
        if not ln["text"]:
            continue
        who = "CHARACTER" if ln["who"] == "character" else "NARRATOR "
        print(f"{who}  {ln['text']}")
    print(f"\nSave it as scripture/audio/{ep['id']}.mp3 and set \"voiceover\": \"audio/{ep['id']}.mp3\".")
    print("Your recording sets the video length; scenes stretch to fit it and the mouth follows your voice.")


def main():
    sys.path.insert(0, str(ROOT / "scripts"))
    import scripture
    ap = argparse.ArgumentParser(description="AI voiceover for scripture episodes")
    ap.add_argument("id", nargs="?")
    ap.add_argument("--script", action="store_true", help="print the lines to record your own voiceover")
    ap.add_argument("--voices", action="store_true", help="list the available voices")
    a = ap.parse_args()
    if a.voices:
        print("\n".join(engine().voices()))
        print("\nam_/af_ = American male/female, bm_/bf_ = British. Set TTS_NARRATOR / TTS_CHARACTER in config/models.env.")
        return
    if not a.id:
        ap.error("give an episode id")
    ep = scripture.load(a.id)
    problems = [p for p in scripture.validate_episode(ep) if "voiceover" not in p]
    if problems:
        sys.exit("fix the episode first:\n  - " + "\n  - ".join(problems))
    if a.script:
        return recording_script(ep)
    s = tts_settings()
    print(f"[{a.id}] narrator {s['narrator']}, character {s['character']}")
    rel, timing = generate(ep)
    ep["voiceover"] = rel
    scripture.save(ep)
    log(f"scripture-{a.id}", f"voice: scripture/{rel} ({timing['seconds']}s, {s['narrator']} + {s['character']})")
    print(f"\nscripture/{rel} written ({timing['seconds']}s) and set as the voiceover.")
    if timing["seconds"] > scripture.MAX_SHORT:
        print(f"! {timing['seconds']:.0f}s is over {scripture.MAX_SHORT:.0f}s: shorten the reflection, an apply point or the skit")
    print(f"Render it: scripts/scripture.sh render {a.id} --draft")


if __name__ == "__main__":
    main()
