"""Step 2: transcribe work/<job>/tight.mp4 -> transcript.srt + words.json

Usage: python3 scripts/transcribe.py <job-id> [--force]
STT=local uses faster-whisper. STT=groq uses Groq's hosted Whisper (needs GROQ_API_KEY).
"""
import json
import subprocess
import sys

from common import env, job_dir, log, write_srt


def local(media):
    """WHISPER_BATCH > 0 uses faster-whisper's batched pipeline: same model, several chunks decoded
    at once, typically 2-4x faster. WHISPER_LANGUAGE (e.g. en) skips language detection."""
    from faster_whisper import WhisperModel
    device = env("WHISPER_DEVICE", "auto")
    model = WhisperModel(env("WHISPER_MODEL", "small"), device=device,
                         compute_type="int8" if device == "cpu" else "default",
                         cpu_threads=int(env("WHISPER_THREADS", 0)))
    opts = {"word_timestamps": True, "vad_filter": True, "language": env("WHISPER_LANGUAGE") or None}
    batch = int(env("WHISPER_BATCH", 8))
    try:
        from faster_whisper import BatchedInferencePipeline  # faster-whisper >= 1.1
    except ImportError:
        batch = 0
    if batch > 0:
        segs, _ = BatchedInferencePipeline(model=model).transcribe(str(media), batch_size=batch, **opts)
    else:
        segs, _ = model.transcribe(str(media), **opts)
    segments, words = [], []
    for s in segs:
        segments.append({"start": s.start, "end": s.end, "text": s.text.strip()})
        for w in s.words or []:
            words.append({"start": w.start, "end": w.end, "word": w.word.strip()})
    return segments, words


def groq(media, wd):
    """Groq caps uploads at 25 MB, so long recordings are sent in 20-minute chunks
    and the timestamps are shifted back onto the full timeline."""
    import requests
    from common import duration
    key = env("GROQ_API_KEY")
    if not key:
        sys.exit("GROQ_API_KEY missing in .env")
    chunk_dir = wd / "audio_chunks"
    chunk_dir.mkdir(exist_ok=True)
    for old in chunk_dir.glob("*.mp3"):
        old.unlink()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(media),
                    "-vn", "-ac", "1", "-ar", "16000", "-b:a", "64k",
                    "-f", "segment", "-segment_time", "1200", "-reset_timestamps", "1",
                    str(chunk_dir / "part_%03d.mp3")], check=True)
    segments, words, offset = [], [], 0.0
    for part in sorted(chunk_dir.glob("part_*.mp3")):
        with open(part, "rb") as fh:
            r = requests.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {key}"},
                files={"file": (part.name, fh, "audio/mpeg")},
                data=[("model", env("GROQ_STT_MODEL", "whisper-large-v3-turbo")),
                      ("response_format", "verbose_json"),
                      ("timestamp_granularities[]", "segment"),
                      ("timestamp_granularities[]", "word")],
                timeout=600)
        r.raise_for_status()
        d = r.json()
        segments += [{"start": s["start"] + offset, "end": s["end"] + offset, "text": s["text"].strip()}
                     for s in d.get("segments", [])]
        words += [{"start": w["start"] + offset, "end": w["end"] + offset, "word": w["word"].strip()}
                  for w in d.get("words", [])]
        offset += duration(part)
    return segments, words


def main():
    job = sys.argv[1]
    force = "--force" in sys.argv
    wd = job_dir(job)
    media = wd / "tight.mp4"
    if (wd / "transcript.srt").exists() and not force:
        log(job, "transcribe: transcript.srt exists, skipping (use --force to redo)")
        return
    stt = env("STT", "local")
    log(job, f"transcribe: STT={stt}" + (f" batch={env('WHISPER_BATCH', 8)}" if stt != "groq" else ""))
    segments, words = groq(media, wd) if stt == "groq" else local(media)
    if not segments:
        sys.exit("transcribe: no speech detected")
    write_srt(segments, wd / "transcript.srt")
    (wd / "words.json").write_text(json.dumps(words, indent=1))
    log(job, f"transcribe: {len(segments)} segments, {len(words)} words")


if __name__ == "__main__":
    main()
