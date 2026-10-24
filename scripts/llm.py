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


def extract_json(text, kind="array"):
    pattern = r"\[.*\]" if kind == "array" else r"\{.*\}"
    m = re.search(pattern, text, re.S)
    if not m:
        raise ValueError(f"no JSON {kind} in model reply")
    return json.loads(m.group(0))
