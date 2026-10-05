"""Known trajectories check window isolation, coordinate mapping and trace loss."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_kinematics import analyze_trace


class KinematicsAnalysisTests(unittest.TestCase):
    def fixture(self, directory):
        start = 10_000_000_000
        header = {"kind": "binding", "clock": "Linux CLOCK_MONOTONIC", "wheel_order": ["FL", "FR", "RL", "RR"]}
        rows = [header]
        frames = []
        for second in [-1, 0, 1, 2, 61]:
            z = second * .001 if 0 <= second <= 2 else 999.0
            for i, phase in enumerate(["FixedUpdate", "LateUpdate"]):
                pose = {"position": [.1, .02, z], "local_position": [0, 0, 0],
                        "rotation": [0, 0, 0, 1], "local_rotation": [0, 0, 0, 1]}
                wheel = {"grounded": True, "rpm": 0, "motor_torque": 0, "brake_torque": 85.6,
                         "steer_angle": 0, "force": 8.5, "forward_slip": 0, "sideways_slip": 0}
                rows.append({"kind": "sample", "index": len(rows)-1,
                    "monotonic_ns": start + second * 1_000_000_000 + i * 1_000_000, "phase": phase,
                    "body": dict(pose, velocity=[0, 0, .001], angular_velocity=[0,0,0], sleeping=False),
                    "root": copy.deepcopy(pose), "axle": copy.deepcopy(pose), "ips": [z, -.1, .02],
                    "throttle": 0, "steering": 0, "wheels": [copy.deepcopy(wheel) for _ in range(4)]})
            frames.append({"received_monotonic_ns": start + second * 1_000_000_000,
                           "motion": {"Position": [z, -.1, .02]}})
        path = directory / "samples.jsonl"
        path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        status = {"samples": len(rows)-1, "trace_bytes": path.stat().st_size,
                  "total_sample_ns": 1000, "max_sample_ns": 100, "total_flush_ns": 100,
                  "flush_count": 1, "max_flush_ns": 100}
        (directory / "status.json").write_text(json.dumps(status))
        return start, frames, rows, status

    def test_outside_samples_do_not_change_window_displacement_or_axes(self):
        with tempfile.TemporaryDirectory() as scratch:
            p=Path(scratch); start, frames, _, _ = self.fixture(p)
            result=analyze_trace(p,start,start+2_000_000_000,frames)
            phase=result["phases"]["FixedUpdate"]
            self.assertEqual(5, result["window_samples"])
            self.assertAlmostEqual(.002, phase["body_position"]["max_displacement_m"])
            self.assertEqual([0, 0, .002], phase["body_position"]["delta_xyz_m"])
            self.assertEqual([0, 0, 0], phase["ips_minus_current_axle_m"]["max"])
            self.assertEqual(3, result["raw_position_rounding_neighborhood"]["matches"])
            self.assertFalse(result["raw_position_rounding_neighborhood"]["identity_claim"])

    def test_missing_trace_record_and_wrong_final_size_are_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            p=Path(scratch); start, frames, rows, status = self.fixture(p)
            rows.pop(3)
            (p/'samples.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError, "incomplete or reordered"):
                analyze_trace(p,start,start+2_000_000_000,frames)
            self.fixture(p)
            status['trace_bytes'] += 1
            (p/'status.json').write_text(json.dumps(status))
            with self.assertRaisesRegex(ValueError, "counters disagree"):
                analyze_trace(p,start,start+2_000_000_000,frames)


if __name__ == "__main__":
    unittest.main()
