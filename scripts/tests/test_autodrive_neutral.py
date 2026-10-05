"""Guard regressions for the approved diagnostic; no ROS, Unity or GUI required."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_neutral import (check_zero_reply, motion_fields, profile_record, rejected_motion_fields,
                              check_kinematics_status, check_kinematics_prefix)


def reference():
    return {"Position": [0.050, 3.158, 0.059], "Encoder Angles": [0.0, 0.0],
            "Encoder Ticks": [0.0, 0.0]}


class NeutralGuardTests(unittest.TestCase):
    def probe_status(self):
        return {"schema": 1, "pid": 123, "state": "ready", "error": "",
                "heartbeat_monotonic_ns": 9_500_000_000, "last_sample_ns": 9_400_000_000,
                "samples": 2, "fixed_samples": 1, "late_samples": 1,
                "trace_bytes": 1000, "max_trace_bytes": 1024 * 1024 * 1024}

    def test_kinematics_status_requires_owned_healthy_complete_trace(self):
        state = self.probe_status()
        check_kinematics_status(state, 123, 10_000_000_000)
        for patch in ({"pid": 124}, {"state": "failed"}, {"error": "disk full"},
                      {"samples": 0}, {"late_samples": 0}, {"samples": 3},
                      {"trace_bytes": 1024 * 1024 * 1024 + 1}, {"samples": float("nan")}):
            with self.subTest(patch=patch), self.assertRaises(RuntimeError):
                check_kinematics_status(dict(state, **patch), 123, 10_000_000_000)

    def test_kinematics_clock_and_closed_state_are_checked(self):
        state = self.probe_status()
        for key in ("heartbeat_monotonic_ns", "last_sample_ns"):
            for bad in (6_999_999_999, 10_000_000_001):
                with self.subTest(key=key, value=bad), self.assertRaises(RuntimeError):
                    check_kinematics_status(dict(state, **{key: bad}), 123, 10_000_000_000)
        with self.assertRaises(RuntimeError):
            check_kinematics_status(state, 123, 20_000_000_000, closed=True)
        check_kinematics_status(dict(state, state="closed"), 123, 20_000_000_000, closed=True)

    def test_kinematics_trace_prefix_rejects_partial_or_nonfinite_json(self):
        with tempfile.TemporaryDirectory() as scratch:
            out = Path(scratch)
            binding = json.dumps({"kind": "binding", "schema": 1, "pid": 123})
            first = {"kind": "sample", "index": 0, "phase": "FixedUpdate", "monotonic_ns": 100}
            path = out / "samples.jsonl"
            path.write_text(binding + "\n" + json.dumps(first) + "\n")
            self.assertEqual(100, check_kinematics_prefix(out, 123)["first_sample_monotonic_ns"])
            for bad in ('{"kind":', json.dumps(dict(first, value=float("nan")))):
                path.write_text(binding + "\n" + bad)
                with self.assertRaises(ValueError):
                    check_kinematics_prefix(out, 123)

    def test_kinematics_cannot_be_enabled_in_p0(self):
        script = Path(__file__).resolve().parents[1] / "autodrive_neutral.py"
        with tempfile.TemporaryDirectory() as scratch:
            results = Path(scratch) / "never-started"
            result = subprocess.run([sys.executable, "-B", str(script), "run", "--kinematics-probe",
                "--results", str(results)], capture_output=True, text=True)
            self.assertEqual(2, result.returncode)
            self.assertIn("diagnostic-only profile", result.stderr)
            self.assertFalse(results.exists())

    def test_default_p0_keeps_first_change_stop(self):
        before = reference()
        self.assertEqual([], rejected_motion_fields(before, copy.deepcopy(before)))
        for key in before:
            after = copy.deepcopy(before)
            after[key][0] += 0.000001
            self.assertIn(key, rejected_motion_fields(before, after))

    def test_diagnostic_position_cap_is_inclusive_and_three_dimensional(self):
        before = reference()
        for position, rejects in [([0.051, 3.158, 0.059], False),
                                  ([0.059, 3.158, 0.059], False),
                                  ([0.060, 3.158, 0.059], True),
                                  ([0.040, 3.158, 0.059], True),
                                  ([0.050, 3.168, 0.059], True),
                                  ([0.050, 3.158, 0.069], True),
                                  ([0.056, 3.166, 0.059], True)]:
            with self.subTest(position=position):
                after = copy.deepcopy(before)
                after["Position"] = position
                self.assertEqual(rejects, "Position" in rejected_motion_fields(before, after, "drift-diagnostic"))

    def test_subcap_drift_never_masks_encoder_change(self):
        before = reference()
        for key in ("Encoder Ticks", "Encoder Angles"):
            after = copy.deepcopy(before)
            after["Position"][0] = 0.051
            after[key][1] = 0.001
            self.assertEqual([key], rejected_motion_fields(before, after, "drift-diagnostic"))

    def test_amended_p0_creep_bound_matches_diagnostic_and_keeps_encoder_stop(self):
        before = reference()
        for position in ([0.059, 3.158, 0.059], [0.060, 3.158, 0.059], [0.056, 3.166, 0.059]):
            after = copy.deepcopy(before)
            after["Position"] = position
            self.assertEqual(rejected_motion_fields(before, after, "drift-diagnostic"),
                             rejected_motion_fields(before, after, "p0-creep"))
        after = copy.deepcopy(before)
        after["Position"][0] = 0.051
        after["Encoder Ticks"][0] = 0.001
        self.assertEqual(["Encoder Ticks"], rejected_motion_fields(before, after, "p0-creep"))
        record = profile_record("p0-creep")
        self.assertFalse(record["diagnostic_only"])
        self.assertEqual((0.010, ">= cap"), (record["position_stop_m"], record["position_stop_comparison"]))

    def test_unknown_profile_fails_closed(self):
        with self.assertRaises(ValueError):
            rejected_motion_fields(reference(), reference(), "relaxed")
        self.assertFalse(profile_record("p0")["diagnostic_only"])
        self.assertTrue(profile_record("drift-diagnostic")["diagnostic_only"])

    def test_zero_command_guard_remains_exact(self):
        check_zero_reply("Bridge", {"V1 Throttle": "0.000", "V1 Steering": "-0.0"})
        for bad in ("0.000001", "-0.001", "nan", "inf"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                check_zero_reply("Bridge", {"V1 Throttle": bad, "V1 Steering": "0"})

    def test_nonfinite_motion_and_feedback_are_rejected_before_profile(self):
        valid = {"V1 Position": "0.05 3.158 0.059", "V1 Encoder Angles": "0 0",
                 "V1 Encoder Ticks": "0 0", "V1 Orientation Quaternion": "0 0 0 1",
                 "V1 Orientation Euler Angles": "0 0 0", "V1 Angular Velocity": "0 0 0",
                 "V1 Linear Acceleration": "0 0 0", "V1 Throttle": "0", "V1 Steering": "0"}
        for key, value in (("V1 Position", "nan 0 0"), ("V1 Encoder Ticks", "0 inf"),
                           ("V1 Throttle", "0.001"), ("V1 Steering", "nan")):
            with self.subTest(field=key), self.assertRaises(ValueError):
                motion_fields(dict(valid, **{key: value}))

    def test_oversized_diagnostic_is_rejected_without_creating_results(self):
        script = Path(__file__).resolve().parents[1] / "autodrive_neutral.py"
        with tempfile.TemporaryDirectory() as scratch:
            results = Path(scratch) / "never-started"
            for option in (("--duration", "61"), ("--runs", "3")):
                completed = subprocess.run([sys.executable, "-B", str(script), "run",
                    "--profile", "drift-diagnostic", "--results", str(results), *option],
                    capture_output=True, text=True)
                self.assertEqual(2, completed.returncode)
                self.assertIn("Approved diagnostic bounds", completed.stderr)
                self.assertFalse(results.exists())


if __name__ == "__main__":
    unittest.main()
