"""S3 (D31): the ported A2RL planning and control code against the A2RL originals, and C0 plan checks.

The equivalence tests load the A2RL plugin (AV-Lab/a2rl dev 0b5cfa8) from a clean export and skip
when it is absent; set ``ROBORACER_A2RL_SOURCE`` to use another export of that commit.
"""

from __future__ import annotations

import importlib
import json
import math
import os
from pathlib import Path
import sys
import types
import unittest

import numpy as np

from avlite.c10_perception.c11_perception_model import EgoState

from roboracer.control.lateral_mpc import LateralMpc, LateralMpcConfig
from roboracer.control.racing_controller import RacingControllerConfig, RacingLineController
from roboracer.planning import racing_line, velocity_profile
from roboracer.planning.trajectory_tracker import LapTrajectoryTracker

A2RL_SOURCE = Path(os.environ.get("ROBORACER_A2RL_SOURCE", "/home/a2rl/roboracer-work/a2rl-dev-0b5cfa8"))
A2RL_COMMIT = "0b5cfa8ee552b3f4b257b887b325c6a3ff4dd3cd"
C0_GEOMETRY = Path("/home/a2rl/Workspace/roboracer/artifacts/s1/20261006T051902Z-s1-05/c0-geometry.json")


def a2rl(module: str):
    """Import ``module`` from the A2RL export as package ``a2rl_ref`` without running the plugin's
    top-level ``__init__`` (which registers it with AVLite)."""
    if "a2rl_ref" not in sys.modules:
        package = types.ModuleType("a2rl_ref")
        package.__path__ = [str(A2RL_SOURCE)]
        sys.modules["a2rl_ref"] = package
    return importlib.import_module("a2rl_ref." + module)


def a2rl_available() -> bool:
    commit = A2RL_SOURCE / "SOURCE_COMMIT"
    return commit.exists() and commit.read_text().strip() == A2RL_COMMIT


def stadium(radius=1.5, straight=3.0, spacing=0.1):
    """Closed stadium centerline (counter-clockwise), last point == first."""
    pts = []
    n_arc = int(math.pi * radius / spacing)
    n_str = int(straight / spacing)
    for i in range(n_str):
        pts.append((i * spacing, -radius))
    for i in range(n_arc):
        a = -math.pi / 2 + math.pi * i / n_arc
        pts.append((straight + radius * math.cos(a), radius * math.sin(a)))
    for i in range(n_str):
        pts.append((straight - i * spacing, radius))
    for i in range(n_arc):
        a = math.pi / 2 + math.pi * i / n_arc
        pts.append((radius * math.cos(a), radius * math.sin(a)))
    pts.append(pts[0])
    return pts


PROFILE = dict(top_speed_mps=3.0, min_speed_mps=0.3, lateral_accel_mps2=3.0, brake_decel_mps2=2.0,
               accel_limit_mps2=1.5, curvature_window_m=0.4, curvature_hold_m=0.5, friction_ellipse=True,
               friction_ellipse_lookahead_m=0.5, peak_lateral_accel_mps2=3.5, peak_curvature_window_m=0.2)


