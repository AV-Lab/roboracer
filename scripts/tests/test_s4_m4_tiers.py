"""S5 D80 A: U3 is tiered by the free gap on the expected passing side."""

import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roboracer_s4_m4 as m4  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[1] / "s4-fixtures"


def judge(gap=None, obstacle=0.27, wall=0.15):
    return {"case": "t2", "checks": {"contact_free_and_on_track": True, "no_abort": True, "icp_valid_while_driving": True,
                                     "one_lap": True, "expected_side": True, "not_blocked": True},
            "min_wall_clearance_m": wall, "min_obstacle_clearance_m": obstacle,
            "icp_error_vs_ips_m": {"p95": 0.02, "max": 0.05}, "stack_tick_ms": {"max": 40.0}, "tick_overruns": 0,
            "laps": [{"lap_time_s": 68.0}],
            "passing_gap": None if gap is None else {"side": "right", "gap_m": gap}}


class GapTierTests(unittest.TestCase):
    def test_full_tier_keeps_u3(self):
        criteria = m4.judge_episode(judge(gap=1.06, obstacle=0.27, wall=0.15))
        self.assertEqual("full", m4.gap_tier(judge(gap=1.06)))
        self.assertFalse(criteria["U3 wall clearance >= 0.2 m"])
        self.assertTrue(criteria["U3 obstacle clearance >= 0.25 m"])

    def test_no_gap_recorded_is_full_tier(self):
        self.assertEqual("full", m4.gap_tier(judge(gap=None)))

    def test_narrow_tier_uses_u3n(self):
        criteria = m4.judge_episode(judge(gap=0.824, obstacle=0.12, wall=0.15))
        self.assertEqual("narrow", m4.gap_tier(judge(gap=0.824)))
        self.assertTrue(all(criteria.values()), criteria)
        criteria = m4.judge_episode(judge(gap=0.824, obstacle=0.09, wall=0.15))
        self.assertFalse(criteria["U3n obstacle clearance >= 0.1 m"])
        criteria = m4.judge_episode(judge(gap=0.824, obstacle=0.2, wall=0.09))
        self.assertFalse(criteria["U3n wall clearance >= 0.1 m"])

    def test_committed_fixtures_fall_in_the_stated_tiers(self):
        expected = {"t1-left-pass": "full", "t2-right-pass": "full", "heldout-h2/t1-left-pass": "full",
                    "heldout-h3/h3-right-pass": "narrow", "heldout-h4/h4-right-pass": "narrow"}
        for name, tier in expected.items():
            prov = json.loads((FIXTURES / f"{name}.provenance.json").read_text())
            side = prov["check"]["expected_corridor"]
            gap = prov["check"]["gaps_m"][f"{side}_m"]
            self.assertEqual(tier, m4.gap_tier({"passing_gap": {"gap_m": gap}}), name)


if __name__ == "__main__":
    unittest.main()
