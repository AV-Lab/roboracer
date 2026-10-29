"""S4 (D54 A): virtual static obstacles at the sensor boundary — ray-cast occlusion, fixture integrity, the
bridge path, and that the driving stack never references the fixture."""

import hashlib
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace as NS
import unittest

import numpy as np

from roboracer.integration import virtual_obstacles as vo
from roboracer.integration.autodrive_observation import LIDAR_MOUNT_M, SCAN_RANGE_MAX_M

from . import s1_02_fixtures as fx

REPO = Path(__file__).resolve().parents[2]
CENTRE_BEAM = 540  # 0 rad, straight ahead


def write_fixture(directory: Path, obstacles, name="test", schema=vo.SCHEMA) -> Path:
    path = Path(directory) / f"{name}.json"
    path.write_text(json.dumps({"schema": schema, "name": name,
                                "obstacles": [{"id": f"o{i}", "polygon": p} for i, p in enumerate(obstacles)]}))
    vo.provenance_path(path).write_text(json.dumps({"fixture_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))
    return path


def box(cx, cy, half=0.125):
    return [[cx - half, cy - half], [cx + half, cy - half], [cx + half, cy + half], [cx - half, cy + half]]


class VirtualObstacleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_box_ahead_cuts_the_centre_beam_at_the_exact_distance(self):
        fixture = vo.load_fixture(write_fixture(self.dir, [box(2.125, 0.0)]))  # near face at x = 2.0
        ranges = np.full(1081, 5.0)
        out = vo.occlude_ranges(fixture, ranges, 0.0, 0.0, 0.0)
        self.assertAlmostEqual(2.0 - LIDAR_MOUNT_M[0], out[CENTRE_BEAM], places=9)
        # The box spans +-0.125 m at 1.7267 m: about +-4.1 deg, i.e. about 33 beams; the rest are unchanged.
        changed = np.flatnonzero(out != ranges)
        self.assertTrue(30 <= len(changed) <= 36, len(changed))
        self.assertEqual(CENTRE_BEAM, int(round(changed.mean())))
        self.assertTrue(np.all(out[changed] < 5.0))

    def test_pose_rotation_and_translation(self):
        """Car at (1, 2) heading +y: a box 2 m further along +y is straight ahead; one along +x is at -90 deg."""
        fixture = vo.load_fixture(write_fixture(self.dir, [box(1.0, 4.125)]))
        out = vo.occlude_ranges(fixture, np.full(1081, 9.0), 1.0, 2.0, math.pi / 2)
        self.assertAlmostEqual(4.0 - (2.0 + LIDAR_MOUNT_M[0]), out[CENTRE_BEAM], places=9)
        side = vo.load_fixture(write_fixture(self.dir, [box(3.125, 2.0 + LIDAR_MOUNT_M[0])], name="side"))
        out = vo.occlude_ranges(side, np.full(1081, 9.0), 1.0, 2.0, math.pi / 2)
        self.assertAlmostEqual(2.0, out[180], places=6)  # beam 180 = -90 deg = the car's right = +x here
        self.assertEqual(9.0, out[CENTRE_BEAM])

    def test_closer_returns_stay_and_no_return_beams_are_filled(self):
        fixture = vo.load_fixture(write_fixture(self.dir, [box(2.125, 0.0)]))
        ranges = np.full(1081, np.inf)
        ranges[CENTRE_BEAM] = 1.0  # a wall closer than the box: the box is hidden behind it
        out = vo.occlude_ranges(fixture, ranges, 0.0, 0.0, 0.0)
        self.assertEqual(1.0, out[CENTRE_BEAM])
        self.assertAlmostEqual(2.0 - LIDAR_MOUNT_M[0], out[CENTRE_BEAM + 1], places=3)
        far = vo.load_fixture(write_fixture(self.dir, [box(SCAN_RANGE_MAX_M + 1.0, 0.0)], name="far"))
        self.assertTrue(np.all(np.isinf(vo.occlude_ranges(far, np.full(1081, np.inf), 0.0, 0.0, 0.0))))

    def test_fixture_integrity_and_validation(self):
        path = write_fixture(self.dir, [box(2.0, 0.0)])
        path.write_text(path.read_text().replace("2.125", "2.225"))  # moved after its provenance was recorded
        with self.assertRaisesRegex(ValueError, "provenance"):
            vo.load_fixture(path)
        with self.assertRaisesRegex(ValueError, "schema"):
            vo.load_fixture(write_fixture(self.dir, [box(2.0, 0.0)], name="schema", schema="other/1"))
        with self.assertRaisesRegex(ValueError, "no area"):
            vo.load_fixture(write_fixture(self.dir, [[[0, 0], [1, 0], [2, 0]]], name="flat"))
        with self.assertRaisesRegex(ValueError, "no obstacles"):
            vo.load_fixture(write_fixture(self.dir, [], name="empty"))

    def test_bridge_applies_the_fixture_to_committed_snapshots_only(self):
        """Through AutoDriveBridge._offer with Devkit-shaped messages: the stack's scan shows the box, the snapshot
        pose is untouched, and the raw message recording keeps the published ranges."""
        from roboracer.integration.autodrive_bridge import AutoDriveBridge
        bridge = AutoDriveBridge()
        # Spawn pose (0.741, 3.158) heading -y: a box whose near face is 1.75 m from the LiDAR origin, straight ahead.
        origin_y = 3.158 - LIDAR_MOUNT_M[0]
        bridge.obstacle_fixture = vo.load_fixture(write_fixture(self.dir, [box(0.741, origin_y - 1.875)]))
        recorded = []
        bridge.message_listener = lambda topic, message, now: recorded.append((topic, message))
        messages, provenance = fx.frame(1)
        for name, message in messages.items():
            bridge._offer(name, message, 0)
        bridge._offer("provenance", NS(data=provenance), 0)
        snapshot = bridge.latest()
        self.assertIsNotNone(snapshot)
        self.assertAlmostEqual(1.75, float(snapshot.scan_ranges[CENTRE_BEAM]), places=3)
        self.assertEqual(5.0, float(snapshot.scan_ranges[0]))
        self.assertEqual((0.741, 3.158), (snapshot.pose.x, snapshot.pose.y))
        points = bridge.get_sensor_frame().get_lidar().points
        self.assertAlmostEqual(1.75, float(np.min(np.hypot(points[:, 0], points[:, 1]))), places=3)
        lidar_raw = [m for t, m in recorded if t == "lidar"][0]
        self.assertEqual(5.0, lidar_raw.ranges[CENTRE_BEAM])
        stats = bridge.statistics()["virtual_obstacles"]
        self.assertEqual((1, 1), (stats["snapshots"], stats["occluded_snapshots"]))
        self.assertEqual("test", stats["fixture"])

    def test_driving_code_never_references_the_fixture(self):
        """Only the bridge (the simulated sensor boundary) and the tests import the fixture module."""
        users = sorted(str(p.relative_to(REPO)) for p in (REPO / "roboracer").rglob("*.py")
                       if "virtual_obstacles" in p.read_text() and "tests" not in p.parts)
        self.assertEqual(["roboracer/integration/autodrive_bridge.py"],
                         users)


if __name__ == "__main__":
    unittest.main()
