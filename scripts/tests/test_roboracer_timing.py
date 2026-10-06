"""S1-06 timing measurement helpers: percentiles, guard event parsing, frozen-limit checks, GPU sampler."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roboracer_timing as rt  # noqa: E402


class TimingTests(unittest.TestCase):
    def test_percentiles_interpolate_and_skip_nonfinite(self):
        p = rt.pct([4, 1, 3, 2, float("nan"), None])
        self.assertEqual((2.5, 3.85, 4, 4), (p["p50"], round(p["p95"], 2), p["max"], p["n"]))
        self.assertIsNone(rt.pct([]))

    def test_guard_events_match_forwarded_sequences(self):
        guard = [{"k": "step", "step": 1},
                 {"k": "event", "step": 100, "mono": 5_000, "text": "2 accept 9 312646250 0 0 avlite.9.t5"},
                 {"k": "event", "step": 101, "mono": 5_100, "text": "3 applied 9 step 101"},
                 {"k": "event", "step": 102, "text": "4 accept 99 1 0 0 x"},          # not forwarded in window
                 {"k": "event", "step": 103, "text": "5 state stopped lease-expired 9"}]
        accepted, applied = rt.guard_events(guard, {9: {"gen_ns": 1}})
        self.assertEqual({9: {"step": 100, "mono": 5_000, "remaining_ms": 312.64625}}, accepted)
        self.assertEqual({9: 101}, applied)

    def test_limits_flag_an_exceeded_value(self):
        stat = lambda v: {"p50": v, "p95": v, "max": v, "n": 1}  # noqa: E731
        m = {"control": {"observation_age_at_request_ms": stat(510.0), "feedback_age_at_request_ms": stat(100.0),
                         "inhibited_decisions": 0},
             "telemetry": {"period_ms": stat(200.0), "clock_bound_ms": stat(40.0)},
             "latency_ms": {"generation_to_guard_accept": stat(150.0)},
             "stop_and_bounds": {"final_stop_s": 0.3, "max_speed_mps": 0.34, "requested_steer_rad_min_max": [-0.35, 0.1]}}
        limits = rt.check_limits(m)
        self.assertFalse(limits["observation_age_at_request_ms"]["within"])
        self.assertTrue(all(v["within"] for k, v in limits.items() if k != "observation_age_at_request_ms"))


class GpuSamplerTests(unittest.TestCase):
    def test_sampler_writes_rows_and_stops(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import autodrive_neutral as an

        class Done:
            returncode, stdout, stderr = 0, "37, 900, 10240, 45\n", ""
        stop = threading.Event()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(an.subprocess, "run", return_value=Done()):
            path = Path(tmp) / "gpu.jsonl"
            thread = threading.Thread(target=an.sample_gpu, args=(path, stop, 0.01))
            thread.start()
            threading.Event().wait(0.05)
            stop.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            rows = [json.loads(line) for line in path.read_text().splitlines()]
        self.assertGreaterEqual(len(rows), 1)
        self.assertEqual((37.0, 900.0, 10240.0), (rows[0]["utilization_pct"], rows[0]["memory_used_mib"],
                                                   rows[0]["memory_total_mib"]))


if __name__ == "__main__":
    unittest.main()
