"""AVLite's ``GreedyLatticePlanner`` at C0 scale, with the S4 blocked-track stop (D57, D58).

The lattice (sampling, quintic edges, collision and boundary checks, edge selection, chaining) is AVLite's,
unchanged; it is what A2RL runs in tracking mode ``selected_local``. Added here:

1. **C0 settings** (``C0_PLANNING``). AVLite's defaults are sized for a full-size race car (30 m maneuvers,
   0.5 m boundary clearance, 3 m/s minimum curvature speed, a 4.5 x 2 m ego box). C0 is a 1:10 car on a
   1.2-2.5 m wide track; every changed value is listed with its reason. They are applied to AVLite's
   ``PlanningSettings`` class (process-wide) when the planner is constructed, as the runner does for its other
   settings, and recorded in ``settings_applied``.
2. **Blocked track / planning failure (D58, gated by D78 A).** After every replan: if no level-0 edge is both
   collision-free and inside the bounds (curvature not considered) **while the plan the car follows runs into a
   confirmed obstacle within the horizon**, or the replan raised, the planner counts a blocked replan.
   ``blocked_after`` (2) consecutive blocked replans latch ``blocked``: from then on the local plan it hands
   out has zero velocity, so the controller's target speed is 0. Only ``reset()`` (rearm) clears it.
   The gate: beside an obstacle being passed, every fresh edge (it starts at the car with no lateral slope) clips
   it although the followed plan clears it; the ungated rule latched there (S5 H2).
   **Stop-distance guard (D78 A):** if the followed plan reaches a confirmed obstacle within the stop envelope
   (D58's 0.30 m + latency + braking at the current speed, measured from the car's front), ``blocked`` latches at
   once, so a late decision still ends >= 0.30 m short.
3. **Early avoidance (D78 A).** AVLite keeps a committed chain until it collides, is shorter, or the wait time
   has passed. A chain that stays on the line for its current edge and only shifts on the next one passes
   AVLite's corridor check (the car is modelled as centred on the path) but leaves the 1:10 car no room to shift
   before the obstacle: in S5 H2 the shift began < 1 m before the box, every fresh edge from the car then
   collided, and the D58 latch fired 0.22 m from it. So: as soon as the fresh line edge from the car collides
   while the committed current edge still ends on the line, a clean lateral plan is taken at once.
4. **AVLite's overtake mode off (D78 A)** (``_agent_blocks_ahead``): it is for moving cars and, with a static box
   ahead, pushed the tail edges to the far wall and back across the line; and the **wall inset** is half the car
   width + 0.20 m (U3), not + 0.10 m. The obstacle corridor stays D57's + 0.10 m.
5. **Map-derived lattice bounds (D79 A).** The lattice's track bounds come from ``data/c0-lattice-bounds.json``
   (built from the C0 map by ``scripts/roboracer_s5_lattice_bounds.py``), not from the plan's LeftBound/RightBound,
   which are outside the real walls by up to 0.24 m in places (S5 §12). They apply only if they were built for
   the plan in use (same waypoints); otherwise the planner refuses to start. The racing line and the global plan
   object are unchanged.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
import time

from avlite.c20_planning.c28_local_lattice_planners import GreedyLatticePlanner
from avlite.c20_planning.c29_settings import PlanningSettings

log = logging.getLogger(__name__)

C0_EGO_LENGTH_M = 0.526   # scorer footprint (S1-05 C0 geometry): x 0.101 behind to 0.425 ahead of the rear axle
C0_EGO_WIDTH_M = 0.288
CLEARANCE_MARGIN_M = 0.10  # D57: half car width + 0.10 m
WALL_MARGIN_M = 0.20  # D78 A: U3 wall clearance (D66) as the lattice's inset from the plan bounds
C0_FRONT_M = 0.425  # footprint front ahead of the pose (scorer geometry)
GUARD_REST_M = 0.30  # D58: stop at least this far from the obstacle
GUARD_LATENCY_S = 0.8  # pose age 0.3 s + stop request to braking (S3 F1-1: 0.28 m travel at 0.5 m/s ~ 0.45 s)
GUARD_RADIUS_M = C0_EGO_WIDTH_M / 2 + 0.05  # narrower than the D57 corridor: only a plan into the obstacle trips it
LATTICE_BOUNDS = Path(__file__).resolve().parents[1] / "data/c0-lattice-bounds.json"  # D79 A

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
    "c28_boundary_clearance": (C0_EGO_WIDTH_M / 2 + WALL_MARGIN_M,
                               "D78 A: half ego width + 0.20 m (U3 wall) from the bounds; D57 had + 0.10 m, which "
                               "let a lateral edge run the body 0.15 m from a wall (default 0.5)"),
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


def load_lattice_bounds(global_plan, path: Path = LATTICE_BOUNDS) -> dict:
    """D79 A: the map-derived bounds for ``global_plan``; refused if they were built for other waypoints."""
    data = json.loads(Path(path).read_text())
    points = [tuple(p[:2]) for p in global_plan.path]
    first, last = data["reference_line_first_last"]
    if (len(points) != data["waypoints"] or len(data["LeftBound"]) != len(points)
            or math.dist(points[0], first) > 1e-6 or math.dist(points[-1], last) > 1e-6):
        raise ValueError(f"{Path(path).name} was built for another plan ({data['waypoints']} waypoints, "
                         f"plan sha256 {data['plan_sha256'][:12]}); the plan in use has {len(points)}")
    return data


def set_c0_ego(ego) -> None:
    """The lattice corridor uses the ego box; AVLite's State defaults to 4.5 x 2.0 m."""
    ego.length, ego.width = C0_EGO_LENGTH_M, C0_EGO_WIDTH_M


