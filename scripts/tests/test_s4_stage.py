"""S4 stage s4 (D56, D58): the blocked outcome after a hold at rest, the obstacle-freshness abort, and the
--obstacle-fixture requirement. Stub executer/bridge/localizer/detector/planner and a fake clock."""

import math
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import autodrive_neutral as an  # noqa: E402
from test_s3_m3_stage import Clock, FakeLocalizer  # noqa: E402

X0, Y0 = an.M0_SPAWN_XY
HEADING = -math.pi / 2


class Harness:
    def __init__(self, results):
        self.results, self.clock = results, Clock()
        self.seq, self.s, self.speed = 0, 0.0, 0.0
        self.b = NS(enabled=False, last={"steer": 0.0})
        self.loc = FakeLocalizer()
        self.detector = NS(obstacles_stamp=None, obstacles=[], status={})
        self.planner = NS(blocked=False, blocked_reason="", diagnostics={}, resets=0, steps=0)

        def reset():
            self.planner.blocked, self.planner.blocked_reason = False, ""
            self.planner.resets += 1

        def step(ego):
            self.planner.steps += 1

        self.planner.reset, self.planner.step = reset, step
        self.executer = NS(controller=self.b, localization=self.loc, perception=NS(_detector=self.detector),
                           local_planner=self.planner, pm=NS(ego_vehicle=NS(x=X0, y=Y0, theta=HEADING)))
        self.bridge = NS(latest=self.latest, _encoder_speed={}, get_sensor_frame=lambda: NS())
        args = NS(results=results, stack_profile="s4", f1_case=None, episodes=1, f2_case=None, m3_ic=None)
        self.state = {"s4": {"blocked": None}}
        self.fresh_obstacles = True
        an.save(results / "bridge-status.json", {"guard": {"state": "disarmed"}})
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic):
            self.stage = an.StackStage(args, self.executer, self.bridge, self.state)

    def latest(self):
        return NS(telemetry_seq=self.seq, episode=1, scan_ranges=np.full(1081, 5.0),
                  pose=NS(x=X0, y=Y0 - self.s, yaw=HEADING))

    def tick(self):
        self.clock.t += 0.1
        self.seq += 1
        driving = self.stage.phase == "run" and self.b.enabled
        self.speed = 0.0 if (self.planner.blocked or not driving) else 0.5
        self.s += self.speed * 0.1
        self.bridge._encoder_speed[self.seq] = self.speed
        self.loc.scan((X0, Y0 - self.s, HEADING))
        if self.fresh_obstacles:
            self.detector.obstacles_stamp = self.clock.t - 0.3
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic), \
                mock.patch.object(an.time, "monotonic_ns", self.clock.monotonic_ns):
            return self.stage.before_tick()

    def run_until(self, phase, limit=400):
        for _ in range(limit):
            self.tick()
            if self.stage.phase == phase:
                return True
        return False


class S4StageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.h = Harness(Path(self.tmp.name))
        an.save(self.h.results / "bridge-status.json", {"guard": {"state": "armed"}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_clear_track_keeps_driving(self):
        self.assertTrue(self.h.run_until("run"))
        for _ in range(50):
            self.h.tick()
        self.assertEqual("run", self.h.stage.phase, self.h.state)
        self.assertIsNone(self.h.state["s4"]["blocked"])

    def test_blocked_ends_as_blocked_after_the_hold_at_rest(self):
        self.assertTrue(self.h.run_until("run"))
        for _ in range(10):
            self.h.tick()
        self.h.planner.blocked, self.h.planner.blocked_reason = True, "no collision-free in-bounds edge"
        ticks = 0
        while self.h.stage.phase == "run" and ticks < 100:
            self.h.tick()
            ticks += 1
        self.assertEqual("stopping", self.h.stage.phase)
        self.assertEqual("blocked", self.h.state["finish_reason"])
        self.assertIsNone(self.h.state.get("abort"))
        blocked = self.h.state["s4"]["blocked"]
        self.assertEqual("no collision-free in-bounds edge", blocked["reason"])
        # Held at rest for S4_BLOCKED_HOLD_S (2 s at 0.1 s ticks), not ended immediately.
        self.assertGreaterEqual(ticks, int(an.S4_BLOCKED_HOLD_S / 0.1))
        self.assertLessEqual(ticks, int(an.S4_BLOCKED_HOLD_S / 0.1) + 2)

    def test_a_latch_from_before_the_run_is_cleared_at_run_start(self):
        """Regression (first T1 attempt): replans before ICP initialization latched "blocked"; the run resets it."""
        self.h.planner.blocked, self.h.planner.blocked_reason = True, "no collision-free in-bounds edge"
        self.assertTrue(self.h.run_until("run"))
        self.assertEqual(1, self.h.planner.resets)
        self.assertFalse(self.h.planner.blocked)
        self.assertEqual({"was_blocked": True, "reason": "no collision-free in-bounds edge"},
                         self.h.state["s4"]["planner_reset_at_run"])
        for _ in range(40):
            self.h.tick()
        self.assertEqual("run", self.h.stage.phase, self.h.state)

    def test_stale_obstacle_observation_aborts(self):
        self.assertTrue(self.h.run_until("run"))
        for _ in range(5):
            self.h.tick()
        self.h.fresh_obstacles = False  # scans keep arriving, the detector produces nothing new
        self.assertTrue(self.h.run_until("stopping", limit=20))
        self.assertIn("no new obstacle observation", self.h.state["abort"])


class S4ArgumentTests(unittest.TestCase):
    def runner(self, *argv):
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/autodrive_neutral.py"), "plugin-observe",
                                   "--results", d, "--plugin", str(ROOT / "roboracer"), *argv],
                                  capture_output=True, text=True, timeout=60)

    def test_obstacle_fixture_is_required_for_and_only_for_s4(self):
        missing = self.runner("--stack-profile", "s4")
        self.assertNotEqual(0, missing.returncode)
        self.assertIn("--obstacle-fixture is required for, and only for, stage s4", missing.stderr)
        stray = self.runner("--stack-profile", "s3v1i", "--obstacle-fixture", str(ROOT / "scripts/s4-fixtures/t1-left-pass.json"))
        self.assertNotEqual(0, stray.returncode)
        self.assertIn("--obstacle-fixture is required for, and only for, stage s4", stray.stderr)


if __name__ == "__main__":
    unittest.main()
