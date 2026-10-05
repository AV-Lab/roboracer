"""S1-03 (proposal v0.2): the supervisor speed loop (D5), the AVLite motion stages m4/m5 and the
reactive baseline A (D6). Pure logic; no simulator, no ROS.
Run with the AVLite interpreter: ``<avlite python> -m unittest discover -s roboracer/tests -t .``
"""

import importlib.util
import math
from pathlib import Path
import sys
import unittest

import numpy as np

PLUGIN = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, PLUGIN / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


core = load("supervisor_core_s103", "runtime/supervisor_core.py")
MS = 1_000_000
NOW = 50_000 * MS


def request(seq, speed=0.2, steer=0.0, gen=NOW - 30 * MS, stamp=NOW - 150 * MS):
    return {"kind": "request", "origin": "avlite", "seq": seq, "gen_ns": gen, "target_speed": speed, "steer": steer,
            "observation": {"telemetry_seq": 40 + seq, "stamp_ns": stamp}}


class SpeedLoopTests(unittest.TestCase):
    def loop(self):
        return core.SpeedLoop()

    def test_feedforward_rise_limit_and_trim(self):
        loop = self.loop()
        loop.feedback(0.0, NOW - 100 * MS, 1, 0.2)
        u, info = loop.command(0.2, NOW)
        self.assertEqual("control", info["rule"])
        self.assertAlmostEqual(0.01, u)                      # first command: one 0.1 s rise step
        u, _ = loop.command(0.2, NOW + 100 * MS)
        self.assertAlmostEqual(0.02, u)
        for k in range(2, 12):
            loop.feedback(0.2, NOW + k * 100 * MS, k, 0.2)
            u, info = loop.command(0.2, NOW + k * 100 * MS + MS)
        self.assertAlmostEqual(0.2 / 5.02 + info["trim"], u, places=5)
        self.assertLessEqual(abs(info["trim"]), 0.01)

    def test_trim_bounded_and_frozen_when_saturated(self):
        loop = self.loop()
        t = NOW
        for k in range(200):
            t += 100 * MS
            loop.feedback(0.0, t - 50 * MS, k, 0.2)          # car never moves: error stays 0.3
            u, info = loop.command(0.3, t)
        self.assertAlmostEqual(0.01, info["trim"])
        self.assertAlmostEqual(min(0.07, 0.3 / 5.02 + 0.01), u, places=5)

    def test_v03_measured_worst_feedback_age_still_controls(self):
        # M4 trial 3: feedback reached 564 ms at request time; v0.3 keeps that in control.
        loop = self.loop()
        loop.feedback(0.1, NOW - 564 * MS, 1, 0.2)
        self.assertEqual("control", loop.command(0.2, NOW)[1]["rule"])

    def test_stale_lost_zero_and_overspeed(self):
        loop = self.loop()
        self.assertEqual((0.0, "no-feedback-yet"), (loop.command(0.2, NOW)[0], loop.command(0.2, NOW)[1]["rule"]))
        loop.feedback(0.1, NOW - 650 * MS, 1, 0.2)
        self.assertEqual((0.0, "stale-feedback"), (loop.command(0.2, NOW)[0], loop.command(0.2, NOW)[1]["rule"]))
        loop.feedback(0.1, NOW - 950 * MS, 2, 0.2)
        self.assertEqual("feedback-lost", loop.command(0.2, NOW)[1]["rule"])
        loop.feedback(0.36, NOW - 50 * MS, 3, 0.2)
        self.assertEqual((0.0, "overspeed"), (loop.command(0.2, NOW)[0], loop.command(0.2, NOW)[1]["rule"]))
        loop.feedback(0.51, NOW - 50 * MS, 4, 0.2)
        self.assertEqual("overspeed", loop.command(0.3, NOW)[1]["rule"])
        loop.feedback(0.1, NOW - 50 * MS, 5, 0.2)
        u, info = loop.command(0.0, NOW)
        self.assertEqual((0.0, "target-zero", 0.0), (u, info["rule"], info["trim"]))


