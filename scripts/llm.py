"""One place that talks to a model. Every script calls ask(prompt).

PICKER=claude-code  uses your Claude subscription through the logged-in `claude` CLI (no API key)
PICKER=claude       Anthropic API, billed per token (needs ANTHROPIC_API_KEY)
PICKER=gemini       Google Gemini API (needs GEMINI_API_KEY)
"""
import json
import os
import re
import shutil
import subprocess

from common import env


def ask(prompt):
    picker = env("PICKER", "claude-code")
    if picker == "claude-code":
        if not shutil.which("claude"):
            raise RuntimeError("`claude` CLI not found. Install Claude Code and run `claude` once to log in")
        child_env = dict(os.environ)
        child_env.pop("ANTHROPIC_API_KEY", None)  # make the CLI use the subscription login, not API billing
        r = subprocess.run(
            ["claude", "-p", "Follow the instructions in the input exactly. Do not use any tools. "
                             "Reply with the requested JSON only.", "--output-format", "text"],
            input=prompt, capture_output=True, text=True, timeout=1800, env=child_env)
        if r.returncode != 0:
            raise RuntimeError(f"claude -p failed: {(r.stderr or r.stdout)[-400:]}")
        return r.stdout
    if picker == "claude":
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model=env("CLAUDE_MODEL", "claude-sonnet-5-5"), max_tokens=8000,
            messages=[{"role": "user", "content": prompt}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    if picker == "gemini":
        from google import genai
        r = genai.Client().models.generate_content(
            model=env("GEMINI_MODEL", "gemini-2.5-flash"), contents=prompt,
            config={"response_mime_type": "application/json"})
        return r.text
    raise ValueError(f"unknown PICKER={picker}")


FENCE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.S)


def iter_json(text, kind="array"):
    """Yield every complete JSON array/object in a model reply, in order.

    Looks inside ```json fences first, then the whole text, and decodes one value at a time
    (json.JSONDecoder.raw_decode), so prose, notes or stray brackets around the JSON don't break it."""
    want, opener = (list, "[") if kind == "array" else (dict, "{")
    dec = json.JSONDecoder()
    for chunk in [m.group(1) for m in FENCE.finditer(text or "")] + [text or ""]:
        i = chunk.find(opener)
        while i != -1:
            try:
                obj, end = dec.raw_decode(chunk, i)
                if isinstance(obj, want):
                    yield obj
                    i = chunk.find(opener, end)
                    continue
            except json.JSONDecodeError:
                pass
            i = chunk.find(opener, i + 1)


def extract_json(text, kind="array"):
    """The first complete JSON array/object in a model reply. Raises ValueError if there is none."""
    for obj in iter_json(text, kind):
        return obj
    raise ValueError(f"no valid JSON {kind} in model reply")


def ask_json(prompt, kind, validate, raw_path=None, attempts=2):
    """ask() + validate() on each JSON value in the reply, retrying once with the error fed back.

    validate(obj) must return the cleaned value or raise ValueError/KeyError/TypeError.
    Every raw reply is appended to raw_path (if given) for debugging."""
    last, p = None, prompt
    for n in range(1, attempts + 1):
        raw = ask(p)
        if raw_path:
            with open(raw_path, "a") as fh:
                fh.write(f"===== attempt {n} =====\n{raw}\n")
        last = ValueError(f"no valid JSON {kind} in model reply")
        for obj in iter_json(raw, kind):  # first candidate that validates wins
            try:
                return validate(obj)
            except (ValueError, KeyError, TypeError) as e:
                last = e
        p = (prompt + f"\n\nYour previous reply could not be used: {last}. "
                      f"Reply again with the JSON {kind} only, exactly in the format above.")
    raise ValueError(f"model reply unusable after {attempts} attempts: {last}")
