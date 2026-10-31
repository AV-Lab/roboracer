"""AVLite's ``GreedyLatticePlanner`` at C0 scale, with the S4 blocked-track stop (D57, D58).

The lattice (sampling, quintic edges, collision and boundary checks, edge selection, chaining) is AVLite's,
unchanged; it is what A2RL runs in tracking mode ``selected_local``. Two things are added here:

1. **C0 settings** (``C0_PLANNING``). AVLite's defaults are sized for a full-size race car (30 m maneuvers,
   0.5 m boundary clearance, 3 m/s minimum curvature speed, a 4.5 x 2 m ego box). C0 is a 1:10 car on a
   1.2-2.5 m wide track; every changed value is listed with its reason. They are applied to AVLite's
   ``PlanningSettings`` class (process-wide) when the planner is constructed, as the runner does for its other
   settings, and recorded in ``settings_applied``.
2. **Blocked track / planning failure (D58).** After every replan: if no level-0 edge is both collision-free and
   inside the bounds (curvature not considered), or the replan raised, the planner counts a blocked replan.
   ``blocked_after`` (2) consecutive blocked replans latch ``blocked``: from then on the local plan it hands
   out has zero velocity, so the controller's target speed is 0. Only ``reset()`` (rearm) clears it.
"""

from __future__ import annotations

import logging
import time

from avlite.c20_planning.c28_local_lattice_planners import GreedyLatticePlanner
from avlite.c20_planning.c29_settings import PlanningSettings

log = logging.getLogger(__name__)

C0_EGO_LENGTH_M = 0.526   # scorer footprint (S1-05 C0 geometry): x 0.101 behind to 0.425 ahead of the rear axle
C0_EGO_WIDTH_M = 0.288
CLEARANCE_MARGIN_M = 0.10  # D57: half car width + 0.10 m

# name: (value, reason)
C0_PLANNING = {
    "c20_collision_safety_margin": (CLEARANCE_MARGIN_M, "D57: corridor = half ego width + 0.10 m (default 0.5)"),
    "c20_obstacle_inflation_margin": (0.0, "the margin is already in the corridor (default 0.5)"),
    "c20_min_velocity_threshold": (0.05, "below this an agent is static; scan obstacles have velocity 0 (default 0.5)"),
    "c20_default_ego_velocity": (0.5, "V1 speed when the ego speed is unknown (default 5)"),
    "c20_min_ramp_start_velocity": (0.1, "creep speed for the restart ramp (default 3 m/s, above the 0.5 m/s cap)"),
    "c20_beside_agent_sweep_time": (0.0, "static obstacles only; no sweep (default 4 s)"),
    "c20_beside_agent_rear_window": (0.0, "static obstacles only (default 10 m)"),
    "c27_max_deceleration": (2.0, "the profile's brake limit (default 3)"),
    "c27_stopping_safety_buffer": (0.5, "C0 scale (default 5 m)"),
    "c28_num_of_edge_points": (10, "one point per 0.2 m on a 2 m edge (unchanged default)"),
    "c28_planning_horizon": (2, "2 edges = 4 m ahead, inside the 7 m detection range; 3 levels cost ~94 ms per replan "
                                  "against the 100 ms tick (S4 §3 profile) (default 3)"),
    "c28_maneuver_distance": (2.0, "2 m edges: room for the 0.45 m T1/T2 shift at 0.5 m/s, and a blocked stop "
                                   "decided about 2 m ahead (S4 §2: ICP needs > 1 m from a full blockage) (default 30)"),
    "c28_boundary_clearance": (C0_EGO_WIDTH_M / 2 + CLEARANCE_MARGIN_M, "D57: half ego width + 0.10 m from the bounds (default 0.5)"),
    "c28_sample_size": (5, "4 lateral samples + the line per level: 30 edges per replan (default 3)"),
    "c28_sample_distribution": (0, "even spread: deterministic replans (default 1 = random)"),
    "c28_replan_wait_time": (0.5, "C0 scale (default 2.5 s)"),
    "c28_urgent_collision_threshold": (2.0, "one edge length (default 10 m)"),
    "c28_disconnect_distance_threshold": (0.5, "C0 scale (default 5 m)"),
    "c28_max_lateral_accel": (3.0, "the racing line's profile assumption (default 4)"),
    "c28_min_curvature_velocity": (0.3, "C0 speeds (default 3 m/s)"),
    "c28_d0_reference_threshold": (0.05, "C0 scale (default 0.2 m)"),
    "c28_preferred_extra_clearance": (0.05, "C0 scale (default 0.5 m)"),
}


