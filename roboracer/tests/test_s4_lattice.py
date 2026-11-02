"""S4 D57/D58: AVLite GreedyLatticePlanner at C0 scale and the latched blocked-track stop."""

import math
from pathlib import Path
import unittest

from avlite.c10_perception.c11_perception_model import AgentState, EgoState, PerceptionModel
from avlite.c20_planning.c21_planning_model import GlobalPlan
from avlite.c20_planning.c29_settings import PlanningSettings

from roboracer.planning import c0_lattice
from roboracer.planning.c0_lattice import C0LatticePlanner

PLAN = Path(__file__).resolve().parents[1] / "data/c0-s3v1-plan.json"
SPAWN = (0.741, 3.158, -math.pi / 2)


class C0LatticeTests(unittest.TestCase):
    def setUp(self):
        self.saved = {name: getattr(PlanningSettings, name) for name in c0_lattice.C0_PLANNING}

    def tearDown(self):
        for name, value in self.saved.items():  # PlanningSettings is process-wide: restore AVLite's defaults
            setattr(PlanningSettings, name, value)

    def planner(self, obstacles=()):
        pm = PerceptionModel(ego_vehicle=EgoState(x=SPAWN[0], y=SPAWN[1], theta=SPAWN[2], velocity=0.5))
        pm.agent_vehicles = list(obstacles)
        planner = C0LatticePlanner(GlobalPlan.from_file(str(PLAN)), pm)
        planner.step(pm.ego_vehicle)
        return planner, pm

    def test_c0_settings_and_ego_box_are_applied(self):
        planner, pm = self.planner()
        for name, (value, reason) in c0_lattice.C0_PLANNING.items():
            self.assertEqual(value, getattr(PlanningSettings, name), name)
            self.assertTrue(reason)
        self.assertEqual(0, PlanningSettings.c28_sample_distribution)  # deterministic replans
        self.assertEqual((c0_lattice.C0_EGO_LENGTH_M, c0_lattice.C0_EGO_WIDTH_M), (pm.ego_vehicle.length, pm.ego_vehicle.width))
        self.assertAlmostEqual(0.288 / 2 + 0.20, PlanningSettings.c28_boundary_clearance)  # D78 A: U3 wall
        self.assertAlmostEqual(0.10, PlanningSettings.c20_collision_safety_margin)  # D57 obstacle corridor
        self.assertFalse(planner._agent_blocks_ahead())  # D78 A: AVLite's overtake mode off

    def test_open_track_is_never_blocked(self):
        planner, pm = self.planner()
        for _ in range(5):
            planner.replan(pm)
        self.assertFalse(planner.blocked)
        self.assertGreater(planner.diagnostics["clear_level0_edges"], 0)
        self.assertGreater(max(planner.get_local_plan().velocity), 0.0)

    def test_full_blockage_latches_after_two_replans_and_reset_clears_it(self):
        # A 2 m wide wall of a box 1.0 m ahead of the spawn (heading -y): no corridor can pass.
        wall = AgentState(x=SPAWN[0], y=SPAWN[1] - 1.5, theta=0.0, length=2.5, width=0.2, velocity=0.0)
        planner, pm = self.planner([wall])
        global_speed_before = list(planner.global_trajectory.velocity)
        planner.replan(pm)
        self.assertFalse(planner.blocked)  # one blocked replan is not enough
        self.assertEqual(1, planner.diagnostics["blocked_streak"])
        planner.replan(pm)
        self.assertTrue(planner.blocked)
        self.assertEqual("no collision-free in-bounds edge", planner.blocked_reason)
        self.assertEqual(0.0, max(planner.get_local_plan().velocity))
        self.assertEqual(global_speed_before, list(planner.global_trajectory.velocity))  # shared trajectory untouched
        pm.agent_vehicles = []  # the blockage disappears: still latched until rearm
        planner.replan(pm)
        self.assertTrue(planner.blocked)
        planner.reset()
        planner.step(pm.ego_vehicle)
        planner.replan(pm)
        self.assertFalse(planner.blocked)
        self.assertGreater(max(planner.get_local_plan().velocity), 0.0)

    def test_stop_distance_guard_latches_at_once_inside_the_envelope(self):
        # D78 A: a full blockage 0.9 m ahead of the pose (front gap ~0.4 m) is inside the 0.76 m stop envelope.
        wall = AgentState(x=SPAWN[0], y=SPAWN[1] - 0.95, theta=0.0, length=2.5, width=0.1, velocity=0.0)
        planner, pm = self.planner([wall])
        self.assertLess(planner._obstacle_gap_on_plan(5.0), planner._stop_envelope_m())
        planner.replan(pm)
        self.assertTrue(planner.blocked)
        self.assertIn("stop-distance guard", planner.blocked_reason)
        self.assertEqual(0.0, max(planner.get_local_plan().velocity))

    def test_no_latch_beside_an_obstacle_the_followed_plan_clears(self):
        # D78 A: a box right beside the car (on the side away from the line). Every fresh edge starts at the car
        # and clips it, but the plan being followed clears it: not blocked.
        box = AgentState(x=SPAWN[0] - 0.29, y=SPAWN[1] - 0.2, theta=math.pi / 2, length=0.5, width=0.1, velocity=0.0)
        planner, pm = self.planner([box])
        for _ in range(4):
            planner.replan(pm)
        self.assertEqual(0, planner.diagnostics["clear_level0_edges"])
        self.assertIsNone(planner.diagnostics["plan_obstacle_gap_m"])
        self.assertFalse(planner.blocked)

    def test_early_avoidance_commits_to_a_lateral_plan_once_the_line_edge_collides(self):
        planner, pm = self.planner()
        planner.replan(pm)  # open track: the committed edge ends on the line
        self.assertLess(abs(planner.selected_local_plan.end.d), PlanningSettings.c28_d0_reference_threshold)
        # A box on the line 2.2 m ahead: the line edge from the car now collides, a lateral edge is clean.
        pm.agent_vehicles = [AgentState(x=SPAWN[0] + 0.17, y=SPAWN[1] - 2.2, theta=0.0, length=0.25, width=0.25,
                                        velocity=0.0)]
        planner.replan(pm)
        self.assertEqual(1, planner.diagnostics["early_avoidance_switches"])
        self.assertGreaterEqual(abs(planner.selected_local_plan.end.d), PlanningSettings.c28_d0_reference_threshold)
        self.assertFalse(planner.selected_local_plan.collision)
        self.assertFalse(planner.blocked)

    def test_a_planner_error_counts_as_blocked(self):
        planner, pm = self.planner()

        def broken(*args, **kwargs):
            raise RuntimeError("injected planning failure")

        planner.lattice.sample_nodes = broken
        planner.replan(pm)
        planner.replan(pm)
        self.assertTrue(planner.blocked)
        self.assertIn("injected planning failure", planner.blocked_reason)
        self.assertEqual(2, planner.diagnostics["replan_errors"])


if __name__ == "__main__":
    unittest.main()
