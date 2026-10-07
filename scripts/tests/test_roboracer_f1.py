"""S1-06 F1 hooks (M1 protocol v0.1): guard-driver triggers, stack-stage injections, D16 stop wait,
F1-8 runner kill and reaping, and the stop detector. No ROS, Unity or GUI required."""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import autodrive_neutral as an  # noqa: E402
import roboracer_episode as ep  # noqa: E402
import roboracer_f1 as f1  # noqa: E402
from test_autodrive_guard import MS, simulate  # noqa: E402


class GuardTriggerTests(unittest.TestCase):
    def test_f1_5_disarm_rearm_stale_epoch_then_one_final_expiry(self):
        def trigger(elapsed_ns):
            return {"disarm": True, "rearm_after_s": 3.0, "source": "f1-5"} if elapsed_ns >= 8_000 * MS else {}

        driver, model, killed = simulate(mode="calibration", duration_s=20, stop_requests_after_s=15,
                                         trigger=trigger, case="f1-5")
        self.assertFalse(killed)
        checks = {c["name"]: c["ok"] for c in driver.phases[0]["checks"]}
        self.assertTrue(driver.summary()["passed"], [c for c in driver.phases[0]["checks"] if not c["ok"]])
        for name in ("rejected not-armed while disarmed", "re-armed with a new epoch",
                     "old-epoch request rejected stale-epoch", "one final lease expiry after re-arm"):
            self.assertTrue(checks[name], name)
        self.assertIn("state armed epoch 2 sup-1", model.events)

    def test_f1_5_without_the_trigger_fails(self):
        driver, _, _ = simulate(mode="calibration", duration_s=20, stop_requests_after_s=15, case="f1-5")
        self.assertFalse(driver.summary()["passed"])

    def test_d16_runner_disarm_stops_forwarding(self):
        def trigger(elapsed_ns):
            return {"disarm": True, "rearm_after_s": None, "source": "runner-error"} if elapsed_ns >= 8_000 * MS else {}

        driver, model, _ = simulate(mode="calibration", duration_s=12, trigger=trigger)
        self.assertTrue(driver.summary()["passed"], driver.phases)
        after = model.events[model.events.index("disarm-request"):]
        self.assertFalse([e for e in after if e.startswith("accept ") or e.startswith("reject ")])


class FakeSnapshot:
    telemetry_seq, session, episode = 40, "s" * 32, 1
    pose = types.SimpleNamespace(x=0.74, y=1.6, yaw=-1.57, stamp=100.0)
    lidar = types.SimpleNamespace(stamp=99.9)


class FakeBridge:
    def __init__(self):
        self._request_seq, self.offered, self.sent = 7, [], []
        sent = self.sent
        self._supervisor = (types.SimpleNamespace(sendto=lambda data, name: sent.append((data, name))), "sup")

    def _offer(self, topic, message):
        self.offered.append((topic, message))

    def latest(self):
        return FakeSnapshot()


