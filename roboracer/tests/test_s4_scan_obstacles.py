"""S4-01 (D56): ScanObstacleDetection -- wall subtraction, quality, 2-scan confirmation, face-on depth, stamps."""

import math
import unittest

import numpy as np
from avlite.c10_perception.c11_perception_model import EgoState, PerceptionModel
from avlite.c50_common.c52_world_sensor_datatypes import Lidar, SensorFrame

from roboracer.integration.autodrive_observation import LIDAR_MOUNT_M, translation
from roboracer.localization.map_icp import load_map
from roboracer.perception.scan_obstacles import ScanObstacleDetection

SPAWN = (0.741, 3.158, -math.pi / 2)


def frame(points_map_xy, stamp, ego):
    """A sensor frame whose LiDAR points land on ``points_map_xy`` for the stack pose ``ego`` (inverse to_map)."""
    lidar = Lidar(sensor_name="lidar", base_to_sensor=translation(LIDAR_MOUNT_M), stamp=stamp)
    world_to_sensor = np.linalg.inv(ego.pose_matrix() @ lidar.base_to_sensor)
    xyz = np.c_[np.asarray(points_map_xy, dtype=float), np.full(len(points_map_xy), 0.096 + 0.0)]
    local = (np.c_[xyz, np.ones(len(xyz))] @ world_to_sensor.T)[:, :3]
    lidar.points = np.c_[local, np.zeros(len(local))].astype(np.float32)
    return SensorFrame(lidars={"lidar": lidar}, primary_lidar_name="lidar", stamp=stamp, frame_id="base_link")


def face(cx, cy, half=0.125, n=30):
    """The face of a box towards the spawn (heading -y): a segment across the track at y = cy + 0 (near side)."""
    return [(cx - half + 2 * half * i / (n - 1), cy) for i in range(n)]


class ScanObstacleTests(unittest.TestCase):
    def setUp(self):
        self.detector = ScanObstacleDetection()
        self.ego = EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2])
        self.pm = PerceptionModel(ego_vehicle=self.ego)
        walls, _ = load_map()
        near = np.hypot(walls[:, 0] - SPAWN[0], walls[:, 1] - SPAWN[1]) < 4.0
        self.walls = [tuple(p) for p in walls[near]]

    def test_wall_points_are_not_obstacles(self):
        self.detector.detect(self.pm, frame(self.walls, 1.0, self.ego))
        self.detector.detect(self.pm, frame(self.walls, 1.2, self.ego))
        self.assertEqual([], self.pm.agent_vehicles)
        self.assertEqual(0, self.detector.status["free_points"])
        self.assertEqual(len(self.walls), self.detector.status["wall_points"])

    def test_a_box_is_confirmed_on_the_second_scan_with_its_stamp(self):
        box = face(SPAWN[0], SPAWN[1] - 2.0)
        self.detector.detect(self.pm, frame(self.walls + box, 1.0, self.ego))
        self.assertEqual(1, self.detector.status["candidates"])
        self.assertEqual([], self.pm.agent_vehicles)  # not yet confirmed
        self.detector.detect(self.pm, frame(self.walls + box, 1.2, self.ego))
        self.assertEqual(1, len(self.pm.agent_vehicles))
        self.assertEqual(1.2, self.detector.obstacles_stamp)
        agent = self.pm.agent_vehicles[0]
        self.assertEqual(0.0, agent.velocity)
        # Seen face-on: the 0.25 m face is kept and the unseen depth defaults to 0.25 m, behind the face.
        self.assertAlmostEqual(0.25, max(agent.length, agent.width), delta=0.01)
        self.assertAlmostEqual(0.25, min(agent.length, agent.width), delta=1e-9)
        self.assertAlmostEqual(SPAWN[1] - 2.0 - 0.125, agent.y, delta=0.01)
        self.assertAlmostEqual(SPAWN[0], agent.x, delta=0.01)

    def test_same_scan_is_processed_once_and_small_clusters_are_dropped(self):
        box = face(SPAWN[0], SPAWN[1] - 2.0)
        self.detector.detect(self.pm, frame(self.walls + box, 1.0, self.ego))
        self.detector.detect(self.pm, frame(self.walls + box, 1.0, self.ego))  # same stamp: not a second scan
        self.assertEqual([], self.pm.agent_vehicles)
        self.assertEqual(1, self.detector.status["scans"])
        tiny = face(SPAWN[0], SPAWN[1] - 2.0, n=3)  # 3 points < min_points
        self.detector.detect(self.pm, frame(self.walls + tiny, 2.0, self.ego))
        self.detector.detect(self.pm, frame(self.walls + tiny, 2.2, self.ego))
        self.assertEqual([], self.pm.agent_vehicles)

    def test_a_moved_cluster_is_not_confirmed(self):
        self.detector.detect(self.pm, frame(self.walls + face(SPAWN[0], SPAWN[1] - 2.0), 1.0, self.ego))
        self.detector.detect(self.pm, frame(self.walls + face(SPAWN[0], SPAWN[1] - 2.5), 1.2, self.ego))  # 0.5 m away
        self.assertEqual([], self.pm.agent_vehicles)


if __name__ == "__main__":
    unittest.main()
