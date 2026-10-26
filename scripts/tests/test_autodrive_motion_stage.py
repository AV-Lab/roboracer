"""Motion protocol v0.1 stage M0 (steering only): runner-side and supervisor-side bounds,
the approval record and the calibration schedule. No ROS, Unity or GUI required."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from autodrive_neutral import (MOTION_APPROVAL, MOTION_STAGES, check_guard_request, m0_schedule,  # noqa: E402
                               m1_next_pulse, motion_fields)

spec = importlib.util.spec_from_file_location("supervisor_core", ROOT / "roboracer/runtime/supervisor_core.py")
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)

MS = 1_000_000
NOW = 10_000 * MS


def frame(throttle="0.000", steering="0.000"):
    data = {"V1 " + k: v for k, v in {"Position": "0.741 3.158 0.059", "Encoder Angles": "0 0", "Encoder Ticks": "0 0",
            "Orientation Quaternion": "0 0 0 1", "Orientation Euler Angles": "0 0 0",
            "Angular Velocity": "0 0 0", "Linear Acceleration": "0 0 0"}.items()}
    data.update({"V1 Throttle": throttle, "V1 Steering": steering})
    return data


def calibration(seq=1, throttle=0.0, steering=0.5):
    return {"kind": "calibration", "origin": "cal", "seq": seq, "gen_ns": NOW - 50 * MS, "throttle": throttle,
            "steering": steering, "observation": {"telemetry_seq": 9, "stamp_ns": NOW - 200 * MS}}


class RunnerStageTests(unittest.TestCase):
    def test_stage_tables_agree_and_approval_names_only_m0(self):
        self.assertEqual(core.STAGES, MOTION_STAGES)
        approval = json.loads(MOTION_APPROVAL.read_text())
        self.assertEqual(("0.1", ["M0", "M1", "M2", "M3", "M3B", "M4", "M5", "M6", "S3B", "M3C", "S3V1", "M3D", "S3V2", "S3V1I"], "A"),
                         (approval["version"], approval["stages"], approval["decisions"]["D1"]))
        for throttle in (0.03, 0.045, 0.06):
            check_guard_request(f"1 sup-1 3 10 20 {throttle} 0 cal.3.t9", "m3b")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.07 0 cal.3.t9", "m3b")
        for item in ("AVLite motion outside M4/M5/M6/S3B/S3V1/S3V2/S3V1I", "more than one lap per episode",
                     "steering while moving outside M5/M6/S3B/S3V1/S3V2/S3V1I", "unattended reset outside S2 batches (D22)",
                     "any S2 live run set without its own run approval (D22)"):
            self.assertIn(item, approval["not_authorized"])

    def test_m4_m5_ranges_match_supervisor(self):
        from autodrive_neutral import AVLITE_MOTION_STAGES
        self.assertEqual(set(core.AVLITE_STAGES), set(AVLITE_MOTION_STAGES))
        for stage, limits in AVLITE_MOTION_STAGES.items():
            self.assertEqual(core.AVLITE_STAGES[stage].get("u_max", core.SpeedLoopParams().u_max), limits["throttle_max"])
            self.assertAlmostEqual(core.AVLITE_STAGES[stage]["max_steer_rad"] / core.STEER_LIMIT_RAD,
                                   limits["steering_max"], places=6)
        check_guard_request("1 sup-1 3 10 20 0.0612 0 avlite.3.t9", "m4")
        check_guard_request("1 sup-1 3 10 20 0.03 -0.668451 avlite.3.t9", "m5")
        for text, stage in (("1 sup-1 3 10 20 0.0701 0 avlite.3.t9", "m4"), ("1 sup-1 3 10 20 0.03 0.1 avlite.3.t9", "m4"),
                            ("1 sup-1 3 10 20 0.03 0.67 avlite.3.t9", "m5"), ("1 sup-1 3 10 20 -0.01 0 avlite.3.t9", "m5")):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_guard_request(text, stage)
        self.assertEqual(0.061, motion_fields(frame(throttle="0.061"), "m4")["Throttle Feedback"])
        self.assertEqual(0.35, motion_fields(frame(steering="0.350"), "m5")["Steering Feedback"])
        for args in ((frame(steering="0.010"), "m4"), (frame(throttle="0.080"), "m5"), (frame(steering="0.400"), "m5")):
            with self.subTest(args=args[1:]), self.assertRaises(ValueError):
                motion_fields(*args)

    def test_simulator_hang_threshold(self):
        from autodrive_neutral import SIM_HANG_S, simulator_hung
        now = 100 * 1_000_000_000
        self.assertEqual(2.0, SIM_HANG_S)
        self.assertFalse(simulator_hung(now - int(0.65e9), now))   # worst observed real gap (M4, GPU-starved)
        self.assertTrue(simulator_hung(now - int(2.01e9), now))
        self.assertFalse(simulator_hung(None, now))                # no frame yet: startup, not a hang

    def test_sim_hang_test_is_stationary_only(self):
        for extra in (["--motion-stage", "m6"], ["--sim-hang-test", "0"]):
            argv = [sys.executable, str(ROOT / "scripts/autodrive_neutral.py"), "run", "--results", "/nonexistent/x",
                    "--sim-hang-test", "10", *extra]
            done = subprocess.run(argv, capture_output=True, text=True)
            self.assertNotEqual(0, done.returncode)
            self.assertIn("--sim-hang-test", done.stderr)

    def test_relocated_path_maps_only_the_documented_move(self):
        from autodrive_neutral import relocated_path
        home = str(Path.home())
        self.assertEqual(f"{home}/roboracer-work/autodrive-builds/x/AutoDRIVE.x86_64",
                         relocated_path("/tmp/roboracer-work/autodrive-builds/x/AutoDRIVE.x86_64"))
        for path in ("/tmp/other/AutoDRIVE.x86_64", f"{home}/roboracer-work/a", None, "/tmp/roboracer-workX/a"):
            self.assertEqual(path, relocated_path(path))

    def test_m6_box_containment_and_m5_radius(self):
        from autodrive_neutral import outside_containment
        spawn = [0.741, 3.158, 0.059]
        self.assertFalse(outside_containment("m6", spawn, [-2.0, -8.0, 0.06]))   # far from spawn, on the track
        for position in ([-4.3, 0.0, 0.06], [2.2, 0.0, 0.06], [0.0, -9.1, 0.06], [0.0, 7.7, 0.06]):
            with self.subTest(position=position):
                self.assertTrue(outside_containment("m6", spawn, position))
        self.assertTrue(outside_containment("m5", spawn, [-2.0, -8.0, 0.06]))    # M5 keeps its 7 m radius
        self.assertFalse(outside_containment("m5", spawn, [0.741, 0.0, 0.059]))
        check_guard_request("1 sup-1 3 10 20 0.03 -0.668451 avlite.3.t9", "m6")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.03 0.67 avlite.3.t9", "m6")

    def test_m3_bounds(self):
        for throttle in (0, 0.005, 0.01, 0.02):
            check_guard_request(f"1 sup-1 3 10 20 {throttle} 0 cal.3.t9", "m3")
        for text in ("1 sup-1 3 10 20 0.03 0 cal.3.t9", "1 sup-1 3 10 20 0.002 0 cal.3.t9",
                     "1 sup-1 3 10 20 0.01 0.1 cal.3.t9"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_guard_request(text, "m3")
        self.assertEqual(0.02, motion_fields(frame(throttle="0.020"), "m3")["Throttle Feedback"])

    def test_m2_bounds(self):
        check_guard_request("1 sup-1 3 10 20 0.01 0 cal.3.t9", "m2")
        check_guard_request("1 sup-1 3 10 20 0 0 cal.3.t9", "m2")
        for text in ("1 sup-1 3 10 20 0.02 0 cal.3.t9", "1 sup-1 3 10 20 0.005 0 cal.3.t9",
                     "1 sup-1 3 10 20 0.01 0.1 cal.3.t9"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_guard_request(text, "m2")
        self.assertEqual(0.01, motion_fields(frame(throttle="0.010"), "m2")["Throttle Feedback"])
        with self.assertRaises(ValueError):
            motion_fields(frame(throttle="0.020"), "m2")

    def test_m1_bounds(self):
        for throttle in (0, 0.002, 0.005, 0.01, 0.02):
            check_guard_request(f"1 sup-1 3 10 20 {throttle} 0 cal.3.t9", "m1")
        for text in ("1 sup-1 3 10 20 0.03 0 cal.3.t9", "1 sup-1 3 10 20 -0.002 0 cal.3.t9",
                     "1 sup-1 3 10 20 0.002 0.1 cal.3.t9"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_guard_request(text, "m1")
        self.assertEqual(0.01, motion_fields(frame(throttle="0.010"), "m1")["Throttle Feedback"])
        for args in ((frame(throttle="0.030"), "m1"), (frame(steering="0.052"), "m1"), (frame(throttle="0.002"), "m0")):
            with self.subTest(args=args[1:]), self.assertRaises(ValueError):
                motion_fields(*args)

    def test_m1_escalation_only_under_caps(self):
        def done(*peaks):
            return [{"throttle": t, "peak_speed_mps": p, "travel_m": 0.01} for t, p in zip((0.002, 0.005, 0.01), peaks)]
        self.assertEqual(0.002, m1_next_pulse([]))
        self.assertEqual(0.005, m1_next_pulse(done(0.05)))
        self.assertIsNone(m1_next_pulse(done(0.25)))           # 0.25 x 2.5 = 0.625 > 0.5: skip
        self.assertEqual(0.02, m1_next_pulse(done(0.05, 0.1, 0.2)))
        self.assertIsNone(m1_next_pulse(done(0.05, 0.1, 0.3)))  # 0.3 x 2 = 0.6 > 0.5
        over = done(0.05)
        over[0]["travel_m"] = 0.6
        self.assertIsNone(m1_next_pulse(over))
        self.assertIsNone(m1_next_pulse(done(0.01, 0.02, 0.04) + [{"throttle": 0.02, "peak_speed_mps": 0.08,
                                                                   "travel_m": 0.01}]))

    def test_guard_request_bounds(self):
        for steering in (0, 0.1, -0.1, 0.5, -0.5, 1.0, -1.0):
            check_guard_request(f"1 sup-1 3 10 20 0 {steering} cal.3.t9", "m0")
        for text in ("1 sup-1 3 10 20 0.01 0 cal.3.t9", "1 sup-1 3 10 20 0 0.3 cal.3.t9",
                     "1 sup-1 3 10 20 0 nan cal.3.t9", "1 sup-1 3 10 20 0 1.5 cal.3.t9", "1 sup-1 3 10 20 0"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                check_guard_request(text, "m0")

    def test_feedback_steering_only_in_m0_and_never_throttle(self):
        self.assertEqual(-0.262, motion_fields(frame(steering="-0.262"), "m0")["Steering Feedback"])
        # Full lock (30 deg = 0.5235988 rad) is reported rounded to 3 decimals.
        self.assertEqual(-0.524, motion_fields(frame(steering="-0.524"), "m0")["Steering Feedback"])
        for args in ((frame(steering="0.262"), None), (frame(throttle="0.010"), "m0"), (frame(steering="0.6"), "m0")):
            with self.subTest(args=args[1:]), self.assertRaises(ValueError):
                motion_fields(*args)

    def test_m0_schedule(self):
        steps = m0_schedule()
        self.assertEqual([0.1, 0.0, -0.1, 0.0, 0.5, 0.0, -0.5, 0.0, 1.0, 0.0, -1.0, 0.0, 0.5], [s[2] for s in steps])
        self.assertEqual(13.0, steps[-1][1])
        self.assertTrue(all(b[0] == a[1] for a, b in zip(steps, steps[1:])))


class SupervisorStageTests(unittest.TestCase):
    def active(self, stage="m0"):
        s = core.SupervisorCore(origin="sup-1", stage=stage)
        s.heartbeat(1, NOW - 100 * MS)
        return s

    def test_m0_forwards_exact_steering_with_zero_throttle(self):
        s = self.active()
        for seq, steering, text in ((1, 0.5, "0.5"), (2, -1.0, "-1.0"), (3, 0.0, "0"), (4, -0.0, "0")):
            d = s.submit(calibration(seq, steering=steering), NOW)
            self.assertEqual(("0", text, "cal.%d.t9" % seq), (d.forward["throttle"], d.forward["steering"],
                                                               d.forward["inputs"]))

    def test_stage_limits_and_no_stage(self):
        s = self.active()
        self.assertEqual("stage-limit", s.submit(calibration(1, throttle=0.01), NOW).reason)
        self.assertEqual("stage-limit", s.submit(calibration(2, steering=0.3), NOW).reason)
        self.assertEqual("no-stage", self.active(None).submit(calibration(1), NOW).reason)
        # The AVLite path stays exact-zero only, even inside the stage (origin binds to the first source).
        a = self.active()
        a.request_origin = "avlite"
        req = {"kind": "request", "origin": "avlite", "seq": 1, "gen_ns": NOW - 50 * MS, "target_speed": 0.0,
               "steer": 0.2, "observation": {"telemetry_seq": 9, "stamp_ns": NOW - 200 * MS}}
        self.assertEqual("motion-not-authorized", a.submit(req, NOW).reason)

    def test_s3b_is_the_m6_envelope(self):
        """S3 B bring-up (D32 A) changes the controller, not the envelope."""
        from autodrive_neutral import AVLITE_MOTION_STAGES
        self.assertEqual(AVLITE_MOTION_STAGES["s3b"], AVLITE_MOTION_STAGES["m6"])
        self.assertEqual(core.AVLITE_STAGES["s3b"], core.AVLITE_STAGES["m6"])

    def test_s3v1_speed_step_envelope(self):
        """S3 speed step V1 (D35-D37): 0.5 m/s, u_max 0.12, overspeed 0.7; every other limit as M6."""
        from autodrive_neutral import AVLITE_MOTION_STAGES, M3C_HOLDS, MOTION_STAGES, STAGE_SPEED_ABORT_MPS
        v1, m6 = AVLITE_MOTION_STAGES["s3v1"], AVLITE_MOTION_STAGES["m6"]
        self.assertEqual({k: v for k, v in v1.items() if k != "throttle_max"}, {k: v for k, v in m6.items() if k != "throttle_max"})
        self.assertEqual(0.12, v1["throttle_max"])
        self.assertEqual(0.7, STAGE_SPEED_ABORT_MPS["s3v1"])
        sup = core.SupervisorCore(origin="sup-1", stage="s3v1")
        self.assertEqual((0.12, 0.7), (sup.speed_loop.p.u_max, sup.speed_loop.p.overspeed_abs_mps))
        self.assertEqual((0.07, 0.5), (core.SupervisorCore(origin="sup-1", stage="s3b").speed_loop.p.u_max,
                                       core.SupervisorCore(origin="sup-1", stage="s3b").speed_loop.p.overspeed_abs_mps))
        check_guard_request("1 sup-1 3 10 20 0.12 0 avlite.3.t9", "s3v1")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.121 0 avlite.3.t9", "s3v1")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.08 0 avlite.3.t9", "s3b")
        self.assertTrue(all(h in MOTION_STAGES["m3c"]["throttle"] for h in M3C_HOLDS))
        check_guard_request("1 sup-1 3 10 20 0.12 0 cal.3.t9", "m3c")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.11 0 cal.3.t9", "m3c")

    def test_s3v2_speed_step_envelope(self):
        """S3 speed step V2 (D40-D42): 1.0 m/s, u_max 0.24, overspeed 1.2; every other limit as M6."""
        from autodrive_neutral import AVLITE_MOTION_STAGES, M3D_HOLDS, MOTION_STAGES, STAGE_SPEED_ABORT_MPS
        v2, m6 = AVLITE_MOTION_STAGES["s3v2"], AVLITE_MOTION_STAGES["m6"]
        self.assertEqual({k: v for k, v in v2.items() if k != "throttle_max"}, {k: v for k, v in m6.items() if k != "throttle_max"})
        self.assertEqual((0.24, 1.2), (v2["throttle_max"], STAGE_SPEED_ABORT_MPS["s3v2"]))
        sup = core.SupervisorCore(origin="sup-1", stage="s3v2")
        self.assertEqual((0.24, 1.2), (sup.speed_loop.p.u_max, sup.speed_loop.p.overspeed_abs_mps))
        self.assertEqual(1.0, core.AVLITE_STAGES["s3v2"]["max_speed_mps"])
        check_guard_request("1 sup-1 3 10 20 0.24 0 avlite.3.t9", "s3v2")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.241 0 avlite.3.t9", "s3v2")
        self.assertTrue(all(h in MOTION_STAGES["m3d"]["throttle"] for h in M3D_HOLDS))
        check_guard_request("1 sup-1 3 10 20 0.24 0 cal.3.t9", "m3d")
        with self.assertRaises(ValueError):
            check_guard_request("1 sup-1 3 10 20 0.12 0 cal.3.t9", "m3d")

    def test_s3v1i_is_the_v1_envelope_on_icp(self):
        from autodrive_neutral import AVLITE_MOTION_STAGES, S3_ICP_STAGES, STAGE_SPEED_ABORT_MPS
        self.assertEqual(AVLITE_MOTION_STAGES["s3v1i"], AVLITE_MOTION_STAGES["s3v1"])
        self.assertEqual(core.AVLITE_STAGES["s3v1i"], core.AVLITE_STAGES["s3v1"])
        self.assertEqual(STAGE_SPEED_ABORT_MPS["s3v1i"], STAGE_SPEED_ABORT_MPS["s3v1"])
        self.assertEqual(("s3v1i", "s3m3a", "s3m3b"), S3_ICP_STAGES)
        for stage in ("s3m3a", "s3m3b"):  # D45/D47: A and B share the V1 envelope
            self.assertEqual(AVLITE_MOTION_STAGES[stage], AVLITE_MOTION_STAGES["s3v1"])
            self.assertEqual(core.AVLITE_STAGES[stage], core.AVLITE_STAGES["s3v1"])

    def test_process_refuses_unconfirmed_stage(self):
        with tempfile.TemporaryDirectory() as scratch:
            bad = Path(scratch, "approval.json")
            bad.write_text(json.dumps({"version": "0.1", "stages": ["M1"]}))
            for confirmation in (str(bad), None):
                argv = [sys.executable, "-B", "-m", "roboracer.runtime.supervisor_process", "--name", "rr-unused",
                        "--target", "rr-unused-t", "--origin", "sup-1", "--status", str(Path(scratch, "s.json")),
                        "--trace", str(Path(scratch, "t.jsonl")), "--stage", "m0"]
                if confirmation:
                    argv += ["--confirmation", confirmation]
                result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=60)
                with self.subTest(confirmation=confirmation):
                    self.assertEqual(2, result.returncode, result.stderr)
                    self.assertIn("not confirmed", result.stderr)


if __name__ == "__main__":
    unittest.main()