class StackInjectionTests(unittest.TestCase):
    def stage(self, case, results):
        args = types.SimpleNamespace(results=results, stack_profile="m6", f1_case=case)
        controller = types.SimpleNamespace(enabled=True, last=None)
        controller.control = lambda *a, **k: types.SimpleNamespace(target_speed=0.3, steer=0.1)
        executer = types.SimpleNamespace(controller=controller)
        stage = an.StackStage(args, executer, FakeBridge(), {})
        stage.phase, stage.phase_start = "run", time.monotonic() - 6.0
        return stage

    def test_each_case_writes_its_trigger(self):
        files = {"f1-1": "freeze-request.json", "f1-5": "guard-trigger.json", "f1-6": "kill-stack-request.json",
                 "f1-7": "runner-heartbeat-pause.json", "f1-8": "kill-runner-request.json",
                 "f1-9": "runner-error-request.json"}
        for case, name in files.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                stage = self.stage(case, Path(tmp))
                stage._inject(time.monotonic(), FakeSnapshot(), 0.3)
                self.assertTrue((Path(tmp) / name).exists())
                self.assertEqual(case, json.loads((Path(tmp) / "fault-inject.json").read_text())["case"])

    def test_f1_2_corrupts_scans_only_inside_the_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.stage("f1-2", Path(tmp))
            stage._install_scan_fault(time.monotonic_ns() + 10_000 * MS)
            scan = types.SimpleNamespace(ranges=[1.0, 2.0])
            stage.bridge._offer("lidar", scan)
            stage.bridge._offer("imu", "imu")
            topic, message = stage.bridge.offered[0]
            self.assertTrue(all(math.isnan(r) for r in message.ranges))
            self.assertEqual([1.0, 2.0], scan.ranges)  # the original message is untouched
            self.assertEqual(("imu", "imu"), stage.bridge.offered[1])

    def test_f1_3_hang_stops_stepping(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.stage("f1-3", Path(tmp))
            stage._inject(time.monotonic(), FakeSnapshot(), 0.3)
            self.assertEqual("hang", stage.phase)

    def test_f1_4_nan_controller_and_direct_supervisor_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            stage = self.stage("f1-4", Path(tmp))
            stage._inject(time.monotonic(), FakeSnapshot(), 0.3)
            command = stage.controller.control()
            self.assertTrue(math.isnan(command.target_speed))
            data, name = stage.bridge.sent[0]
            message = json.loads(data)
            self.assertEqual((8, "\0sup"), (message["seq"], name))
            self.assertTrue(math.isnan(message["target_speed"]))


class RunnerHookTests(unittest.TestCase):
    def test_d16_waits_for_disarm_and_still_wheels(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            frame = {"guard": {"state": "disarmed"}, "motion": {"Encoder Angles": [3.0, 3.1]}}
            (out / "bridge-frames.jsonl").write_text("\n".join(json.dumps(frame) for _ in range(3)) + "\n")
            result = an.runner_error_stop(out, wait_s=1.0)
            self.assertEqual((True, True), (result["disarmed"], result["stopped"]))
            self.assertEqual({"disarm": True, "rearm_after_s": None, "source": "runner-error"},
                             json.loads((out / "guard-trigger.json").read_text()))

    def test_f1_8_kills_the_runner_and_reaps_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            results = Path(tmp) / "results"
            run = results / "run-01"
            run.mkdir(parents=True)
            # A real orphan (re-parented to init, which reaps it), in its own session like the runner's children.
            launcher = subprocess.run(["sh", "-c", "setsid sleep 60 >/dev/null 2>&1 & echo $!"], capture_output=True,
                                      text=True, check=True)
            orphan = int(launcher.stdout.strip())
            (run / "run.json").write_text(json.dumps({"children": [{"label": "player", "pid": orphan}]}))
            runner = subprocess.Popen(["sleep", "60"])
            (run / "kill-runner-request.json").write_text("{}")
            record = ep.kill_runner_when_requested(runner, results, observe_s=0.1, timeout_s=5)
            self.assertTrue(record["killed"] and record["all_gone"], record)
            self.assertEqual(-signal.SIGKILL, runner.returncode)
            self.assertEqual("terminated by SIGTERM", record["reaped"][0]["result"])


class ThreadSnapshotTests(unittest.TestCase):
    def test_snapshot_lists_threads_of_a_live_process(self):
        child = subprocess.Popen(["sleep", "30"])
        try:
            time.sleep(0.1)
            snap = an.thread_snapshot(child.pid)
        finally:
            child.kill()
            child.wait()
        self.assertEqual(child.pid, snap["pid"])
        self.assertEqual(1, len(snap["threads"]))
        self.assertEqual("sleep", snap["threads"][0]["comm"])
        self.assertIn(snap["threads"][0]["state"], ("S", "R", "D"))
        self.assertIn("Threads", snap["status"])

    def test_snapshot_of_a_gone_process_reports_the_error(self):
        child = subprocess.Popen(["true"])
        child.wait()
        self.assertIn("error", an.thread_snapshot(child.pid))


class StopDetectorTests(unittest.TestCase):
    def test_stop_time_and_travel(self):
        series = [(int(t * 1e9), t, 0.3 * min(t, 1.0), 0.0) for t in [i * 0.2 for i in range(15)]]
        result = f1.stop_after(series, int(0.6e9))
        self.assertAlmostEqual(0.6, result["stop_s"], places=6)  # first frame of zero speed: t = 1.2 s
        self.assertAlmostEqual(0.12, result["travel_m"], places=6)

    def test_never_stopping_reports_none(self):
        series = [(int(t * 1e9), t, 0.3 * t, 0.0) for t in [i * 0.2 for i in range(10)]]
        self.assertIsNone(f1.stop_after(series, 0)["stop_s"])


if __name__ == "__main__":
    unittest.main()