@unittest.skipUnless(a2rl_available(), "A2RL dev 0b5cfa8 export not available")
class PortEquivalenceTests(unittest.TestCase):
    def test_velocity_profile_identical(self):
        ref = a2rl("planning.velocity_profile")
        path = stadium()
        ours = velocity_profile.build_friction_limited_velocity_profile(path, velocity_profile.VelocityProfileConfig(**PROFILE))
        theirs = ref.build_friction_limited_velocity_profile(
            path, ref.VelocityProfileConfig(**PROFILE, local_speed_caps=(), local_speed_floors=()))
        self.assertEqual(ours, theirs)
        for window, hold in ((0.4, 0.5), (0.2, 0.0)):
            self.assertEqual(velocity_profile.build_path_curvature_envelope(path, curvature_window_m=window, curvature_hold_m=hold),
                             ref.build_path_curvature_envelope(path, curvature_window_m=window, curvature_hold_m=hold))
        self.assertEqual(velocity_profile.estimate_profile_time_sec(path, ours), ref.estimate_profile_time_sec(path, theirs))

    def test_min_curvature_line_identical(self):
        ref = a2rl("planning.racing_line")
        path = stadium()
        left, right = [0.6] * len(path), [-0.6] * len(path)
        kwargs = dict(boundary_margin_m=0.3, pinned_offsets={0: (-0.05, 0.05)}, reweight_iterations=2, reweight_window_m=0.4)
        ours = racing_line.generate_min_curvature_racing_line_candidate(path, left, right, **kwargs)
        theirs = ref.generate_min_curvature_racing_line_candidate(path, left, right, **kwargs)
        self.assertEqual(ours["offset_d_m"], theirs["offset_d_m"])
        self.assertEqual(ours["candidate_path"], theirs["candidate_path"])

    def test_tracker_projection_identical(self):
        ref = a2rl("planning.trajectory_tracker")
        path = stadium()
        speed = [1.0] * len(path)
        ours, theirs = LapTrajectoryTracker(path=path, velocity=speed), ref.A2RLTrajectoryTracker(path=path, velocity=speed)
        points = [(0.05, -1.45), (4.4, 0.3), (-0.02, -1.6), (2.0, 1.4)]
        np.testing.assert_array_equal(ours.convert_xy_path_to_sd_path_np(points), theirs.convert_xy_path_to_sd_path_np(points))
        for x, y in points:
            ours.update_waypoint_by_xy(x, y)
            theirs.update_waypoint_by_xy(x, y)
            self.assertEqual((ours.current_wp, ours.next_wp), (theirs.current_wp, theirs.next_wp))

    def test_lateral_mpc_identical(self):
        ref = a2rl("control.lateral_mpc")
        fields = dict(horizon_steps=15, dt_s=0.1, wheelbase_m=0.324, steer_lag_s=0.08, q_lateral=91.5,
                      q_heading=10.0, r_feedforward=20.0, r_rate=200.0, max_wheel_angle_rad=0.5236,
                      understeer_gradient_s2pm=0.0)
        ours, theirs = LateralMpc(LateralMpcConfig(**fields)), ref.LateralMpc(ref.LateralMpcConfig(**fields))
        rng = np.random.default_rng(3)
        for _ in range(20):
            args = (float(rng.uniform(0.1, 3.0)), float(rng.normal(0, 0.1)), float(rng.normal(0, 0.1)),
                    float(rng.normal(0, 0.1)), float(rng.normal(0, 0.1)), list(rng.normal(0, 0.5, 15)))
            self.assertEqual(ours.solve(*args), theirs.solve(*args))
            steps = [(0.1, float(rng.normal(0, 0.2)), float(rng.normal(0, 0.5))) for _ in range(3)]
            self.assertEqual(ours.advance(args[0], args[1], args[2], steps), theirs.advance(args[0], args[1], args[2], steps))

    def test_controller_steering_identical(self):
        """The ported lateral chain (feedback + MPC apply) gives A2RL's steering on the same path, egos and config."""
        ref = a2rl("control.base_stack_controller")
        path = stadium()
        ours_cfg = RacingControllerConfig(mpc_lateral_mode="apply", lat_ff_preview_time_s=0.2, steer_excess_limit_rad=0.3,
                                          mpc_slide_blend_start_rad=0.05, speed_cap_mps=10.0)
        theirs_cfg = ref._BaseStackConfig(
            wheelbase_m=ours_cfg.wheelbase_m, rear_axle_to_cg_m=ours_cfg.rear_axle_to_cg_m,
            max_wheel_angle_rad=ours_cfg.max_wheel_angle_rad, kp_steer_fb=ours_cfg.kp_steer_fb,
            lookahead_distance_yaw_m=ours_cfg.lookahead_distance_yaw_m, lat_ff_preview_time_s=0.2,
            steer_excess_limit_rad=0.3, mpc_lateral_mode="apply", mpc_horizon_steps=ours_cfg.mpc_horizon_steps,
            mpc_dt_s=ours_cfg.mpc_dt_s, mpc_steer_lag_s=ours_cfg.mpc_steer_lag_s, mpc_q_lateral=ours_cfg.mpc_q_lateral,
            mpc_q_heading=ours_cfg.mpc_q_heading, mpc_r_feedforward=ours_cfg.mpc_r_feedforward,
            mpc_r_rate=ours_cfg.mpc_r_rate, mpc_delay_s=ours_cfg.mpc_delay_s, mpc_slide_blend_start_rad=0.05,
            tracking_safe_stop_min_speed_threshold_mps=100.0)
        ours = RacingLineController(config=ours_cfg)
        theirs = ref.A2RLBaseStackController(config=theirs_cfg)
        tj_ours = LapTrajectoryTracker(path=path, velocity=[1.0] * len(path))
        tj_theirs = ref.A2RLTrajectoryTracker(path=path, velocity=[1.0] * len(path)) if hasattr(ref, "A2RLTrajectoryTracker") \
            else a2rl("planning.trajectory_tracker").A2RLTrajectoryTracker(path=path, velocity=[1.0] * len(path))
        ours.config.tracking_safe_stop_min_speed_mps = 100.0  # safe stop off on both sides (A2RL threshold above)
        for k in range(40):
            s = 0.1 * k
            ego = EgoState(x=s + 0.02 * math.sin(k), y=-1.5 + 0.05 * math.cos(0.3 * k), theta=0.03 * math.sin(0.5 * k),
                           velocity=1.0)
            got = ours.control(ego, tj_ours, control_dt=0.1)
            want = theirs.control(ego, tj_theirs, control_dt=0.1)
            self.assertEqual(got.steer, want.steer, f"step {k}")

    def test_safe_stop_steering_identical_and_latched(self):
        ref = a2rl("control.base_stack_controller")
        path = stadium()
        ours_cfg = RacingControllerConfig(tracking_safe_stop_min_speed_mps=0.5)
        theirs_cfg = ref._BaseStackConfig(
            wheelbase_m=ours_cfg.wheelbase_m, rear_axle_to_cg_m=ours_cfg.rear_axle_to_cg_m,
            max_wheel_angle_rad=ours_cfg.max_wheel_angle_rad, kp_steer_fb=ours_cfg.kp_steer_fb,
            lookahead_distance_yaw_m=ours_cfg.lookahead_distance_yaw_m, tracking_safe_stop_min_speed_threshold_mps=0.5,
            safe_stop_lateral_error_threshold_m=ours_cfg.safe_stop_lateral_error_m,
            safe_stop_yaw_error_threshold_rad=ours_cfg.safe_stop_yaw_error_rad)
        ours, theirs = RacingLineController(config=ours_cfg), ref.A2RLBaseStackController(config=theirs_cfg)
        tracker = a2rl("planning.trajectory_tracker").A2RLTrajectoryTracker
        tj_ours, tj_theirs = (LapTrajectoryTracker(path=path, velocity=[1.0] * len(path)),
                              tracker(path=path, velocity=[1.0] * len(path)))
        ego = EgoState(x=1.0, y=-1.5, theta=0.3, velocity=1.0)  # yaw error 0.3 rad > 0.2
        got = ours.control(ego, tj_ours, control_dt=0.1)
        want = theirs.control(ego, tj_theirs, control_dt=0.1)
        self.assertEqual(theirs.debug.get("safe_stop_reason"), "yaw_error")
        self.assertEqual(ours.safe_stop_reason, "yaw_error")
        self.assertEqual((got.target_speed, got.steer), (0.0, want.steer))
        calm = EgoState(x=1.2, y=-1.5, theta=0.0, velocity=1.0)
        self.assertEqual(ours.control(calm, tj_ours, control_dt=0.1).target_speed, 0.0)  # latched
        ours.reset()
        self.assertGreater(ours.control(calm, tj_ours, control_dt=0.1).target_speed, 0.0)


