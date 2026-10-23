"""S3-02: map ICP (extends AVLite LidarLocalization) on a synthetic track: convergence, degeneracy, odometry,
loss, map integrity. No simulator."""

import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from avlite.c10_perception.c11_perception_model import EgoState, PerceptionModel
from avlite.c50_common.c52_world_sensor_datatypes import Lidar, SensorFrame

from roboracer.localization.map_icp import MapIcpLocalization, load_map


def box_rings():
    """A 10 x 4 m rectangle with a 6 x 0.6 m inner block: two 1.7 m wide straights joined by ends."""
    outer = [(-5, -2), (5, -2), (5, 2), (-5, 2)]
    inner = [(-3, -0.3), (3, -0.3), (3, 0.3), (-3, 0.3)]
    return [outer, inner]


def sample(rings, spacing=0.02):
    pts = []
    for ring in rings:
        for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
            n = max(1, int(math.hypot(x1 - x0, y1 - y0) / spacing))
            pts += [(x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n) for i in range(n)]
    return np.asarray(pts)


def raycast(rings, pose, beams=720, max_range=10.0):
    """2D scan (sensor = body frame) at pose (x, y, theta) against the ring segments."""
    x, y, th = pose
    segs = [(a, b) for ring in rings for a, b in zip(ring, ring[1:] + ring[:1])]
    points = []
    for k in range(beams):
        a = th - math.radians(135) + math.radians(270) * k / (beams - 1)
        dx, dy = math.cos(a), math.sin(a)
        best = max_range
        for (x0, y0), (x1, y1) in segs:
            ex, ey = x1 - x0, y1 - y0
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            t = ((x0 - x) * ey - (y0 - y) * ex) / den
            u = ((x0 - x) * dy - (y0 - y) * dx) / den
            if t > 0 and 0 <= u <= 1:
                best = min(best, t)
        if best < max_range:
            rel = a - th
            points.append((best * math.cos(rel), best * math.sin(rel), 0.0, 0.0))
    return np.asarray(points)


class MapIcpTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.rings = box_rings()
        self.map_file = Path(self.tmp.name) / "map.json"
        self.map_file.write_text(json.dumps({"points": sample(self.rings).tolist()}))
        self.record = Path(self.tmp.name) / "map.provenance.json"
        self.record.write_text(json.dumps({"map_sha256": hashlib.sha256(self.map_file.read_bytes()).hexdigest()}))

    def tearDown(self):
        self.tmp.cleanup()

    def use_rings(self, rings):
        self.rings = rings
        self.map_file.write_text(json.dumps({"points": sample(rings).tolist()}))
        self.record.write_text(json.dumps({"map_sha256": hashlib.sha256(self.map_file.read_bytes()).hexdigest()}))

    def localizer(self, **kw):
        pm = PerceptionModel(ego_vehicle=EgoState())
        return MapIcpLocalization(pm, map_file=self.map_file, provenance_file=self.record, **kw), pm

    def frame(self, pose, stamp):
        lidar = Lidar(sensor_name="lidar", points=raycast(self.rings, pose), stamp=stamp)
        return SensorFrame(lidars={"lidar": lidar}, primary_lidar_name="lidar", stamp=stamp, frame_id="base_link")

    def test_nothing_before_configuration_initialization(self):
        loc, pm = self.localizer()
        loc.localize(pm, self.frame((0, -1.15, 0), 1.0))
        self.assertEqual("uninitialized", loc.status["state"])

    def test_converges_from_a_small_offset_at_an_end(self):
        loc, pm = self.localizer()
        loc.initialize(4.0 + 0.08, 1.0 - 0.05, math.pi / 2 + 0.05)
        loc.localize(pm, self.frame((4.0, 1.0, math.pi / 2), 1.0))
        self.assertEqual("valid", loc.status["state"], loc.status)
        self.assertLess(math.hypot(pm.ego_vehicle.x - 4.0, pm.ego_vehicle.y - 1.0), 0.01)
        self.assertLess(abs(pm.ego_vehicle.theta - math.pi / 2), 0.01)

    def test_corridor_is_degenerate_and_odometry_carries_along_track_motion(self):
        # 50 m corridor, 1.7 m wide: its ends are beyond the 10 m scan range, so nothing constrains x.
        self.use_rings([[(-25, -2), (25, -2), (25, 2), (-25, 2)], [(-23, -0.3), (23, -0.3), (23, 0.3), (-23, 0.3)]])
        loc, pm = self.localizer()
        x, y = -2.0, -1.15
        loc.initialize(x, y, 0.0)
        for k in range(1, 8):
            loc.add_odometry(0.2)  # the car moves 0.2 m along +x between scans
            loc.localize(pm, self.frame((x + 0.2 * k, y, 0.0), float(k)))
            self.assertEqual("valid", loc.status["state"], loc.status)
        self.assertTrue(loc.status["degenerate"], loc.status["constraint_ratio"])
        self.assertLess(abs(pm.ego_vehicle.x - (x + 1.4)), 0.02)
        without, pm2 = self.localizer()
        without.initialize(x, y, 0.0)
        for k in range(1, 8):  # no odometry: the estimate cannot follow along the corridor
            without.localize(pm2, self.frame((x + 0.2 * k, y, 0.0), float(k)))
        self.assertGreater(abs(pm2.ego_vehicle.x - (x + 1.4)), 0.5)

    def test_wrong_place_is_reported_and_loss_is_sticky(self):
        loc, pm = self.localizer(loss_after=3)
        loc.initialize(-2.0, -1.15, 0.0)
        other = [[(-1, -1), (1, -1), (1, 1), (-1, 1)]]  # the scan comes from a different, small room
        for k in range(4):
            lidar = Lidar(sensor_name="lidar", points=raycast(other, (0, 0, 0)), stamp=float(k))
            loc.localize(pm, SensorFrame(lidars={"lidar": lidar}, primary_lidar_name="lidar", stamp=float(k),
                                         frame_id="base_link"))
        self.assertEqual("lost", loc.status["state"])
        loc.localize(pm, self.frame((-2.0, -1.15, 0.0), 9.0))  # even a good scan does not clear a loss
        self.assertEqual("lost", loc.status["state"])
        loc.initialize(-2.0, -1.15, 0.0)  # only operator/configuration reinitialization does
        loc.localize(pm, self.frame((-2.0, -1.15, 0.0), 10.0))
        self.assertEqual("valid", loc.status["state"])

    def test_tampered_map_is_refused(self):
        self.map_file.write_text(self.map_file.read_text().replace("-5", "-6", 1))
        with self.assertRaises(ValueError):
            load_map(self.map_file, self.record)

    def test_committed_c0_map_loads(self):
        points, digest = load_map()
        self.assertEqual(3152, len(points))
        self.assertEqual(64, len(digest))


if __name__ == "__main__":
    unittest.main()
