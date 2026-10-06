"""Recorded-input episode export (S1-05) on a synthetic run directory over the ring fixture."""
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import roboracer_episode as ep
    from test_roboracer_scoring import R_MID, ring_geometry
except ImportError:  # pragma: no cover
    ep = None


def write_run(results: Path, angles, status):
    run = results / "run-01"
    run.mkdir(parents=True)
    with open(run / "bridge-frames.jsonl", "w") as f:
        f.write(json.dumps({"event": "connect"}) + "\n")  # rows without motion are skipped
        for i, a in enumerate(angles):
            yaw = a + math.pi / 2
            f.write(json.dumps({"motion": {"Position": [R_MID * math.cos(a), R_MID * math.sin(a), 0.06],
                                           "Orientation Quaternion": [0, 0, math.sin(yaw / 2), math.cos(yaw / 2)]},
                                "provenance": {"telemetry_seq": i + 1, "sources": {"ips": {"sim_time": 0.2 * i}}},
                                "received_monotonic_ns": i}) + "\n")
    (run / "run.json").write_text(json.dumps({
        "children": [{"label": "player", "argv": [str(results / "AutoDRIVE.x86_64")], "exit_code": 0}],
        "manual_mode_review": {"mode": "Guarded", "note": "reviewed"}, "actions": [{"action": "Connect only"}],
        "provenance": True, "endpoint_released": True}))
    if status is not None:
        (run / "plugin-observer-status.json").write_text(json.dumps(status))
    (results / "result.json").write_text(json.dumps({"tool_sha256": "x"}))


@unittest.skipIf(ep is None, "shapely unavailable; run with the AVLite interpreter")
class EpisodeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.geometry = self.root / "geometry.json"
        self.geometry.write_text(json.dumps(ring_geometry()))

    def tearDown(self):
        self.tmp.cleanup()

    def export(self, angles, status, runner_exit=None):
        write_run(self.root / "results", angles, status)
        out = self.root / "episode"
        episode = ep.export(self.root / "results", self.geometry, out, "recorded", {"argv": []}, runner_exit)
        return episode, json.loads((out / "manifest.json").read_text())

    def test_finished_lap_is_scored_and_manifest_records_manual_initialization(self):
        status = {"stack_profile": "m5", "stage_phase": "finished", "abort": None, "finish_reason": "distance",
                  "precheck": {"passed": True}}
        episode, manifest = self.export([2 * math.pi * k / 60 for k in range(62)], status)
        self.assertEqual({"state": "finished", "reason": "distance"}, episode["outcome"])
        self.assertEqual(1, episode["completed_laps"])
        self.assertTrue(episode["contact_free_and_on_track"])
        init = manifest["initialization"]
        self.assertFalse(init["unattended_reset"])
        self.assertEqual("visual pre-Connect review", init["manual_steps"][0]["step"])
        self.assertEqual({"passed": True}, manifest["start_conditions"]["workspace_precheck"])
        self.assertAlmostEqual(0.0, manifest["start_conditions"]["offset_from_spawn_m"], places=6)
        self.assertFalse(manifest["binaries"]["player"]["exists"])
        for key in ("code", "configuration", "scene", "randomization", "clocks", "provenance", "processes", "host"):
            self.assertIn(key, manifest)

    def test_abort_is_reported_from_the_stack_not_inferred(self):
        status = {"stack_profile": "m5", "stage_phase": "aborted", "abort": "side clearance", "finish_reason": None}
        episode, _ = self.export([0.05 * k for k in range(5)], status)
        self.assertEqual({"state": "aborted", "reason": "side clearance"}, episode["outcome"])

    def test_missing_status_or_runner_failure_is_incomplete(self):
        episode, _ = self.export([0.0, 0.05], None)
        self.assertEqual("incomplete", episode["outcome"]["state"])
        status = {"stage_phase": "finished", "abort": None, "finish_reason": "distance"}
        self.assertEqual("incomplete", ep.outcome(status, {}, 2)["state"])


if __name__ == "__main__":
    unittest.main()
