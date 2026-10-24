# tests/

| File | What it checks | Time | Needs |
|---|---|---|---|
| `test_units.py` | the logic with no rendering: JSON parsing of model replies, plan/edit/clip validation, time and SRT parsing, pause cuts, shot splitting, crop maths, look filters, hook placement, scripture references and KJV lookup, episode checks, scene timing | under a second | Python only |
| `smoke.sh` | real renders with FFmpeg and no model: a generated test video through clip mode, event mode (final + draft) and montage mode, then checks each output's length, size and audio/video sync | ~2 min | FFmpeg |

```bash
python3 -m unittest discover -s tests -v     # unit tests
tests/smoke.sh                               # end-to-end render test
```

CI (`.github/workflows/ci.yml`) runs both on every pull request, then type-checks the Remotion template and renders a draft scripture episode. `main` only accepts changes that pass.

## Adding a test

- **New logic** (parsing, validation, timing): add a test to `test_units.py`. Use plain `unittest`, standard library only, and `unittest.mock` to fake the model.
- **New render output**: add the step to `smoke.sh`, plus a `check(...)` line for its length and size.
- **Model calls:** never call a real model in tests. Patch `llm.ask` or put a fake `claude` script on `PATH`.
