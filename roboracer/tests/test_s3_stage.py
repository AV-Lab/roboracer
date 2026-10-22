"""S3 stage s3b (B bring-up, D32 A): plan file integrity, factory assembly and the unchanged M6 envelope."""

import json
from pathlib import Path
import shutil
import tempfile
import unittest

from roboracer.planning import s3b
from roboracer.runtime.supervisor_core import AVLITE_STAGES
from roboracer.runtime.supervisor_process import check_confirmation

from .test_s1_01_plugin import probe

REPO = Path(__file__).resolve().parents[2]


class S3bStageTests(unittest.TestCase):
    def test_committed_plan_loads_and_matches_its_provenance(self):
        tracker, info = s3b.load_plan()
        self.assertEqual(info["points"], 313)
        self.assertAlmostEqual(info["lap_m"], 31.25, delta=0.05)
        self.assertLessEqual(info["max_speed_mps"], 0.3)
        self.assertTrue(tracker.is_initialized)
        provenance = json.loads(s3b.PROVENANCE_FILE.read_text())
        self.assertGreaterEqual(provenance["report"]["min_polyline_clearance_m"], 0.28)

    def test_tampered_plan_is_refused(self):
        with tempfile.TemporaryDirectory() as scratch:
            plan, record = Path(scratch) / "plan.json", Path(scratch) / "plan.provenance.json"
            shutil.copy(s3b.PLAN_FILE, plan)
            shutil.copy(s3b.PROVENANCE_FILE, record)
            payload = json.loads(plan.read_text())
            payload["ReferenceSpeed"][5] = 3.0
            plan.write_text(json.dumps(payload) + "\n")
            with self.assertRaises(ValueError):
                s3b.load_plan(plan, record)

    def test_controller_config_stays_inside_the_m6_envelope(self):
        cfg = s3b.controller_config()
        self.assertEqual(AVLITE_STAGES["s3b"], AVLITE_STAGES["m6"])
        self.assertLessEqual(cfg.speed_cap_mps, AVLITE_STAGES["m6"]["max_speed_mps"])
        self.assertLessEqual(cfg.max_wheel_angle_rad, AVLITE_STAGES["m6"]["max_steer_rad"])
        self.assertEqual(cfg.mpc_lateral_mode, "apply")

    def test_supervisor_refuses_s3b_until_approved(self):
        record = json.loads((REPO / "docs/planning/s1-motion-approval.json").read_text())
        expected = "S3B" in record.get("stages", [])
        self.assertEqual(check_confirmation(str(REPO / "docs/planning/s1-motion-approval.json"), "s3b") is not None,
                         expected)

    def test_factory_assembles_s3b(self):
        r = probe("factory_s3b")
        self.assertEqual(r["controller"], "RacingLineController")
        self.assertEqual(r["global_planner"], "RaceLineGlobalPlanner")
        self.assertTrue(r["same_plan"])
        self.assertEqual(r["plan"]["points"], 313)
        self.assertEqual(r["config"], {"speed_cap_mps": 0.3, "max_wheel_angle_rad": 0.35, "mpc_lateral_mode": "apply"})
        self.assertEqual(r["disabled"]["reason"], "disabled")
        # Without telemetry the ego sits at the origin, far off the line: B safe-stops (target 0).
        self.assertEqual(r["enabled_last"]["target_speed"], 0.0)
        self.assertTrue(r["enabled_last"]["safe_stop"])
        self.assertEqual(r["last_request"]["target_speed"], 0.0)


if __name__ == "__main__":
    unittest.main()
