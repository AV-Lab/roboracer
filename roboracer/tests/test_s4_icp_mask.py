"""S4 D61 A: map ICP leaves out scan points inside confirmed static obstacles; without obstacles nothing changes."""

import math
import unittest

import numpy as np
from avlite.c10_perception.c11_perception_model import AgentState, EgoState, PerceptionModel

from roboracer.localization.map_icp import OBSTACLE_MASK_MARGIN_M, MapIcpLocalization


class IcpMaskTests(unittest.TestCase):
    def setUp(self):
        self.pm = PerceptionModel(ego_vehicle=EgoState(x=0.0, y=0.0, theta=0.0))
        self.loc = MapIcpLocalization(self.pm)
        self.scan = np.c_[np.arange(0.51, 3.0101, 0.05), np.zeros(51)]  # 0.51..3.01 m: no point exactly on a box edge

    def test_no_obstacles_returns_the_scan_unchanged(self):
        out, masked = self.loc._mask_obstacles(self.scan, 1.0, 2.0, 0.3)
        self.assertIs(out, self.scan)
        self.assertEqual(0, masked)

    def test_points_inside_a_static_box_plus_margin_are_dropped(self):
        # Pose (1, 2) heading +y: base x maps to world +y. A 0.25 m box centred 2 m ahead covers base x 1.875..2.125.
        self.pm.agent_vehicles = [AgentState(x=1.0, y=4.0, theta=0.0, length=0.25, width=0.25, velocity=0.0)]
        out, masked = self.loc._mask_obstacles(self.scan, 1.0, 2.0, math.pi / 2)
        lo, hi = 2.0 - 0.125 - OBSTACLE_MASK_MARGIN_M, 2.0 + 0.125 + OBSTACLE_MASK_MARGIN_M
        expected = np.count_nonzero((self.scan[:, 0] >= lo - 1e-9) & (self.scan[:, 0] <= hi + 1e-9))
        self.assertEqual(expected, masked)
        self.assertEqual(len(self.scan) - expected, len(out))
        self.assertTrue(np.all((out[:, 0] < lo - 1e-9) | (out[:, 0] > hi + 1e-9)))

    def test_moving_agents_are_not_masked_and_box_rotation_is_respected(self):
        self.pm.agent_vehicles = [AgentState(x=2.0, y=0.0, theta=0.0, length=0.25, width=0.25, velocity=1.0)]
        self.assertEqual(0, self.loc._mask_obstacles(self.scan, 0.0, 0.0, 0.0)[1])
        # A long thin box (1.0 x 0.1) across the line: rotated 90 deg it covers only ~0.1 + 2 x margin along the line.
        self.pm.agent_vehicles = [AgentState(x=2.0, y=0.0, theta=math.pi / 2, length=1.0, width=0.1, velocity=0.0)]
        masked = self.loc._mask_obstacles(self.scan, 0.0, 0.0, 0.0)[1]
        self.assertEqual(np.count_nonzero(np.abs(self.scan[:, 0] - 2.0) <= 0.05 + OBSTACLE_MASK_MARGIN_M + 1e-9), masked)


if __name__ == "__main__":
    unittest.main()