class C0PlanTests(unittest.TestCase):
    def test_stadium_line_inside_margin_and_profile_limits(self):
        path = stadium()
        left, right = [0.6] * len(path), [-0.6] * len(path)
        line = racing_line.generate_min_curvature_racing_line_candidate(path, left, right, boundary_margin_m=0.3)
        self.assertTrue(line["optimizer_converged"])
        self.assertTrue(all(-0.3 - 1e-9 <= d <= 0.3 + 1e-9 for d in line["offset_d_m"]))
        cfg = velocity_profile.VelocityProfileConfig(**PROFILE)
        race = line["candidate_path"]
        speed = velocity_profile.build_friction_limited_velocity_profile(race, cfg)
        curvature = velocity_profile.build_path_curvature_envelope(race, curvature_window_m=0.4, curvature_hold_m=0.5)
        for v, k in zip(speed, curvature):
            self.assertLessEqual(v, cfg.top_speed_mps + 1e-9)
            self.assertGreaterEqual(v, cfg.min_speed_mps - 1e-9)
            if k > 1e-6:
                self.assertLessEqual(v * v * k, cfg.lateral_accel_mps2 + 1e-6)
        s = velocity_profile.path_s_values(race, True)
        for i in range(len(speed) - 1):
            ds = s[i + 1] - s[i]
            self.assertLessEqual(speed[i] ** 2 - speed[i + 1] ** 2, 2 * cfg.brake_decel_mps2 * ds + 1e-6)
            self.assertLessEqual(speed[i + 1] ** 2 - speed[i] ** 2, 2 * cfg.accel_limit_mps2 * ds + 1e-6)

    @unittest.skipUnless(C0_GEOMETRY.exists(), "C0 geometry not available")
    def test_c0_plan_stays_inside_the_region(self):
        from shapely import wkt
        from shapely.geometry import LineString
        from roboracer.planning.c0_track import build_c0_plan
        geometry = json.loads(C0_GEOMETRY.read_text())
        region = wkt.loads(geometry["region_wkt"])
        cfg = velocity_profile.VelocityProfileConfig(**PROFILE)
        payload, report = build_c0_plan(geometry["centerline"], region, spacing_m=0.1, boundary_margin_m=0.3,
                                        profile=cfg, start_pin_m=0.05)
        self.assertTrue(report["optimizer_converged"])
        self.assertGreaterEqual(report["min_polyline_clearance_m"], 0.28)
        line = [p[:2] for p in payload["ReferenceLine"]]
        self.assertTrue(region.contains(LineString(line)))
        self.assertLess(math.dist(line[0], geometry["spawn"]["xy"]), 0.2)
        self.assertEqual(len(payload["ReferenceSpeed"]), len(line))
        with self.assertRaises(ValueError):
            build_c0_plan(geometry["centerline"], region, spacing_m=0.5, boundary_margin_m=0.3, profile=cfg,
                          start_pin_m=0.05)

    def test_controller_tracks_a_closed_loop_in_simulation(self):
        """Kinematic bicycle with a 0.3 s observation delay: the controller keeps a stadium lap inside 0.1 m."""
        path = stadium()
        tj = LapTrajectoryTracker(path=path, velocity=[1.0] * len(path))
        cfg = RacingControllerConfig(mpc_lateral_mode="apply", speed_cap_mps=1.0)
        ctl = RacingLineController(config=cfg)
        x, y, th, v, delta, dt = 0.0, -1.45, 0.05, 1.0, 0.0, 0.1
        history, worst = [], 0.0
        for _ in range(250):
            history.append((x, y, th))
            ox, oy, oth = history[max(0, len(history) - 4)]  # pose 0.3 s old
            target, steer, detail = ctl.steer_and_speed(tj, EgoState(x=ox, y=oy, theta=oth, velocity=v), dt)
            for _ in range(10):  # 10 ms plant steps, steering lag 0.08 s
                delta += (steer - delta) * 0.01 / 0.08
                x += v * math.cos(th) * 0.01
                y += v * math.sin(th) * 0.01
                th += v / cfg.wheelbase_m * math.tan(delta) * 0.01
            worst = max(worst, abs(tj.convert_xy_to_sd(x, y)[1]))
        self.assertFalse(ctl.safe_stop_reason)
        self.assertLess(worst, 0.1)


if __name__ == "__main__":
    unittest.main()
