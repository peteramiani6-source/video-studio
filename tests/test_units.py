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
import look  # noqa: E402
from render import hook_filters, keep_ranges, remap  # noqa: E402
from plan_shots import heuristic_edit, quality_warnings, validate_edit  # noqa: E402
from render_shots import frame_filter  # noqa: E402
from shots import cut_times, mean_in, parse_metadata, split_shots  # noqa: E402


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
        with mock.patch.object(llm, "ask", side_effect=lambda p, i=(): prompts.append(p) or next(replies)):
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


class Look(unittest.TestCase):
    def test_color_is_skipped_when_neutral(self):
        self.assertEqual(look.color_filters(look.DEFAULTS), [])
        self.assertEqual(look.color_filters({**look.DEFAULTS, "contrast": 1.08, "saturation": 1.25}),
                         ["eq=contrast=1.08:saturation=1.25:brightness=0:gamma=1"])

    def test_wind_filter(self):
        self.assertEqual(look.audio_filters({"wind_filter": True, "wind_cutoff_hz": 120}), ["highpass=f=120"])
        self.assertEqual(look.audio_filters({"wind_filter": False}), [])

    def test_stabilize_modes(self):
        self.assertEqual(look.stabilize_filters({"stabilize": "off"}, "x", 0, 1, 30, ".", "n"), [])
        self.assertEqual(look.stabilize_filters({"stabilize": "deshake"}, "x", 0, 1, 30, ".", "n"), ["deshake"])
        self.assertEqual(look.stabilize_mode({"stabilize": "bogus"}), "off")
        with mock.patch.object(look, "has_filter", return_value=False):
            self.assertEqual(look.stabilize_mode({"stabilize": "vidstab"}), "deshake")

    def test_vidstab_runs_detect_pass_then_transforms(self):
        with mock.patch.object(look, "has_filter", return_value=True), \
                mock.patch.object(look.subprocess, "run") as run:
            f = look.stabilize_filters({"stabilize": "vidstab", "stabilize_zoom": 5}, "src.mp4", 2, 8, 30, ".", "c1")
        self.assertIn("vidstabdetect", " ".join(run.call_args[0][0]))
        self.assertTrue(f[0].startswith("vidstabtransform=input=c1.trf") and "zoom=5" in f[0])


class Hook(unittest.TestCase):
    CFG = {"seconds": 1.5, "font_size": 84, "anchor": "bottom", "y": 0.61, "shadow": 5, "outline": 3,
           "box": False, "max_chars_per_line": 16}

    def render(self, cfg):
        with tempfile.TemporaryDirectory() as d:
            return hook_filters("Behind the scenes of our garden interview", "c", Path(d), cfg, 1920, "DejaVu Sans")

    def test_bottom_anchor_ends_above_y(self):
        f = self.render(self.CFG)
        ys = [int(x.split(":y=")[1].split(":")[0]) for x in f]
        self.assertEqual(len(f), 3)
        self.assertLessEqual(ys[-1] + 84, int(1920 * 0.61))
        self.assertTrue(all("shadowx=5" in x and "borderw=3" in x and "box=1" not in x for x in f))
        self.assertIn("enable='lt(t,1.5)'", f[0])

    def test_box_and_top_anchor(self):
        f = self.render({**self.CFG, "anchor": "top", "box": True, "shadow": 0})
        self.assertEqual(int(f[0].split(":y=")[1].split(":")[0]), int(1920 * 0.61))
        self.assertIn("box=1", f[0])
        self.assertNotIn("shadowx", f[0])

    def test_disabled(self):
        self.assertEqual(self.render({**self.CFG, "enabled": False}), [])


class Shots(unittest.TestCase):
    META = ("frame:0    pts:0       pts_time:0\nlavfi.blur=4.5\n"
            "frame:1    pts:1       pts_time:0.2\nlavfi.blur=5.5\n"
            "frame:2    pts:2       pts_time:10.4\nlavfi.blur=20\n")

    def test_parse_metadata_and_cuts(self):
        self.assertEqual(parse_metadata(self.META, "lavfi.blur"), [(0.0, 4.5), (0.2, 5.5), (10.4, 20.0)])
        self.assertEqual(cut_times(self.META), [0.0, 0.2, 10.4])
        self.assertEqual(mean_in(parse_metadata(self.META, "lavfi.blur"), 0, 1), 5.0)
        self.assertIsNone(mean_in([], 0, 1))

    def test_split_shots_chunks_long_takes_and_merges_slivers(self):
        shots = split_shots([10.0, 10.3, 30.0], total=34.0, max_shot=8)
        # the 0.3 s sliver at 10.0-10.3 joins take 1; take 2 (19.7 s) becomes three chunks under 8 s
        self.assertEqual([(s["take"], s["start"], s["end"]) for s in shots],
                         [(1, 0.0, 5.15), (1, 5.15, 10.3), (2, 10.3, 16.867), (2, 16.867, 23.433),
                          (2, 23.433, 30.0), (3, 30.0, 34.0)])

    def test_no_cuts_still_chunks(self):
        shots = split_shots([], total=20.0, max_shot=8)
        self.assertEqual(len(shots), 3)
        self.assertAlmostEqual(shots[1]["start"], 20 / 3, places=2)


