"""S2 batch orchestrator: sessions, recovery ladder, attempted-episode counting (stub runner, stationary)."""

import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import roboracer_batch as rb  # noqa: E402

# The stub stands in for autodrive_neutral.py: session N (from its --results name) completes
# plan[N]["complete"] stationary episodes, passing or not, then exits with plan[N]["exit"].
STUB = r'''
import json, os, sys
from pathlib import Path
argv = sys.argv
results = Path(argv[argv.index("--results") + 1])
session = int(results.name.split("-")[1])
plan = json.loads(Path(os.environ["STUB_PLAN"]).read_text())[str(session)]
run = results / "run-01"
run.mkdir(parents=True)
phases = [{"phase": f"episode {i}", "passed": ok, "last_frame": 10 * i, "checks": [{"ok": ok}]}
          for i, ok in enumerate(plan["complete"], 1)]
status = {"error": plan.get("error"), "manual_mode_review": {"automated": {"passed": True}},
          "guard_actions": [{"kind": "gui-reset", "review": {"automated": {"passed": True}}}], "argv": argv}
if plan["exit"] == 0:
    status["bridge_at_end"] = {"guard": {"phases": phases}}  # like the runner: only on a completed run
(run / "bridge-status.json").write_text(json.dumps({"guard": {"phases": phases}}))
(run / "run.json").write_text(json.dumps(status))
sys.exit(plan["exit"])
'''


class BatchTests(unittest.TestCase):
    def run_plan(self, episodes, plan):
        d = Path(self.tmp.name)
        (d / "stub.py").write_text(STUB)
        (d / "plan.json").write_text(json.dumps(plan))
        os.environ["STUB_PLAN"] = str(d / "plan.json")
        out = d / f"batch-{len(list(d.glob('batch-*')))}"
        args = ["--stage", "stationary", "--episodes", str(episodes), "--output", str(out), "--context", "c.json",
                "--player", "p", "--ui-reference", "r.json", "--runner", str(d / "stub.py")]
        code = rb.main(args)
        return code, json.loads((out / "batch.json").read_text())

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()
        os.environ.pop("STUB_PLAN", None)

    def test_one_clean_session_runs_every_episode(self):
        code, b = self.run_plan(3, {"1": {"complete": [True, True, True], "exit": 0}})
        self.assertEqual((0, 3, 3, 3, True, True), (code, b["attempted"], b["healthy"], b["longest_healthy_streak"],
                                                     b["passed"], b["unattended"]))
        self.assertEqual([], b["recovery_actions"])
        self.assertEqual(1, len(b["sessions"]))

    def test_failed_session_counts_the_episode_and_restarts_for_the_rest(self):
        plan = {"1": {"complete": [True], "exit": 1, "error": "RuntimeError: Simulator hang"},
                "2": {"complete": [True], "exit": 0}}
        code, b = self.run_plan(3, plan)
        self.assertEqual(["healthy", "failed", "healthy"], [e["outcome"] for e in b["episodes"]])
        self.assertIn("Simulator hang", b["episodes"][1]["failure"])
        self.assertEqual(1, len(b["recovery_actions"]))
        self.assertEqual("fresh player (recovery step 2)", b["recovery_actions"][0]["action"])
        session2 = b["sessions"][1]
        self.assertEqual(1, session2["episodes_requested"])     # only the remaining episode
        self.assertEqual((1, False, "all episodes attempted"), (code, b["passed"], b["end_reason"]))

    def test_episodes_finished_before_a_failure_count_from_the_live_bridge_status(self):
        plan = {"1": {"complete": [True], "exit": 1, "error": "RuntimeError: Simulator hang"},
                "2": {"complete": [True], "exit": 0}}
        _, b = self.run_plan(3, plan)
        self.assertEqual([(1, "healthy"), (1, "failed"), (2, "healthy")], [(e["session"], e["outcome"]) for e in b["episodes"]])
        self.assertEqual([3, 1], [s["episodes_requested"] for s in b["sessions"]])

    def test_session_ending_early_with_exit_0_still_counts_and_recovers(self):
        plan = {"1": {"complete": [], "exit": 0}, "2": {"complete": [True], "exit": 0}}  # e.g. F2-6 Devkit loss
        _, b = self.run_plan(2, plan)
        self.assertEqual([(1, "failed"), (2, "healthy")], [(e["session"], e["outcome"]) for e in b["episodes"]])
        self.assertEqual("session ended early", b["episodes"][0]["failure"])
        self.assertEqual(1, len(b["recovery_actions"]))

    def test_restart_that_fails_again_ends_the_batch(self):
        plan = {"1": {"complete": [], "exit": 1, "error": "RuntimeError: Initialization failed after GUI Reset"},
                "2": {"complete": [], "exit": 1, "error": "RuntimeError: Automated pre-Connect check failed"}}
        code, b = self.run_plan(5, plan)
        self.assertEqual(2, len(b["sessions"]))
        self.assertEqual(2, b["attempted"])                       # failed initializations count
        self.assertTrue(b["end_reason"].startswith("restart failed"))
        self.assertEqual(1, code)

    def test_streak_counts_consecutive_healthy_episodes(self):
        plan = {"1": {"complete": [True, True, False, True, True, True], "exit": 0}}
        _, b = self.run_plan(6, plan)
        self.assertEqual((5, 3), (b["healthy"], b["longest_healthy_streak"]))


if __name__ == "__main__":
    unittest.main()