class C0LatticePlanner(GreedyLatticePlanner):
    """``GreedyLatticePlanner`` with C0 settings and the D58 latched blocked-track stop."""

    blocked_after = 2

    def __init__(self, global_plan, env, setting=PlanningSettings):
        self.settings_applied = apply_c0_planning_settings()
        super().__init__(global_plan, env, setting)
        if env is not None and getattr(env, "ego_vehicle", None) is not None:
            set_c0_ego(env.ego_vehicle)
        self._apply_map_bounds(global_plan)
        self._init_blocked()

    def set_global_plan(self, global_plan, ego_xy=None) -> None:
        super().set_global_plan(global_plan, ego_xy=ego_xy)
        if getattr(self, "lattice", None) is not None:
            self._apply_map_bounds(global_plan)

    def _apply_map_bounds(self, global_plan) -> None:
        """D79 A: the lattice samples and checks against the map-derived bounds, not the plan's."""
        data = load_lattice_bounds(global_plan)
        self.lattice.ref_left_boundary_d = list(data["LeftBound"])
        self.lattice.ref_right_boundary_d = list(data["RightBound"])
        self.bounds_source = {"file": LATTICE_BOUNDS.name, "plan_sha256": data["plan_sha256"]}

    def _init_blocked(self):
        self.blocked = False
        self.blocked_reason = ""
        self._blocked_streak = 0
        self.diagnostics = {"replans": 0, "level0_edges": 0, "clear_level0_edges": 0, "blocked_streak": 0,
                            "replan_errors": 0, "replan_s": None, "early_avoidance_switches": 0}

    def _agent_blocks_ahead(self) -> bool:
        """D78 A: AVLite's overtake mode is off. It prefers lateral targets for every edge and relaxes the bounds
        while any agent is within the horizon, which is for moving cars; C0 obstacles are static scan detections
        (velocity 0), whose line edges the collision check already rejects. With it on, the tail edges after a
        static box were pushed to the far side (body 0.15 m from a wall) and back across the line (S5 §11)."""
        return False

    def should_switch_plan(self, new_plan, force_if_collision: bool = True) -> bool:
        if super().should_switch_plan(new_plan, force_if_collision):
            return True
        if self._early_avoidance(new_plan):
            self.diagnostics["early_avoidance_switches"] += 1
            log.info("early avoidance (D78): line edge blocked, committing to d = %.2f", new_plan.end.d)
            return True
        return False

    def _early_avoidance(self, new_plan) -> bool:
        """D78 A: the fresh line edge collides, the committed current edge ends on the line, ``new_plan`` is clean."""
        current = self.selected_local_plan
        if current is None or new_plan.collision or new_plan.boundary_violation:
            return False
        line_nodes = self.lattice.lattice_nodes_by_level.get(1) or []
        if not line_nodes:
            return False
        line_node = line_nodes[0]  # AVLite samples the line node first at every level
        line_edges = [e for e in self.lattice.level0_edges if e.end is line_node]
        if not any(e.collision for e in line_edges):
            return False
        d0 = PlanningSettings.c28_d0_reference_threshold
        on_line = abs(current.end.d - line_node.d) < d0
        lateral = abs(new_plan.end.d - line_node.d) >= d0
        return on_line and lateral

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
        located = len(self.traversed_s) > 0
        horizon = self.planning_horizon * self.maneuver_distance + C0_FRONT_M
        plan_gap = self._obstacle_gap_on_plan(horizon) if error is None and located else None
        d["plan_obstacle_gap_m"] = plan_gap
        # D78 A: no clear fresh edge counts only while the followed plan runs into an obstacle. Beside a box being
        # passed, every fresh edge (it starts at the car, with no lateral slope) clips the box although the plan
        # the car follows clears it (S5 §11: the H2 latch fired so).
        if error is not None or (not clear and not handed_off and located and plan_gap is not None):
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
        if not self.blocked and plan_gap is not None and plan_gap <= self._stop_envelope_m():
            self.blocked = True
            self.blocked_reason = f"stop-distance guard: obstacle on the plan {plan_gap:.2f} m ahead"
            log.warning("blocked track latched (D58, D78 guard): %s", self.blocked_reason)

    def _stop_envelope_m(self) -> float:
        """Front-to-obstacle distance at which a stop must begin to end ``GUARD_REST_M`` short (D58)."""
        v = max(0.0, float(getattr(self.pm.ego_vehicle, "velocity", 0.0) or 0.0))
        return GUARD_REST_M + v * GUARD_LATENCY_S + v * v / (2.0 * PlanningSettings.c27_max_deceleration)

    def _obstacle_gap_on_plan(self, reach: float):
        """D78 A: distance from the car's front to the first confirmed obstacle on the plan it is following.

        The followed path (committed chain, else the global line from its current waypoint) is walked from the car
        for ``reach`` m; the first segment whose ``GUARD_RADIUS_M`` corridor touches an obstacle box gives the gap.
        A planned pass keeps the D57 corridor (+ 0.10 m) clear, so the narrower guard corridor (+ 0.05 m) only
        touches an obstacle the plan would drive into. ``None``: nothing on the plan within reach.
        """
        import numpy as np
        from shapely.geometry import LineString
        agents = list(getattr(self.pm, "agent_vehicles", None) or []) if self.pm is not None else []
        if not agents:
            return None
        committed = self._committed_trajectory
        traj = committed if committed is not None else self.global_trajectory
        xs, ys = np.asarray(traj.path_x, dtype=float), np.asarray(traj.path_y, dtype=float)
        n = len(xs)
        if n < 2:
            return None
        start = int(np.clip(getattr(traj, "current_wp", 0), 0, n - 1))
        order = range(start, start + n) if committed is None else range(start, n)  # the global line is closed
        boxes = [a.get_bb_polygon() for a in agents]
        previous, travelled = tuple(self.location_xy), 0.0
        for k in order:
            point = (float(xs[k % n]), float(ys[k % n]))
            step = float(np.hypot(point[0] - previous[0], point[1] - previous[1]))
            if step > 1e-6:
                corridor = LineString([previous, point]).buffer(GUARD_RADIUS_M, cap_style="flat")
                if any(corridor.intersects(b) for b in boxes):
                    return max(0.0, travelled - C0_FRONT_M)
                travelled += step
                previous = point
            if travelled > reach:
                break
        return None

    def get_local_plan(self):
        plan = super().get_local_plan()
        if not self.blocked:
            return plan
        # A new plan on the same path with zero velocity. ``from_trajectory`` wraps the committed (or the global)
        # trajectory object itself, so it must not be modified in place.
        from avlite.c20_planning.c21_planning_model import LocalPlan
        return LocalPlan(path=list(plan.path), velocity=[0.0] * len(plan.path))
