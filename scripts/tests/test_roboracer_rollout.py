"""2D LiDAR cast and rollout plumbing for the offline lap check (S1-05) on the ring fixture."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from shapely import wkt
    import roboracer_rollout as ro
    from test_roboracer_scoring import R_IN, R_MID, R_OUT, ring_geometry
except ImportError:  # pragma: no cover
    ro = None


@unittest.skipIf(ro is None, "shapely unavailable; run with the AVLite interpreter")
class CastTests(unittest.TestCase):
    def setUp(self):
        self.g = ring_geometry()
        self.segments = ro.wall_segments(wkt.loads(self.g["walls_wkt"]))

    def test_side_and_forward_ranges_from_the_mount(self):
        ranges = ro.cast(self.segments, R_MID, 0.0, math.pi / 2)  # heading +y, inner wall on the left
        mount_y = ro.LIDAR_MOUNT_X
        left = ranges[int(round((90 + 135) / 0.25))]
        right = ranges[int(round((-90 + 135) / 0.25))]
        self.assertAlmostEqual(R_MID - math.sqrt(R_IN ** 2 - mount_y ** 2), left, delta=0.005)
        self.assertAlmostEqual(math.sqrt(R_OUT ** 2 - mount_y ** 2) - R_MID, right, delta=0.005)
        self.assertTrue(all(math.isfinite(r) for r in ranges))

    def test_constant_command_policy_drives_forward_without_contact(self):
        # A fixed-curvature policy matching the ring: steer = atan(L / R_MID), slow speed.
        steer = math.atan(ro.WHEELBASE / R_MID)
        r = ro.rollout(self.g, lambda pts: (0.2, steer, {}), 0.35, max_time_s=20.0, distance_m=3.0)
        self.assertEqual({"state": "finished", "reason": "distance"}, {k: r["end"][k] for k in ("state", "reason")})
        self.assertEqual([], r["score"]["contact_events"])
        self.assertGreater(r["score"]["progress_m"], 2.5)

    def test_requested_steer_above_the_limit_aborts(self):
        r = ro.rollout(self.g, lambda pts: (0.2, 0.4, {}), 0.35, max_time_s=5.0, distance_m=3.0)
        self.assertEqual("abort", r["end"]["state"])
        self.assertIn("requested steer", r["end"]["reason"])


if __name__ == "__main__":
    unittest.main()