class AVLiteStageTests(unittest.TestCase):
    def core(self, stage):
        s = core.SupervisorCore(origin="sup-1", stage=stage)
        s.heartbeat(1, NOW - 100 * MS)
        s.feedback(0.0, NOW - 100 * MS, 1, 0.2)
        return s

    def test_m4_forwards_speed_loop_output_with_zero_steering(self):
        s = self.core("m4")
        d = s.submit(request(1, speed=0.2), NOW)
        self.assertTrue(d.accepted, d.reason)
        self.assertEqual(("0.01", "0"), (d.forward["throttle"], d.forward["steering"]))
        self.assertEqual("control", d.control["rule"])
        self.assertEqual("stage-limit", s.submit(request(2, speed=0.2, steer=0.05), NOW).reason)
        self.assertEqual("stage-limit", s.submit(request(3, speed=0.31), NOW).reason)

    def test_m5_converts_steering_exactly(self):
        s = self.core("m5")
        d = s.submit(request(1, speed=0.0, steer=0.35), NOW)
        self.assertEqual(("0", repr(round(0.35 / 0.5235987755982988, 6))), (d.forward["throttle"], d.forward["steering"]))
        self.assertEqual("stage-limit", s.submit(request(2, steer=-0.36), NOW).reason)

    def test_no_feedback_yet_forwards_zero_and_stays_active(self):
        # Found live (M4 attempt 2): the first request precedes the first speed sample.
        s = core.SupervisorCore(origin="sup-1", stage="m4")
        s.heartbeat(1, NOW - 100 * MS)
        d = s.submit(request(1, speed=0.0), NOW)
        self.assertEqual((True, "0", "no-feedback-yet"), (d.accepted, d.forward["throttle"], d.control["rule"]))
        d = s.submit(request(2, speed=0.2), NOW)
        self.assertEqual((True, "0", "no-feedback-yet", "active"), (d.accepted, d.forward["throttle"], d.control["rule"], s.state))

    def test_feedback_lost_inhibits(self):
        s = core.SupervisorCore(origin="sup-1", stage="m4")
        s.heartbeat(1, NOW - 100 * MS)
        s.feedback(0.1, NOW - 950 * MS, 1, 0.2)
        self.assertEqual("feedback-lost", s.submit(request(1), NOW).reason)
        self.assertEqual(("inhibited", "feedback-lost"), (s.state, s.reason))
        self.assertEqual("inhibited", s.submit(request(2), NOW).reason)

    def test_avlite_requests_still_closed_outside_m4_m5(self):
        for stage in (None, "m3b"):
            s = core.SupervisorCore(origin="sup-1", stage=stage)
            s.heartbeat(1, NOW - 100 * MS)
            self.assertEqual("limit", s.submit(request(1, speed=0.2), NOW).reason)


class GapFollowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(PLUGIN.parent))
        from roboracer.control import gap_follow
        cls.gf = gap_follow

    def corridor(self, left=0.74, right=-0.54, front=7.4, extra=()):
        pts = []
        for x in np.arange(-0.5, front, 0.02):
            pts += [(x, left), (x, right)]
        for y in np.arange(right, left, 0.02):
            pts.append((front, y))
        pts += list(extra)
        cloud = np.zeros((len(pts), 4), dtype=np.float32)
        cloud[:, :2] = pts
        return cloud

    def test_open_corridor_full_speed_small_steer(self):
        speed, steer, detail = self.gf.gap_follow(self.corridor())
        self.assertAlmostEqual(0.3 * (1 - abs(steer) / 0.6), speed, places=6)
        self.assertLess(abs(steer), 0.12)
        # Within +-10 deg the side walls are nearest: 0.54 m / sin(10 deg) ~ 3.1 m (still full speed).
        self.assertGreater(detail["front_m"], 3.0)
        self.assertEqual(0.3 * (1 - abs(steer) / 0.6), speed)

    def test_obstacle_on_the_right_steers_left(self):
        box = [(1.5, y) for y in np.arange(-0.54, 0.1, 0.02)]
        _, steer, _ = self.gf.gap_follow(self.corridor(extra=box))
        self.assertGreater(steer, 0.0)

    def test_wall_ahead_slows_and_stops(self):
        speed, _, _ = self.gf.gap_follow(self.corridor(front=1.0))
        self.assertLessEqual(speed, 0.25 * (1.0 - 0.5) + 1e-9)
        speed, _, _ = self.gf.gap_follow(self.corridor(front=0.45))
        self.assertEqual(0.0, speed)

    def test_steer_clamped(self):
        side = [(x, -0.3) for x in np.arange(0.1, 7, 0.02)]
        speed, steer, _ = self.gf.gap_follow(self.corridor(left=5.0, right=-0.3, front=0.6, extra=side))
        self.assertLessEqual(abs(steer), 0.35 + 1e-12)


if __name__ == "__main__":
    unittest.main()
