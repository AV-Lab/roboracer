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

    def test_virtual_obstacle_contact_and_clearance_are_scored_separately(self):
        """S4 (D54 A): a box on the centerline is one obstacle-contact event; wall results are unchanged."""
        from shapely.geometry import box
        frames = frames_along([0.05 * k for k in range(20)])
        plain = rs.score(self.g, frames)
        a = 0.5  # the box sits on the centerline at angle 0.5 rad, which frame 10 passes through
        on_path = box(R_MID * math.cos(a) - 0.1, R_MID * math.sin(a) - 0.1, R_MID * math.cos(a) + 0.1, R_MID * math.sin(a) + 0.1)
        r = rs.score(self.g, frames, [on_path])
        self.assertEqual(1, len(r["obstacle_contact_events"]))
        self.assertEqual(0.0, r["min_obstacle_clearance_m"])
        for key in ("contact_events", "offtrack_events", "min_clearance_m", "laps", "progress_m"):
            self.assertEqual(plain[key], r[key])
        self.assertNotIn("obstacle_contact_events", plain)
        # A box beside the path: no contact, clearance = gap between the box and the footprint's outer side.
        beside = box(2.9 * math.cos(a) - 0.05, 2.9 * math.sin(a) - 0.05, 2.9 * math.cos(a) + 0.05, 2.9 * math.sin(a) + 0.05)
        r = rs.score(self.g, frames, [beside])
        self.assertEqual([], r["obstacle_contact_events"])
        self.assertGreater(r["min_obstacle_clearance_m"], 0.2)
        self.assertLess(r["min_obstacle_clearance_m"], 2.9 - 0.05 - R_MID - 0.145 + 0.01)

    def test_an_obstacle_removed_before_the_car_reaches_it_is_not_contact(self):
        """S4 D63 A rearm-cleared: obstacles count only for frames received before their removal."""
        from shapely.geometry import box
        frames = frames_along([0.05 * k for k in range(20)])  # received_ns = frame index
        a = 0.5  # frame 10 passes through the box
        on_path = box(R_MID * math.cos(a) - 0.1, R_MID * math.sin(a) - 0.1, R_MID * math.cos(a) + 0.1, R_MID * math.sin(a) + 0.1)
        self.assertEqual(1, len(rs.score(self.g, frames, [on_path], obstacles_until_ns=15)["obstacle_contact_events"]))
        removed = rs.score(self.g, frames, [on_path], obstacles_until_ns=5)
        self.assertEqual([], removed["obstacle_contact_events"])
        self.assertGreater(removed["min_obstacle_clearance_m"], 0.0)

    def test_obstacle_fixture_must_match_its_provenance(self):
        import hashlib
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "t1.json"
            fixture.write_text(json.dumps({"schema": "roboracer.virtual-obstacles/1", "name": "t1",
                                           "obstacles": [{"id": "b", "polygon": [[0, 0], [0.2, 0], [0.2, 0.2], [0, 0.2]]}]}))
            provenance = Path(tmp) / "t1.provenance.json"
            provenance.write_text(json.dumps({"fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()}))
            polygons, record = rs.load_obstacles(fixture)
            self.assertEqual((1, "t1"), (len(polygons), record["name"]))
            fixture.write_text(fixture.read_text().replace("0.2", "0.3"))
            with self.assertRaises(SystemExit):
                rs.load_obstacles(fixture)


@unittest.skipIf(rs is None, "shapely unavailable; run with the AVLite interpreter")
class EpisodeTruthTests(unittest.TestCase):
    """SIM1-04: evaluator truth comes from one simulator episode; a reset (new episode) is never mixed in."""

    def write(self, rows):
        import json
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        run = Path(self.tmp.name)
        with open(run / "bridge-frames.jsonl", "w") as f:
            for seq, episode, ips_episode, sim in rows:
                f.write(json.dumps({"motion": {"Position": [1.0, 2.0, 0.06], "Orientation Quaternion": [0, 0, 0, 1]},
                                    "provenance": {"telemetry_seq": seq, "episode": episode,
                                                   "sources": {"ips": {"episode": ips_episode, "sim_time": sim}}},
                                    "received_monotonic_ns": seq}) + "\n")
        return run

    def tearDown(self):
        self.tmp.cleanup()

    def test_single_episode_is_returned_with_its_number(self):
        frames = rs.truth_frames(self.write([(1, 1, 1, 0.2), (2, 1, 1, 0.4)]))
        self.assertEqual([1, 1], [f["episode"] for f in frames])

    def test_two_episodes_are_refused_unless_one_is_selected(self):
        run = self.write([(1, 1, 1, 10.0), (2, 1, 1, 10.2), (3, 2, 2, 0.1), (4, 2, 2, 0.3)])
        with self.assertRaises(ValueError):
            rs.truth_frames(run)
        self.assertEqual([3, 4], [f["telemetry_seq"] for f in rs.truth_frames(run, episode=2)])
        self.assertEqual([1, 2], rs.run_episodes(run))

    def test_ips_sample_from_another_episode_is_refused(self):
        with self.assertRaises(ValueError):
            rs.truth_frames(self.write([(1, 2, 1, 0.1)]))


if __name__ == "__main__":
    unittest.main()
