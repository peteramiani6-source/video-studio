"""Fast unit tests for the logic that doesn't need FFmpeg or a model. Standard library only.

Run: python3 -m unittest discover -s tests -v
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import llm  # noqa: E402
from common import clean_range, parse_srt, parse_time, write_srt  # noqa: E402
from pick_clips import snap, validate_clips  # noqa: E402
from plan_event import clean_ranges, validate_plan  # noqa: E402
from render import keep_ranges, remap  # noqa: E402


class ExtractJson(unittest.TestCase):
    def test_fenced_object_with_braces_in_trailing_note(self):
        text = 'Here you go:\n```json\n{"segments": [{"start": 1, "end": 2}]}\n```\nNote: skipped {the} intro.'
        self.assertEqual(llm.extract_json(text, "object"), {"segments": [{"start": 1, "end": 2}]})

    def test_array_followed_by_bracketed_aside(self):
        self.assertEqual(llm.extract_json('[{"start": 1, "end": 30}]\n(times [approx])'),
                         [{"start": 1, "end": 30}])

    def test_skips_brackets_in_prose_before_the_json(self):
        self.assertEqual(llm.extract_json('I picked [3] clips: [{"start": 5, "end": 40}]'), [3])
        self.assertEqual(llm.extract_json('Clips (see [note]): [{"start": 5, "end": 40}]'),
                         [{"start": 5, "end": 40}])

    def test_object_kind_ignores_arrays(self):
        self.assertEqual(llm.extract_json('[1, 2] then {"a": 1}', "object"), {"a": 1})

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            llm.extract_json("Sorry, I can't help with that.", "object")
        with self.assertRaises(ValueError):
            llm.extract_json('{"broken": ', "object")


class AskJsonRetry(unittest.TestCase):
    def test_retries_once_with_error_then_succeeds(self):
        replies = iter(["no json here", '[{"start": 1, "end": 40}]'])
        prompts = []
        with mock.patch.object(llm, "ask", side_effect=lambda p: prompts.append(p) or next(replies)):
            out = llm.ask_json("PROMPT", "array", lambda x: x)
        self.assertEqual(out, [{"start": 1, "end": 40}])
        self.assertEqual(len(prompts), 2)
        self.assertIn("could not be used", prompts[1])

    def test_picks_the_candidate_that_validates(self):
        def needs_clips(x):
            if not all(isinstance(c, dict) for c in x):
                raise ValueError("not clips")
            return x

        with mock.patch.object(llm, "ask", return_value='I picked [3] clips: [{"start": 5, "end": 40}]') as ask:
            self.assertEqual(llm.ask_json("P", "array", needs_clips), [{"start": 5, "end": 40}])
        self.assertEqual(ask.call_count, 1)

    def test_gives_up_after_two_attempts_and_logs_raw(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(llm, "ask", return_value="nope"):
            raw = Path(d) / "raw.txt"
            with self.assertRaises(ValueError):
                llm.ask_json("P", "object", lambda x: x, raw)
            self.assertEqual(raw.read_text().count("===== attempt"), 2)


class Times(unittest.TestCase):
    def test_parse_time_forms(self):
        self.assertEqual(parse_time(95), 95.0)
        self.assertEqual(parse_time("95"), 95.0)
        self.assertEqual(parse_time("1:35"), 95.0)
        self.assertEqual(parse_time("01:01:35"), 3695.0)
        self.assertAlmostEqual(parse_time("00:01:35,500"), 95.5)

    def test_parse_time_rejects_junk(self):
        for bad in ("soon", "1:2:3:4", True, ""):
            with self.assertRaises((ValueError, TypeError)):
                parse_time(bad)

    def test_clean_range(self):
        self.assertEqual(clean_range({"start": "0:10", "end": 25}, total=20)["end"], 20.0)
        self.assertIsNone(clean_range({"start": 5}))
        self.assertIsNone(clean_range({"start": 9, "end": 3}))
        self.assertIsNone(clean_range("not a dict"))

    def test_srt_round_trip(self):
        cues = [{"start": 1.25, "end": 3.5, "text": "Hello there"}, {"start": 3661.0, "end": 3662.004, "text": "Hi"}]
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.srt"
            write_srt(cues, p)
            back = parse_srt(p.read_text())
        self.assertEqual([c["text"] for c in back], ["Hello there", "Hi"])
        self.assertAlmostEqual(back[1]["start"], 3661.0)
        self.assertAlmostEqual(back[1]["end"], 3662.004)

    def test_srt_dot_milliseconds(self):
        self.assertAlmostEqual(parse_srt("1\n00:00:01.500 --> 00:00:02.000\nx\n")[0]["start"], 1.5)


class Plans(unittest.TestCase):
    def test_validate_plan_coerces_and_drops(self):
        plan = validate_plan({"segments": [{"start": "0:05", "end": "0:30", "label": "Talk"},
                                           {"start": 40},                       # no end: dropped
                                           {"start": 50, "end": 45}],           # backwards: dropped
                              "highlights": [{"start": 6, "end": 12}, {"oops": 1}],
                              "social_clips": [{"start": 5, "end": 40, "title": 7}]}, total=100)
        self.assertEqual(len(plan["segments"]), 1)
        self.assertEqual(plan["segments"][0]["start"], 5.0)
        self.assertEqual(plan["segments"][0]["speaker"], "")
        self.assertEqual(len(plan["highlights"]), 1)
        self.assertEqual(plan["social_clips"][0]["title"], "7")
        self.assertEqual(plan["youtube"], {"title": "", "description": ""})

    def test_validate_plan_needs_a_segment(self):
        with self.assertRaises(ValueError):
            validate_plan({"segments": [{"start": "x", "end": "y"}]}, total=100)
        with self.assertRaises(ValueError):
            validate_plan([], total=100)

    def test_clean_ranges_merges_same_label_and_butts_different(self):
        out = clean_ranges([{"start": 10, "end": 20, "label": "A"}, {"start": 19, "end": 30, "label": "A"},
                            {"start": 29, "end": 40, "label": "B"}], total=100, min_len=3, pad=0)
        self.assertEqual([(o["start"], o["end"], o["label"]) for o in out], [(10, 30, "A"), (30, 40, "B")])


class Clips(unittest.TestCase):
    SEGS = [{"start": float(i * 5), "end": i * 5 + 4.2, "text": "x"} for i in range(30)]

    def test_validate_clips(self):
        self.assertEqual(len(validate_clips([{"start": "1:00", "end": "1:40"}, {"end": 3}])), 1)
        with self.assertRaises(ValueError):
            validate_clips([{"start": 1}])
        with self.assertRaises(ValueError):
            validate_clips({"start": 1, "end": 2})
        self.assertEqual(validate_clips([], allow_empty=True), [])

    def test_snap_handles_strings_overlap_and_out_of_range(self):
        out = snap([{"start": "0:03", "end": 50}, {"start": 40, "end": 95}, {"start": 140, "end": 400}],
                   self.SEGS, 150, 25, 60)
        self.assertEqual([(c["start"], c["end"]) for c in out], [(5.0, 49.2), (50.0, 94.2)])

    def test_snap_without_transcript(self):
        self.assertEqual(snap([{"start": 1, "end": 40}], [], 150, 25, 60), [])


class PauseCuts(unittest.TestCase):
    WORDS = [{"start": 1.0, "end": 1.4, "word": "a"}, {"start": 1.5, "end": 1.9, "word": "b"},
             {"start": 5.0, "end": 5.4, "word": "c"}, {"start": 5.5, "end": 5.9, "word": "d"}]

    def test_long_pause_is_cut(self):
        r = keep_ranges(self.WORDS, 0.0, 8.0, min_gap=0.8, margin=0.2, fps=30)
        self.assertEqual(len(r), 2)
        self.assertAlmostEqual(r[0][1], 2.1, places=1)
        self.assertAlmostEqual(r[1][0], 4.8, places=1)

    def test_remap_moves_later_times_back(self):
        r = [(0.0, 2.1), (4.8, 8.0)]
        self.assertAlmostEqual(remap(1.0, r), 1.0)
        self.assertAlmostEqual(remap(5.0, r), 2.1 + 0.2)
        self.assertAlmostEqual(remap(3.0, r), 2.1)  # inside the cut: lands on the next kept range


class LlmSubscriptionEnv(unittest.TestCase):
    def test_claude_code_picker_never_passes_the_api_key(self):
        seen = {}

        def fake_run(cmd, **kw):
            seen.update(kw["env"])
            return mock.Mock(returncode=0, stdout="[]", stderr="")

        with mock.patch.dict(os.environ, {"PICKER": "claude-code", "ANTHROPIC_API_KEY": "sk-test"}), \
                mock.patch.object(llm.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(llm.subprocess, "run", side_effect=fake_run):
            llm.ask("hi")
        self.assertNotIn("ANTHROPIC_API_KEY", seen)


if __name__ == "__main__":
    unittest.main()
