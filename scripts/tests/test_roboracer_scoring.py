"""Analytical fixtures for the independent C0 scorer (S1-05): a synthetic ring track."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from shapely.geometry import Point
    import roboracer_scoring as rs
except ImportError:  # pragma: no cover
    rs = None

R_IN, R_OUT, R_MID = 1.5, 3.0, 2.25
FOOTPRINT = {"x_min": -0.1, "x_max": 0.42, "y_min": -0.145, "y_max": 0.145}


def ring_geometry():
    """Annulus 1.5..3.0 m; walls 0.2 m thick on both sides; centerline CCW from angle 0."""
    region = Point(0, 0).buffer(R_OUT, 256).difference(Point(0, 0).buffer(R_IN, 256))
    walls = Point(0, 0).buffer(R_OUT + 0.2, 256).difference(Point(0, 0).buffer(R_OUT, 256)).union(
        Point(0, 0).buffer(R_IN, 256).difference(Point(0, 0).buffer(R_IN - 0.2, 256)))
    n = 2000
    centerline = [[R_MID * math.cos(2 * math.pi * k / n), R_MID * math.sin(2 * math.pi * k / n)] for k in range(n)]
    length = 2 * math.pi * R_MID
    return {"region_wkt": region.wkt, "walls_wkt": walls.wkt, "centerline": centerline, "length_m": length,
            "footprint": FOOTPRINT, "spawn": {"xy": [R_MID, 0.0], "yaw": math.pi / 2}, "gates": [0.25, 0.5, 0.75]}


def frames_along(angles, radius=R_MID, dt=0.2):
    out = []
    for i, a in enumerate(angles):
        out.append({"sim_time": i * dt, "x": radius * math.cos(a), "y": radius * math.sin(a), "yaw": a + math.pi / 2,
                    "telemetry_seq": i + 1, "received_ns": i})
    return out


@unittest.skipIf(rs is None, "shapely unavailable; run with the AVLite interpreter")
class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.g = ring_geometry()

    def test_one_full_lap_counts_once_with_time(self):
        angles = [2 * math.pi * k / 60 for k in range(62)]  # a little past one lap
        r = rs.score(self.g, frames_along(angles))
        self.assertEqual(1, len(r["laps"]))
        # Laps are detected at frame resolution: within one 0.2 s frame of the exact 12 s.
        self.assertAlmostEqual(60 * 0.2, r["laps"][0]["lap_time_s"], delta=0.2 + 1e-6)
        self.assertEqual([], r["contact_events"])
        self.assertEqual([], r["offtrack_events"])
        # Closest point: the front-outer footprint corner to the outer wall.
        self.assertAlmostEqual(R_OUT - math.hypot(R_MID + 0.145, 0.42), r["min_clearance_m"], delta=0.005)

    def test_oscillation_across_the_start_line_is_not_a_lap(self):
        angles = [(-0.3 if k % 2 else 0.3) for k in range(200)]
        r = rs.score(self.g, frames_along(angles))
        self.assertEqual([], r["laps"])
        self.assertLess(abs(r["progress_m"]), 2 * 0.3 * R_MID + 1e-3)  # polygonal centerline tolerance

    def test_reverse_lap_is_not_a_lap(self):
        r = rs.score(self.g, frames_along([-2 * math.pi * k / 60 for k in range(62)]))
        self.assertEqual([], r["laps"])
        self.assertLess(r["progress_m"], -self.g["length_m"] * 0.9)

    def test_one_and_a_half_laps_counts_one(self):
        r = rs.score(self.g, frames_along([2 * math.pi * k / 60 for k in range(91)]))
        self.assertEqual(1, len(r["laps"]))
        self.assertAlmostEqual(1.5 * self.g["length_m"], r["progress_m"], delta=0.3)

    def test_wall_contact_is_one_deduplicated_event_with_duration(self):
        frames = frames_along([0.05 * k for k in range(10)])
        for i in (4, 5, 6):  # drift outwards into the outer wall for three frames
            a = 0.05 * i
            frames[i].update(x=2.95 * math.cos(a), y=2.95 * math.sin(a))
        r = rs.score(self.g, frames)
        self.assertEqual(1, len(r["contact_events"]))
        self.assertGreaterEqual(r["contact_events"][0]["duration_s"], 0.4 - 1e-9)
        self.assertEqual(1, len(r["offtrack_events"]))

    def test_swept_footprint_catches_a_crossing_between_frames(self):
        # Two frames on the centerline either side of a jump through the inner wall's region.
        frames = frames_along([0.0, 0.0])
        frames[1].update(x=-R_MID, y=0.0, yaw=-math.pi / 2)  # straight across the infield
        r = rs.score(self.g, frames)
        self.assertEqual(1, len(r["contact_events"]))


if __name__ == "__main__":
    unittest.main()
