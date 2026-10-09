"""S2 batch (D20 A): the AVLite StackStage runs several episodes in one stack process, reporting each
finished episode to stage-episodes.json and restarting only after a scene load (new episode).
Stub executer/bridge and a fake clock; no ROS, Unity or AVLite."""

import json
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


class Clock:
    def __init__(self):
        self.t = 1000.0

    def monotonic(self):
        return self.t

    def monotonic_ns(self):
        return int(self.t * 1e9)


class Harness:
    def __init__(self, results, episodes, f2_case=None):
        self.results = results
        self.offered = []
        self.clock = Clock()
        self.seq, self.episode, self.xy = 0, 1, an.M0_SPAWN_XY
        self.controller = NS(enabled=False, last={"steer": 0.0})
        self.bridge = NS(latest=self.latest, _encoder_speed={}, _offer=lambda topic, m: self.offered.append((topic, m)))
        args = NS(results=results, stack_profile="m6", f1_case=None, episodes=episodes, f2_case=f2_case)
        self.state = {}
        self.guard("disarmed")
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic):
            self.stage = an.StackStage(args, NS(controller=self.controller), self.bridge, self.state)

    def guard(self, state):
        an.save(self.results / "bridge-status.json", {"guard": {"state": state}})

    def latest(self):
        return NS(telemetry_seq=self.seq, episode=self.episode, scan_ranges=np.full(1081, 5.0),
                  pose=NS(x=self.xy[0], y=self.xy[1], yaw=4.712))

    def tick(self, move_m=0.0):
        """One 0.1 s stack tick with a new telemetry frame."""
        self.clock.t += 0.1
        self.seq += 1
        self.xy = (self.xy[0] + move_m, self.xy[1])
        with mock.patch.object(an.time, "monotonic", self.clock.monotonic), \
                mock.patch.object(an.time, "monotonic_ns", self.clock.monotonic_ns):
            return self.stage.before_tick()

    def lap(self):
        """Arm, settle, drive 33 m, stop: until the stage goes silent."""
        self.guard("armed")
        while self.stage.phase in ("wait-armed", "settle"):
            self.tick()
        self.assertion_phase = self.stage.phase
        while self.stage.phase == "run":
            self.tick(move_m=2.0)
        while self.stage.phase == "stopping":
            self.tick()

    def episodes(self):
        path = self.results / "stage-episodes.json"
        return json.loads(path.read_text())["episodes"] if path.exists() else []


class BatchStageTests(unittest.TestCase):
    def test_two_episodes_each_reported_and_restart_only_after_a_scene_load(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), episodes=2)
            h.lap()
            self.assertEqual("run", h.assertion_phase)
            self.assertFalse(h.tick())                      # finished: silent, reports episode 1
            (first,) = h.episodes()
            self.assertEqual((1, 1, "distance", None), (first["number"], first["episode"], first["finish_reason"], first["abort"]))
            self.assertGreaterEqual(first["path_m"], 33.0)
            h.guard("disarmed")
            for _ in range(5):                              # same scene: stays silent, no new episode
                self.assertFalse(h.tick())
            self.assertEqual("finished", h.stage.phase)
            h.episode, h.xy = 2, an.M0_SPAWN_XY             # GUI Reset: scene load, back at the spawn
            self.assertTrue(h.tick())
            self.assertEqual(("wait-armed", 2, 0.0), (h.stage.phase, h.stage.number, h.stage.path_m))
            self.assertFalse(h.controller.enabled)          # zero requests until the next run phase
            h.lap()
            self.assertEqual("run", h.assertion_phase)
            self.assertFalse(h.tick())
            self.assertEqual([1, 2], [e["number"] for e in h.episodes()])
            self.assertEqual([1, 2], [e["episode"] for e in h.episodes()])
            h.episode = 3                                   # a further scene load starts nothing
            for _ in range(3):
                self.assertFalse(h.tick())
            self.assertEqual(("finished", 2), (h.stage.phase, len(h.episodes())))

    def test_armed_left_over_from_the_previous_episode_is_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), episodes=2)
            h.lap()
            h.tick()                                        # finished, reported; guard status still "armed"
            h.episode = 2
            for _ in range(3):
                h.tick()
            self.assertEqual("wait-armed", h.stage.phase)   # stale "armed" never starts episode 2
            h.guard("disarmed")
            h.tick()
            h.guard("armed")
            h.tick()
            self.assertEqual("settle", h.stage.phase)

    def test_a_late_frame_of_the_old_scene_does_not_start_the_next_episode(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), episodes=2)
            h.lap()
            h.tick()
            h.guard("disarmed")
            h.episode = 2
            h.tick()                                        # waiting in episode 2, guard seen disarmed
            h.episode = 1                                   # late old-scene frame while the guard reads armed
            h.guard("armed")
            h.tick()
            self.assertEqual("wait-armed", h.stage.phase)
            h.episode = 2
            h.tick()
            self.assertEqual("settle", h.stage.phase)

    def test_single_episode_stage_still_reports_and_stays_finished(self):
        with tempfile.TemporaryDirectory() as d:
            h = Harness(Path(d), episodes=1)
            h.lap()
            self.assertFalse(h.tick())
            h.episode = 2
            self.assertFalse(h.tick())
            self.assertEqual(1, len(h.episodes()))


