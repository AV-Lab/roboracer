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
        self.detector = NS(obstacles_stamp=None, obstacles=[], status={}, resets=0)

        def detector_reset():
            self.detector.obstacles, self.detector.resets = [], self.detector.resets + 1

        self.detector.reset = detector_reset
        self.planner = NS(blocked=False, blocked_reason="", diagnostics={}, resets=0, steps=0)

        def reset():
            self.planner.blocked, self.planner.blocked_reason = False, ""
            self.planner.resets += 1

        def step(ego):
            self.planner.steps += 1

        self.planner.reset, self.planner.step = reset, step
        self.executer = NS(controller=self.b, localization=self.loc, perception=NS(_detector=self.detector),
                           local_planner=self.planner, pm=NS(ego_vehicle=NS(x=X0, y=Y0, theta=HEADING), agent_vehicles=[]))
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
        self.h.detector.obstacles = ["phantom", "phantom"]  # confirmed before the pose was localized (S4 §22)
        self.h.executer.pm.agent_vehicles = list(self.h.detector.obstacles)
        self.assertTrue(self.h.run_until("run"))
        self.assertEqual(1, self.h.planner.resets)
        self.assertEqual(1, self.h.detector.resets)
        self.assertEqual([], self.h.detector.obstacles)
        self.assertEqual([], self.h.executer.pm.agent_vehicles)
        self.assertEqual({"obstacles": 2}, self.h.state["s4"]["detector_reset_at_run"])
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


class S4FaultCaseTests(unittest.TestCase):
    """D60 F4-2 / F4-3: injected at F4_INJECT_S of run time; F4-2 then ends on the D56 freshness abort."""

    def harness(self, case):
        self.tmp = tempfile.TemporaryDirectory()
        h = Harness(Path(self.tmp.name))
        h.stage.f4 = case
        h.detector.detect = lambda perception_model=None, sensors=None: perception_model
        h.planner.lattice = NS(sample_nodes=lambda *a, **k: None)
        an.save(h.results / "bridge-status.json", {"guard": {"state": "armed"}})
        return h

    def tearDown(self):
        self.tmp.cleanup()

    def test_f4_2_freezes_the_detector_and_the_stage_aborts_within_the_window(self):
        h = self.harness("f4-2")
        self.assertTrue(h.run_until("run"))
        while h.stage.f4_injected is None:
            h.tick()
        injected = h.state["s4"]["f4"]
        self.assertAlmostEqual(an.F4_INJECT_S, injected["run_elapsed_s"], delta=0.11)
        self.assertTrue((h.results / "fault-inject.json").exists())
        pm = NS(agent_vehicles=[])
        h.detector.obstacles = ["box"]
        self.assertEqual(["box"], h.detector.detect(pm, None).agent_vehicles)  # re-reports, never a new stamp
        h.fresh_obstacles = False  # the frozen detector no longer advances obstacles_stamp
        ticks = 0
        while h.stage.phase == "run" and ticks < 20:
            h.tick()
            ticks += 1
        self.assertEqual("stopping", h.stage.phase)
        self.assertIn("no new obstacle observation", h.state["abort"])
        self.assertLessEqual(ticks, int(an.S4_OBSTACLE_STALE_S / 0.1) + 2)

    def test_f4_3_makes_every_replan_raise(self):
        h = self.harness("f4-3")
        self.assertTrue(h.run_until("run"))
        while h.stage.f4_injected is None:
            h.tick()
        with self.assertRaisesRegex(RuntimeError, "injected planning failure"):
            h.planner.lattice.sample_nodes()
        self.assertEqual("f4-3", h.state["s4"]["f4"]["case"])


class S4RearmTests(unittest.TestCase):
    """D63 A: after the blocked hold the stage disarms/re-arms through the guard trigger, then resets lattice and B."""

    def harness(self, case):
        self.tmp = tempfile.TemporaryDirectory()
        h = Harness(Path(self.tmp.name))
        h.stage.s4_rearm = case
        h.bridge.obstacle_fixture = NS(name="t3-blocked")
        h.b.reset = lambda: setattr(h.b, "was_reset", True)
        an.save(h.results / "bridge-status.json", {"guard": {"state": "armed"}})
        self.assertTrue(h.run_until("run"))
        for _ in range(5):
            h.tick()
        h.planner.blocked, h.planner.blocked_reason = True, "no collision-free in-bounds edge"
        self.assertTrue(h.run_until("rearm", limit=40))
        return h

    def tearDown(self):
        self.tmp.cleanup()

    def guard(self, h, state):
        an.save(h.results / "bridge-status.json", {"guard": {"state": state}})

    def test_rearm_waits_for_disarm_then_arm_and_resets_lattice_and_b(self):
        h = self.harness("blocked")
        trigger = an.read(h.results / "guard-trigger.json")
        self.assertEqual({"disarm": True, "rearm_after_s": an.S4_REARM_AFTER_S, "source": "s4-rearm"}, trigger)
        self.assertIsNotNone(h.bridge.obstacle_fixture)  # "blocked": the obstacle stays
        h.tick()
        self.assertEqual("rearm", h.stage.phase)  # still armed: the disarm has not taken effect
        self.guard(h, "disarmed")
        for _ in range(5):
            h.tick()
        self.assertEqual("rearm", h.stage.phase)
        resets = h.planner.resets
        self.guard(h, "armed")
        h.tick()
        self.assertEqual("run", h.stage.phase)
        self.assertEqual(resets + 1, h.planner.resets)
        self.assertFalse(h.planner.blocked)
        self.assertTrue(getattr(h.b, "was_reset", False))
        self.assertIsNotNone(h.state["s4"]["blocked_before_rearm"])
        self.assertIsNone(h.state["s4"]["blocked"])
        self.assertIsNotNone(h.state["s4"]["rearm"]["rearmed_ns"])

    def test_cleared_removes_the_fixture_at_the_disarm(self):
        h = self.harness("cleared")
        self.assertIsNone(h.bridge.obstacle_fixture)
        self.assertTrue(h.state["s4"]["rearm"]["fixture_removed"])
        self.assertEqual("t3-blocked", h.state["s4"]["rearm"]["fixture"])

    def test_rearm_that_never_completes_aborts(self):
        h = self.harness("blocked")
        self.guard(h, "disarmed")
        self.assertTrue(h.run_until("stopping", limit=int(an.S4_REARM_TIMEOUT_S / 0.1) + 5))
        self.assertIn("rearm not completed", h.state["abort"])


class S4ArgumentTests(unittest.TestCase):
    def runner(self, *argv):
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run([sys.executable, "-B", str(ROOT / "scripts/autodrive_neutral.py"), "plugin-observe",
                                   "--results", d, "--plugin", str(ROOT / "roboracer"), *argv],
                                  capture_output=True, text=True, timeout=60)

    def test_obstacle_fixture_is_for_s4_only(self):
        """S5: the fixture is optional on s4 (the release profile on the clear track) and refused on other stages."""
        stray = self.runner("--stack-profile", "s3v1i", "--obstacle-fixture", str(ROOT / "scripts/s4-fixtures/t1-left-pass.json"))
        self.assertNotEqual(0, stray.returncode)
        self.assertIn("--obstacle-fixture is for stage s4 only", stray.stderr)
        f4_elsewhere = self.runner("--stack-profile", "s3v1i", "--f4-case", "f4-2")
        self.assertNotEqual(0, f4_elsewhere.returncode)
        self.assertIn("--f4-case is for stage s4 only", f4_elsewhere.stderr)


if __name__ == "__main__":
    unittest.main()