def apply_c0_planning_settings() -> dict:
    applied = {}
    for name, (value, reason) in C0_PLANNING.items():
        if not hasattr(PlanningSettings, name):
            raise AttributeError(f"AVLite PlanningSettings has no {name}")
        applied[name] = {"default": getattr(PlanningSettings, name), "c0": value, "reason": reason}
        setattr(PlanningSettings, name, value)
    return applied


def set_c0_ego(ego) -> None:
    """The lattice corridor uses the ego box; AVLite's State defaults to 4.5 x 2.0 m."""
    ego.length, ego.width = C0_EGO_LENGTH_M, C0_EGO_WIDTH_M


class C0LatticePlanner(GreedyLatticePlanner):
    """``GreedyLatticePlanner`` with C0 settings and the D58 latched blocked-track stop."""

    blocked_after = 2
    # S4 §18 (experimental, default off = AVLite's cost): weight on the lateral change within one edge, so that a
    # return to the line after a pass is spread over more than one edge (a gentler S-curve).
    lateral_change_weight = 0.0

    def _edge_cost(self, edge) -> float:
        return super()._edge_cost(edge) + self.lateral_change_weight * abs(edge.end.d - edge.start.d)

    def __init__(self, global_plan, env, setting=PlanningSettings):
        self.settings_applied = apply_c0_planning_settings()
        super().__init__(global_plan, env, setting)
        if env is not None and getattr(env, "ego_vehicle", None) is not None:
            set_c0_ego(env.ego_vehicle)
        self._init_blocked()

    def _init_blocked(self):
        self.blocked = False
        self.blocked_reason = ""
        self._blocked_streak = 0
        self.diagnostics = {"replans": 0, "level0_edges": 0, "clear_level0_edges": 0, "blocked_streak": 0,
                            "replan_errors": 0, "replan_s": None}

    def reset(self, wp: int = 0):
        super().reset(wp)
        self._init_blocked()  # rearm clears the latch (D58)

    def replan(self, perception_model=None, sensors=None, back_to_ref_horizon=10):
        if perception_model is not None and getattr(perception_model, "ego_vehicle", None) is not None:
            set_c0_ego(perception_model.ego_vehicle)
        error = None
        started = time.perf_counter()
        try:
            super().replan(perception_model=perception_model, sensors=sensors, back_to_ref_horizon=back_to_ref_horizon)
        except Exception as exc:  # planning failure (D58): counted as blocked, never driven through
            error = f"{type(exc).__name__}: {exc}"
            log.error("lattice replan failed: %s", error)
        edges = list(self.lattice.level0_edges) if error is None else []
        clear = [e for e in edges if not e.collision and not e.boundary_violation]
        handed_off = error is None and not edges and self.selected_local_plan is None and len(self.traversed_s) > 0 \
            and self.location_sd[0] + self.maneuver_distance > self.global_trajectory.track_end_s
        d = self.diagnostics
        d["replans"] += 1
        d["replan_s"] = time.perf_counter() - started
        d["level0_edges"], d["clear_level0_edges"] = len(edges), len(clear)
        if error is not None or (not clear and not handed_off and len(self.traversed_s) > 0):
            self._blocked_streak += 1
            reason = f"planner error: {error}" if error else "no collision-free in-bounds edge"
        else:
            self._blocked_streak, reason = 0, ""
        d["blocked_streak"] = self._blocked_streak
        if error:
            d["replan_errors"] += 1
        if not self.blocked and self._blocked_streak >= self.blocked_after:
            self.blocked, self.blocked_reason = True, reason
            log.warning("blocked track latched (D58): %s", reason)

    def get_local_plan(self):
        plan = super().get_local_plan()
        if not self.blocked:
            return plan
        # A new plan on the same path with zero velocity. ``from_trajectory`` wraps the committed (or the global)
        # trajectory object itself, so it must not be modified in place.
        from avlite.c20_planning.c21_planning_model import LocalPlan
        return LocalPlan(path=list(plan.path), velocity=[0.0] * len(plan.path))
