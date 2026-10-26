"""S3-05 M3 stage (D44/D45): B approaches the initial condition on ICP, holds, the pose is checked against the
configured IC, then the measured episode starts with A (or B). Stub executer/bridge/localizer and a fake clock."""

import math
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest import mock

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import autodrive_neutral as an  # noqa: E402

X0, Y0 = an.M0_SPAWN_XY
HEADING = -math.pi / 2


class Clock:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def monotonic_ns(self):
        return int(self.t * 1e9)


class FakeLocalizer:
    def __init__(self):
        self.status, self.lost, self.stamp = {"state": "uninitialized"}, False, 0.0

    def initialize(self, *pose):
        self.status = {"state": "initialized"}

    def verify_initialization(self, frame):
        self.status = {"state": "verified"}
        return {"accepted": True, "along_track": "unobservable"}

    def scan(self, pose):
        self.stamp += 0.1
        self.status = {"state": "valid", "stamp": self.stamp, "pose": list(pose)}


class Harness:
    def __init__(self, results, ic, algorithm="A"):
        self.results, self.clock = results, Clock()
        self.seq, self.s, self.speed = 0, 0.0, 0.0
        path_s = np.linspace(0.0, 40.0, 401)
        tj = NS(path_s=path_s, path_x=np.full(401, X0), path_y=Y0 - path_s, path_heading=np.full(401, HEADING))
        self.b = NS(enabled=False, tj=tj, config=NS(speed_cap_mps=0.5), last={"steer": 0.0, "s_m": 0.0})
        self.a = NS(enabled=False, last={"steer": 0.0}, params=NS())
        self.loc = FakeLocalizer()
        self.executer = NS(controller=self.b, localization=self.loc)
        self.bridge = NS(latest=self.latest, _encoder_speed={}, get_sensor_frame=lambda: NS())
        args = NS(results=results, stack_profile="s3m3a" if algorithm == "A" else "s3m3b", f1_case=None, episodes=1,
                  f2_case=None, m3_ic=ic)
        self.state = {"m3": {"ic": ic}}
        an.save(results / "bridge-status.json", {"guard": {"state": "disarmed"}})
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic):
            self.stage = an.StackStage(args, self.executer, self.bridge, self.state)
            self.stage.m3_setup(ic, self.a if algorithm == "A" else None)

    def xy(self):
        return X0, Y0 - self.s

    def latest(self):
        x, y = self.xy()
        return NS(telemetry_seq=self.seq, episode=1, scan_ranges=np.full(1081, 5.0), pose=NS(x=x, y=y, yaw=HEADING))

    def tick(self):
        self.clock.t += 0.1
        self.seq += 1
        moving = self.stage.phase == "approach" and self.b.enabled
        if moving:
            self.s += min(self.b.config.speed_cap_mps, 0.5) * 0.1
        self.b.last = {"steer": 0.0, "s_m": self.s}
        self.bridge._encoder_speed[self.seq] = min(self.b.config.speed_cap_mps, 0.5) if moving else 0.0
        self.loc.scan((*self.xy(), HEADING))
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic), \
                mock.patch.object(an.time, "monotonic_ns", self.clock.monotonic_ns):
            return self.stage.before_tick()

    def arm(self):
        an.save(self.results / "bridge-status.json", {"guard": {"state": "armed"}})


class M3StageTests(unittest.TestCase):
    def test_approach_hold_check_then_a_takes_over(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), ic=1)
            h.arm()
            caps = []
            for _ in range(400):
                h.tick()
                if h.stage.phase == "approach":
                    caps.append(h.b.config.speed_cap_mps)
                if h.stage.phase == "run":
                    break
            self.assertEqual("run", h.stage.phase, h.state)
            self.assertAlmostEqual(6.25, h.s, delta=0.05)
            self.assertEqual(0.5, max(caps))
            self.assertAlmostEqual(an.M3_APPROACH_CREEP, min(caps), delta=1e-9)  # creeping at the end
            reached = h.state["m3"]["reached"]
            self.assertLess(reached["deviation_m"], an.M3_IC_TOLERANCE[0])
            self.assertIs(h.executer.controller, h.a)  # configuration A drives the episode
            self.assertTrue(h.a.enabled)
            self.assertEqual(0.0, h.stage.path_m)
            self.assertIn("episode_start_ns", h.state["m3"])

    def test_ic0_starts_at_the_spawn_without_approach(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), ic=0, algorithm="B")
            h.arm()
            for _ in range(100):
                h.tick()
                if h.stage.phase == "run":
                    break
            self.assertEqual("run", h.stage.phase)
            self.assertIsNone(h.state["m3"]["approach"])
            self.assertIs(h.executer.controller, h.b)

    def test_pose_outside_tolerance_is_an_initialization_failure(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), ic=2)
            h.stage.m3_target = (h.stage.m3_target[0], h.stage.m3_target[1] + 0.2, *h.stage.m3_target[2:])
            h.arm()
            for _ in range(600):
                h.tick()
                if h.stage.phase in ("stopping", "run"):
                    break
            self.assertEqual("stopping", h.stage.phase)
            self.assertIn("initialization failure", h.state["abort"])


if __name__ == "__main__":
    unittest.main()
