"""S2 F2 analysis on synthetic batch directories (no simulator)."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import roboracer_f2 as f2  # noqa: E402

T0 = 1_000_000_000_000
ONSET = T0 + 10_000_000_000


def frame(t_ns, x, events=()):
    sim = (t_ns - T0) / 1e9
    return {"received_monotonic_ns": t_ns, "motion": {"Position": [x, 3.158, 0.059]},
            "provenance": {"episode": 1, "sources": {"ips": {"sim_time": sim}}},
            "guard": {"events": [[i + 1, e] for i, e in enumerate(events)]}}


def make_batch(d: Path, case, stop_after_s=0.6, expiry=True, episode2="healthy", children=None):
    run = d / "session-01" / "run-01"
    run.mkdir(parents=True)
    frames = []
    x = 0.741
    for i in range(80):                        # 0.2 s frames at 0.25 m/s, then the stop
        t = T0 + i * 200_000_000
        moving = t < ONSET + stop_after_s * 1e9
        x += 0.05 if moving else 0.0
        events = ["state stopped lease-expired 99"] if expiry and abs(t - (ONSET + 400_000_000)) < 100_000_000 else []
        frames.append(frame(t, x, events))
    (run / "bridge-frames.jsonl").write_text("\n".join(json.dumps(f) for f in frames) + "\n")
    (run / "f2-inject.json").write_text(json.dumps({"case": case, "injected_ns": ONSET, "run_elapsed_s": 6.02, "episode": 1}))
    status = {"f2_case": case, "children": children or [{"label": "player", "exit_code": 0}]}
    (run / "run.json").write_text(json.dumps(status))
    (run / "plugin-observer-status.json").write_text(json.dumps({"statistics": {}}))
    (run / "plugin-snapshots.jsonl").write_text("")
    (d / "batch.json").write_text(json.dumps({"episodes": [{"outcome": "failed"}, {"outcome": episode2, "session": 2}],
                                              "recovery_actions": [{"action": "fresh player (recovery step 2)"}]}))
    return d


class F2AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_supervisor_exit_with_expiry_stop_and_recovery_passes(self):
        r = f2.analyze(make_batch(self.d / "a", "f2-7"))
        self.assertTrue(r["passed"], r["checks"])
        self.assertLessEqual(r["stop"]["stop_s"], 1.5)

    def test_missing_expiry_or_late_stop_fails(self):
        r = f2.analyze(make_batch(self.d / "b", "f2-7", expiry=False))
        self.assertFalse(r["checks"]["guard lease expiry after the supervisor loss"])
        r = f2.analyze(make_batch(self.d / "c", "f2-8", stop_after_s=2.5))
        self.assertFalse(r["passed"])
        self.assertFalse(r["checks"]["stopped within 1.5 s of onset"])

    def test_simulator_exit_is_containment_not_a_stop(self):
        children = [{"label": "player", "exit_code": -9, "expected_kill": True,
                     "termination": "SIGKILL (F2-9 simulator exit; containment, not a stop)"}]
        r = f2.analyze(make_batch(self.d / "e", "f2-9", children=children))
        self.assertTrue(r["passed"], r["checks"])
        self.assertEqual("containment", r["classification"])
        self.assertNotIn("stop", r)

    def test_stop_is_judged_on_the_injected_episode_only(self):
        # F2-4 shape (run 3): after the fault stop a GUI Reset starts episode 2 in the same session, which
        # drives again; the stop must not wait for the end of that lap.
        d = make_batch(self.d / "h", "f2-4", stop_after_s=0.5, expiry=False)
        run = d / "session-01" / "run-01"
        frames = [json.loads(l) for l in (run / "bridge-frames.jsonl").read_text().splitlines()]
        t, x = frames[-1]["received_monotonic_ns"], frames[-1]["motion"]["Position"][0]
        for i in range(1, 40):                     # episode 2: driving at 0.25 m/s
            f = frame(t + i * 200_000_000, x + 0.05 * i)
            f["provenance"]["episode"] = 2
            frames.append(f)
        frames[-50]["guard"]["events"] = [[1, "clock clock-discontinuity"], [2, "state fault clock-discontinuity"]]
        (run / "bridge-frames.jsonl").write_text("\n".join(json.dumps(f) for f in frames) + "\n")
        r = f2.analyze(d)
        self.assertLessEqual(r["stop"]["stop_s"], 1.5)
        self.assertLessEqual(r["stop"]["travel_m"], 0.40)

    def test_unhealthy_recovery_episode_fails_the_case(self):
        r = f2.analyze(make_batch(self.d / "f", "f2-7", episode2="failed"))
        self.assertFalse(r["checks"]["recovered: episode 2 healthy"])

    def test_unexpected_termination_fails(self):
        r = f2.analyze(make_batch(self.d / "g", "f2-7", children=[{"label": "supervisor-1", "exit_code": -9}]))
        self.assertFalse(r["checks"]["processes: only expected terminations"])


if __name__ == "__main__":
    unittest.main()
