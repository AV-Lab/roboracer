"""SIM1-01 provenance contract/fault cases on recorded-style frames; no ROS, Unity or GUI."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_provenance import (SCHEMA, SOURCES, ClockEstimator, ProvenanceError, ProvenanceTracker,
                                  parse_stamp, summarize)
from autodrive_neutral import check_zero_reply


def frame(seq=1, episode=1, lidar_seq=1, emit=10_000_000, echo="", receipt=0, hooks=False, session="a" * 32):
    data = {"RR Schema": SCHEMA, "RR Session": session, "RR Episode": str(episode),
            "RR Telemetry Seq": str(seq),
            "RR Capabilities": "provenance clock-echo" + (" test-hooks" if hooks else ""),
            "RR Clock": "Stopwatch 10000000", "RR Ping Echo": echo, "RR Ping Receipt Mono": str(receipt),
            "RR Test Frozen": "", "RR Test Hook Rejections": "0", "RR Emit Mono": str(emit)}
    for name, key in SOURCES.items():
        source_seq = lidar_seq if name == "lidar" else seq * 100
        data[key] = f"{source_seq} {episode} {source_seq * 10} {source_seq * 0.05!r} {1_000_000 + source_seq} {1_000_000 + source_seq}"
    return data


class ProvenanceContractTests(unittest.TestCase):
    def test_stamp_parsing_rejects_malformed_nonfinite_and_negative(self):
        self.assertEqual(3, parse_stamp("3 1 30 0.15 100 120")["seq"])
        for bad in ("", "1 2 3", "1 1 1 nan 1 1", "1 1 1 inf 1 1", "-1 1 1 0 1 1", "1 1 1 -0.5 1 1",
                    "x 1 1 0 1 1", "2 1 1 0.1 200 100"):
            with self.subTest(stamp=bad), self.assertRaises((ProvenanceError, ValueError)):
                parse_stamp(bad)

    def test_new_and_reused_samples_keep_identity(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        first = tracker.check(frame(seq=1, lidar_seq=5), 20_000_000)["sources"]["lidar"]
        self.assertFalse(first["reused"])
        again = tracker.check(frame(seq=2, lidar_seq=5), 21_000_000)["sources"]["lidar"]
        self.assertTrue(again["reused"])
        self.assertEqual(first["mono_ns"], again["mono_ns"])
        self.assertFalse(tracker.check(frame(seq=3, lidar_seq=6), 22_000_000)["sources"]["lidar"]["reused"])

    def test_duplicate_and_out_of_order_telemetry_rejected(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        tracker.check(frame(seq=5), 1)
        for seq in (5, 4):
            with self.subTest(seq=seq), self.assertRaises(ProvenanceError):
                tracker.check(frame(seq=seq), 2)

    def test_session_schema_capability_and_missing_field_fail_closed(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        tracker.check(frame(seq=1), 1)
        with self.assertRaises(ProvenanceError):
            tracker.check(frame(seq=2, session="b" * 32), 2)
        for mutate in (lambda f: f.update({"RR Schema": "roboracer.sim1/0"}),
                       lambda f: f.update({"RR Capabilities": "provenance"}),
                       lambda f: f.pop(SOURCES["imu"]),
                       lambda f: f.update({"RR Telemetry Seq": "0"})):
            data = frame(seq=1)
            mutate(data)
            with self.assertRaises(ProvenanceError):
                ProvenanceTracker(expect_test_hooks=False).check(data, 1)

    def test_test_hook_capability_must_match_trial(self):
        with self.assertRaises(ProvenanceError):
            ProvenanceTracker(expect_test_hooks=False).check(frame(hooks=True), 1)
        with self.assertRaises(ProvenanceError):
            ProvenanceTracker(expect_test_hooks=True).check(frame(hooks=False), 1)
        ProvenanceTracker(expect_test_hooks=True).check(frame(hooks=True), 1)

    def test_backward_source_sequence_and_conflicting_reuse_rejected(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        tracker.check(frame(seq=1, lidar_seq=5), 1)
        with self.assertRaises(ProvenanceError):
            tracker.check(frame(seq=2, lidar_seq=4), 2)
        tracker = ProvenanceTracker(expect_test_hooks=False)
        tracker.check(frame(seq=1, lidar_seq=5), 1)
        altered = frame(seq=2, lidar_seq=5)
        altered[SOURCES["lidar"]] = "5 1 50 0.25 999 999"
        with self.assertRaises(ProvenanceError):
            tracker.check(altered, 2)

    def test_episode_reset_clears_sources_and_cross_episode_stamp_rejected(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        tracker.check(frame(seq=1, lidar_seq=9), 1)
        result = tracker.check(frame(seq=2, episode=2, lidar_seq=1), 2)
        self.assertTrue(result["episode_changed"])
        self.assertFalse(result["sources"]["lidar"]["reused"])
        with self.assertRaises(ProvenanceError):
            tracker.check(frame(seq=3, episode=1), 3)
        mixed = frame(seq=4, episode=2)
        mixed[SOURCES["ips"]] = "1 1 10 0.05 1000001 1000001"
        with self.assertRaises(ProvenanceError):
            tracker.check(mixed, 4)

    def test_acquisition_after_emission_rejected(self):
        with self.assertRaises(ProvenanceError):
            ProvenanceTracker(expect_test_hooks=False).check(frame(emit=10), 1)

    def test_clock_offset_bound_and_stale_echo(self):
        clock = ClockEstimator()
        sent = clock.ping(1_000)
        # Simulator clock is 5_000 ahead; 100 ns each way; 50 ns inside the simulator.
        sample = clock.observe(sent, 6_100, 6_150, 1_250)
        self.assertEqual(5_000, sample["offset_ns"])
        self.assertEqual(100, sample["bound_ns"])
        self.assertIsNone(clock.observe(sent, 6_100, 6_150, 1_250))  # repeated echo cannot reuse a ping
        self.assertIsNone(clock.observe("", 0, 0, 0))
        self.assertIsNone(clock.observe("777", 0, 0, 0))  # never-sent value
        bad = clock.ping(2_000)
        with self.assertRaises(ProvenanceError):
            clock.observe(bad, 7_000, 6_999, 2_100)

    def test_age_uses_offset_and_bound(self):
        tracker = ProvenanceTracker(expect_test_hooks=False)
        echo = tracker.clock.ping(500_000)
        data = frame(seq=1, lidar_seq=1, emit=1_200_000, echo=echo, receipt=1_100_000)
        result = tracker.check(data, 700_000)
        clock = result["clock"]
        lidar = result["sources"]["lidar"]
        self.assertAlmostEqual(700_000 - (1_000_001 - clock["offset_ns"]), lidar["age_ns"])
        self.assertEqual(clock["bound_ns"], lidar["age_bound_ns"])


    def freeze_rows(self, resume_after=1, other_reused=False):
        tracker, rows = ProvenanceTracker(expect_test_hooks=True), []
        lidar, t = 1, 0
        for seq in range(1, 15):
            frozen = 4 <= seq <= 9
            if not frozen and seq > 9 + resume_after - 1 or seq < 4:
                lidar += 1
            data = frame(seq=seq, lidar_seq=lidar, emit=10_000_000 + seq * 1000, hooks=True)
            data["RR Test Frozen"] = "lidar" if frozen else ""
            if other_reused and seq == 6:
                data[SOURCES["imu"]] = rows[-1]["imu_raw"]
            echo = tracker.clock.ping(t)
            data.update({"RR Ping Echo": echo, "RR Ping Receipt Mono": str(9_000_000 + seq * 1000)})
            t += 1_000_000
            rows.append({"provenance": tracker.check(data, t), "stamp_basis": "acquisition", "imu_raw": data[SOURCES["imu"]]})
        return rows

    def test_freeze_evaluation_passes_only_complete_reuse_and_prompt_resume(self):
        self.assertTrue(summarize(self.freeze_rows(), [], "lidar")["freeze"]["passed"])
        self.assertFalse(summarize(self.freeze_rows(resume_after=4), [], "lidar")["freeze"]["passed"])
        self.assertFalse(summarize([], [], "lidar")["freeze"]["passed"])

    def test_reply_guard_allows_only_zero_controls_and_known_sim1_fields(self):
        check_zero_reply("Bridge", {"V1 Throttle": "0", "V1 Steering": "0", "RR Ping Mono": "123", "RR Test Freeze": ""})
        check_zero_reply("Bridge", {"V1 Throttle": "0", "V1 Steering": "0", "RR Test Freeze": "lidar,ips"})
        for bad in ({"V1 Throttle": "0", "V1 Steering": "0", "RR Ping Mono": "-1"},
                    {"V1 Throttle": "0", "V1 Steering": "0", "RR Test Freeze": "imu"},
                    {"V1 Throttle": "0", "V1 Steering": "0", "V1 Headlights": "1"},
                    {"V1 Throttle": "0.1", "V1 Steering": "0", "RR Ping Mono": "1"},
                    {"V1 Steering": "0", "RR Ping Mono": "1"}):
            with self.subTest(reply=bad), self.assertRaises(ValueError):
                check_zero_reply("Bridge", bad)


    def test_cli_profile_rule_applies_to_run_and_bridge_but_not_observer(self):
        import subprocess, tempfile
        script = Path(__file__).resolve().parents[1] / "autodrive_neutral.py"
        with tempfile.TemporaryDirectory() as scratch:
            results = Path(scratch) / "never-started"
            run = subprocess.run([sys.executable, "-B", str(script), "run", "--provenance", "--results", str(results)],
                                 capture_output=True, text=True)
            self.assertEqual(2, run.returncode)
            self.assertIn("p0-creep", run.stderr)
            observe = subprocess.run([sys.executable, "-B", str(script), "observe", "--provenance", "--results",
                                      str(results), "--startup-timeout", "nan"], capture_output=True, text=True)
            self.assertNotIn("SIM1 provenance runs use", observe.stderr)
            self.assertIn("Positive finite bounds", observe.stderr)  # reached the later, unrelated check
            self.assertFalse(results.exists())


if __name__ == "__main__":
    unittest.main()