class Montage(unittest.TestCase):
    SHOTS = [{"id": 1, "take": 1, "start": 0.0, "end": 5.0, "blur": 4.0, "motion": 3.0},
             {"id": 2, "take": 2, "start": 5.0, "end": 15.0, "blur": 25.0, "motion": 2.0},
             {"id": 3, "take": 3, "start": 15.0, "end": 23.0, "blur": 5.0, "motion": 30.0},
             {"id": 4, "take": 4, "start": 23.0, "end": 30.0, "blur": 4.5, "motion": 4.0}]
    CFG = {"min_shot": 1.5, "max_shot": 8, "seconds": 12, "gear_max": 3}

    def test_validate_edit_keeps_order_and_fixes_bad_values(self):
        e = validate_edit({"hook": "Hi", "edit": [
            {"shot": 4, "in": 24, "out": 29, "role": "wide", "focus_x": 0.2},
            {"shot": 1, "in": "0:01", "out": 99, "role": "GEAR", "focus_x": 7},   # out capped to shot end
            {"shot": 42, "in": 1, "out": 2},                                      # no such shot
            {"shot": 4, "in": 25, "out": 27},                                     # overlaps piece 1
            {"shot": 2, "in": 6, "out": 6.5}]}, self.SHOTS, self.CFG)              # too short
        self.assertEqual([(p["shot"], p["in"], p["out"]) for p in e["edit"]], [(4, 24.0, 29.0), (1, 1.0, 5.0)])
        self.assertEqual(e["edit"][1]["role"], "gear")
        self.assertEqual(e["edit"][1]["focus_x"], 1.0)

    def test_validate_edit_caps_length_and_needs_two(self):
        e = validate_edit({"edit": [{"shot": 2, "in": 5, "out": 15}, {"shot": 4, "in": 23, "out": 30}]},
                          self.SHOTS, self.CFG)
        self.assertEqual(e["edit"][0]["out"] - e["edit"][0]["in"], 8)
        with self.assertRaises(ValueError):
            validate_edit({"edit": [{"shot": 1, "in": 0, "out": 4}]}, self.SHOTS, self.CFG)

    def test_quality_warnings(self):
        w = quality_warnings({"edit": [{"shot": 2}, {"shot": 3}, {"shot": 4}]}, self.SHOTS)
        self.assertEqual(len(w), 2)
        self.assertIn("blurry", w[0])
        self.assertIn("shaky", w[1])

    def test_heuristic_prefers_sharp_steady_in_time_order(self):
        e = heuristic_edit(self.SHOTS, self.CFG)
        self.assertEqual([p["shot"] for p in e["edit"]], [1, 4])

    def test_frame_filter(self):
        self.assertIn("x='(iw-ow)*0.25'", frame_filter("vertical", 1080, 1920, 0.25))
        self.assertIn("x='(iw-ow)*1'", frame_filter("vertical", 1080, 1920, 3))
        self.assertTrue(frame_filter("wide", 1920, 1080, 0.5).startswith("scale=1920:1080"))


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

    def test_images_go_through_the_read_tool_only(self):
        calls = {}

        def fake_run(cmd, **kw):
            calls["cmd"], calls["input"] = cmd, kw["input"]
            return mock.Mock(returncode=0, stdout="{}", stderr="")

        with mock.patch.dict(os.environ, {"PICKER": "claude-code"}), \
                mock.patch.object(llm.shutil, "which", return_value="/usr/bin/claude"), \
                mock.patch.object(llm.subprocess, "run", side_effect=fake_run):
            llm.ask("pick shots", images=["work/j/frames/sheet_01.jpg"])
        self.assertEqual(calls["cmd"][-2:], ["--allowedTools", "Read"])
        self.assertIn("sheet_01.jpg", calls["input"])
        self.assertTrue(calls["input"].rstrip().endswith("pick shots"))


if __name__ == "__main__":
    unittest.main()
