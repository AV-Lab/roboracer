"""Analytical fixtures for the LiDAR scan-convention check (synthetic room, no player)."""
import argparse
import importlib.util
import json
import math
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("autodrive_scan_check", ROOT / "scripts/autodrive_scan_check.py")


def unity_matrix(np, position, yaw_deg=0.0):
    """Unity world transform with a rotation about Unity +y (clockwise seen from above)."""
    a = math.radians(yaw_deg)
    m = np.eye(4)
    m[:3, :3] = [[math.cos(a), 0, math.sin(a)], [0, 1, 0], [-math.sin(a), 0, math.cos(a)]]
    m[:3, 3] = position
    return m


def quad(np, p, q, low, high):
    """Two triangles of a vertical wall from p to q (ROS x/y), z from low to high."""
    a, b = [p[0], p[1], low], [q[0], q[1], low]
    c, d = [q[0], q[1], high], [p[0], p[1], high]
    return np.array([[a, b, c], [a, c, d]], dtype=float)


class ScanCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import numpy as np
        except ImportError:
            raise unittest.SkipTest("NumPy unavailable; run with the analysis interpreter")
        cls.np = np
        cls.scan = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.scan)
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)

    def build(self, name, vehicle_box=True):
        """Asymmetric room in ROS coordinates and a frame measured with the vendor convention."""
        np, scan = self.np, self.scan
        corners = [(-2.0, -1.5), (4.0, -1.5), (4.0, 3.0), (1.0, 3.0), (1.0, 2.0), (-2.0, 2.0)]
        walls = [quad(np, corners[i], corners[(i + 1) % len(corners)], 0.0, 1.0) for i in range(len(corners))]
        triangles = [np.concatenate(walls)]
        colliders = [{"path": "Infrastructure/Room", "type": "MeshCollider", "layer": 0, "enabled": True, "active": True}]
        owners = [np.zeros(len(triangles[0]), dtype=int)]
        # Scene: vehicle facing Unity +z (ROS +x), LiDAR head 0.27 m ahead of the rear axle.
        sensors = {"F1TENTH": unity_matrix(np, [0, 0.01, 0]).tolist(),
                   "F1TENTH/Transforms/Rear Axle Center": unity_matrix(np, [0, 0.06, 0]).tolist(),
                   "F1TENTH/Sensors/LIDAR/Head": unity_matrix(np, [0, 0.156, 0.27]).tolist()}
        ips, yaw = np.array([0.5, 0.3, 0.06]), 0.7
        head = ips + np.array([0.27 * math.cos(yaw), 0.27 * math.sin(yaw), 0.096])
        if vehicle_box:
            # Closed housing around the head at the measured pose: the real raycast ignores it.
            lo, hi = head - 0.03, head + 0.03
            box = [(lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])]
            housing = np.concatenate([quad(np, box[i], box[(i + 1) % 4], lo[2], hi[2]) for i in range(4)])
            triangles.append(housing)
            colliders.append({"path": "F1TENTH/Vehicle/Hokuyo", "type": "MeshCollider", "layer": 0,
                              "enabled": True, "active": True})
            owners.append(np.ones(len(housing), dtype=int))
        n = 1081
        angles = yaw + np.deg2rad(scan.ANGLE_MIN_DEG + scan.RESOLUTION_DEG * np.arange(n))
        directions = np.stack([np.cos(angles), np.sin(angles), np.zeros(n)], axis=1)
        ranges = scan.raycast(head, directions, triangles[0], scan.RANGE_MAX_M)
        text = " ".join("inf" if not math.isfinite(r) else f"{r:.6f}" for r in ranges)
        directory = Path(self.temp.name) / name
        directory.mkdir()
        geometry = directory / "geometry.npz"
        tri = np.concatenate(triangles)
        np.savez_compressed(geometry, triangles=tri, layers=np.zeros(len(tri), dtype=int),
                            owners=np.concatenate(owners))
        geometry.with_suffix(".json").write_text(json.dumps(
            {"colliders": colliders, "sensors_world_unity": sensors, "npz_sha256": "fixture"}))
        frame = directory / "frame.json"
        frame.write_text(json.dumps({"V1 Position": " ".join(f"{v:.6f}" for v in ips),
                                     "V1 Orientation Euler Angles": f"0 0 {yaw}",
                                     "V1 LIDAR Range Array": text}))
        return directory, geometry, frame

    def compare(self, directory, geometry, frame):
        output = directory / "report.json"
        code = self.scan.compare(argparse.Namespace(geometry=geometry, frame=frame, output=output))
        return code, json.loads(output.read_text())

    def test_vendor_convention_selected_despite_enclosing_vehicle_collider(self):
        code, report = self.compare(*self.build("housing"))
        self.assertEqual(code, 0)
        self.assertEqual(report["best"], "convention: ccw from -135 deg, mount from scene")
        self.assertGreater(report["excluded_vehicle_triangles"], 0)
        best = report["hypotheses"][report["best"]]
        self.assertEqual(best["finite_mismatch"], 0)
        self.assertLess(best["abs_error_m_p50_p95_max"][2], 1e-5)
        for name, result in report["hypotheses"].items():
            if name != report["best"]:
                self.assertGreater(result["abs_error_m_p50_p95_max"][1], 0.01, name)

    def test_mount_recovered_from_scene_transforms(self):
        _, report = self.compare(*self.build("mount", vehicle_box=False))
        self.assertAlmostEqual(report["scene_yaw_rad"], 0.0)
        self.np.testing.assert_allclose(report["mount_from_scene_m"], [0.27, 0.0, 0.096], atol=1e-9)

    def test_output_must_be_fresh(self):
        directory, geometry, frame = self.build("fresh", vehicle_box=False)
        self.compare(directory, geometry, frame)
        with self.assertRaises(SystemExit):
            self.compare(directory, geometry, frame)


if __name__ == "__main__":
    unittest.main()