class F2StageTests(unittest.TestCase):
    def run_to_injection(self, case, sub=""):
        results = Path(self.d.name) / sub
        results.mkdir(exist_ok=True)
        h = Harness(results, episodes=2, f2_case=case)
        h.guard("armed")
        while h.stage.phase in ("wait-armed", "settle"):
            h.tick()                                   # at rest: the start check must pass
        self.assertEqual("run", h.stage.phase)
        for _ in range(200):                           # bounded: injection is due 6 s (60 ticks) into the run
            if h.stage.f2_injected is not None:
                break
            h.tick(move_m=0.05)
        self.assertIsNotNone(h.stage.f2_injected)
        return h

    def setUp(self):
        self.d = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.d.cleanup()

    def test_injection_at_six_seconds_of_run_time_in_the_first_episode_only(self):
        h = self.run_to_injection("f2-9")
        record = json.loads((h.results / "f2-inject.json").read_text())
        self.assertEqual(("f2-9", 1), (record["case"], record["episode"]))
        self.assertGreaterEqual(record["run_elapsed_s"], an.F2_INJECT_S)
        self.assertLess(record["run_elapsed_s"], an.F2_INJECT_S + 0.11)

    def test_scene_reload_during_the_run_ends_and_reports_the_episode(self):
        h = self.run_to_injection("f2-1")
        h.guard("disarmed")
        h.episode = 2                                  # the runner's mid-episode GUI Reset
        h.tick()
        (entry,) = h.episodes()
        self.assertEqual(("scene reload", 1), (entry["finish_reason"], entry["number"]))
        self.assertEqual(("wait-armed", 2), (h.stage.phase, h.stage.number))

    def test_clock_jump_and_blackout_requests_are_written(self):
        h = self.run_to_injection("f2-4")
        self.assertEqual(an.F2_CLOCK_JUMP_NS, json.loads((h.results / "guard-trigger.json").read_text())["clock_jump_ns"])
        h2 = self.run_to_injection("f2-5", sub="b")
        self.assertTrue((h2.results / "supervisor-feedback-blackout.json").exists())

    def test_duplicates_deliver_every_message_twice_inside_the_window(self):
        h = self.run_to_injection("f2-2")
        with mock.patch.object(an.time, "monotonic_ns", h.clock.monotonic_ns):
            h.bridge._offer("lidar", "scan-1")
            h.clock.t += an.F2_FAULT_S + 0.1
            h.bridge._offer("lidar", "scan-2")
        self.assertEqual(["scan-1", "scan-1", "scan-2"], [m for _, m in h.offered])

    def test_reorder_delivers_each_provenance_after_the_next_one(self):
        h = self.run_to_injection("f2-3")
        with mock.patch.object(an.time, "monotonic_ns", h.clock.monotonic_ns):
            for name in ("p1", "p2", "p3", "p4"):
                h.bridge._offer("provenance", name)
            h.bridge._offer("imu", "i1")               # sensors are never held
            h.clock.t += an.F2_FAULT_S + 0.1
            h.bridge._offer("provenance", "p5")      # window over, nothing held: delivered in order
        self.assertEqual(["p2", "p1", "p4", "p3", "i1", "p5"], [m for _, m in h.offered])


if __name__ == "__main__":
    unittest.main()
