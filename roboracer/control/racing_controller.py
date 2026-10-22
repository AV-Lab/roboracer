"""B's path-tracking controller (S3, D30/D31): the A2RL base-stack lateral chain, ported.

Port of the lateral part of ``A2RLBaseStackController.control`` in the A2RL plugin (AV-Lab/a2rl ``dev``
0b5cfa8, ``control/base_stack_controller.py``) with its helpers ``_wrap_s``, ``_value_at_s``,
``_heading_at_s``, ``_curvature_at_s``, ``_preview_pure_pursuit_shadow``, ``_preview_pure_pursuit_blend_alpha``,
``_lateral_mpc``, ``_mpc_slide_blend_alpha``, ``_track_sent_steer`` and ``_tracking_safe_stop_reason``:

    steer = atan(L kappa(s + v t_ff)) - k_fb (e_y + L_yaw (e_psi + l_r kappa))   (+ optional preview
    pure-pursuit blend), replaced by the lateral MPC in "apply" mode (with the oversteer hand-back),
    then the steer-excess limit around the feedforward.

Not ported (does not apply to this car): the longitudinal chain (EAV24 engine map, gears, brake
pressure). B emits the A2RL velocity profile's target speed to the qualified supervisor speed loop
(S1 D5) as a ``TargetSpeedSteeringCommand``, capped by the approved envelope. Also not ported: the
high-speed (30-50 m/s) gain schedules, yaw damping and steering-rate shadows, whose defaults are
inactive in A2RL. A tracking safe stop sets the target speed to 0 while steering on the
current-curvature law (as A2RL); unlike A2RL it latches until ``reset()``.

Defaults: C0 geometry and the A2RL tuned values scaled by geometric similarity (length ratio
0.324 / 3.1); they are starting values to be re-identified in shadow mode, as A2RL did.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math

import numpy as np

from avlite.c30_control.c31_control_model import ControlCommand
from avlite.c30_control.c32_control_strategy import ControlStrategy

from ..runtime.commands import TargetSpeedSteeringCommand
from .lateral_mpc import LateralMpc, LateralMpcConfig

A2RL_WHEELBASE_M = 3.1
C0_WHEELBASE_M = 0.324
LENGTH_RATIO = C0_WHEELBASE_M / A2RL_WHEELBASE_M


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _normalize_angle(angle: float) -> float:
    return (float(angle) + math.pi) % (2.0 * math.pi) - math.pi


@dataclass
class RacingControllerConfig:
    wheelbase_m: float = C0_WHEELBASE_M
    rear_axle_to_cg_m: float = 1.35 * LENGTH_RATIO
    max_wheel_angle_rad: float = math.radians(30.0)
    steering_offset_rad: float = 0.0
    kp_steer_fb: float = 0.06 / LENGTH_RATIO
    lookahead_distance_yaw_m: float = 15.0 * LENGTH_RATIO
    lat_ff_preview_time_s: float = 0.0
    preview_pure_pursuit_enabled: bool = False
    preview_pure_pursuit_lookahead_time_s: float = 0.20
    preview_pure_pursuit_min_distance_m: float = 2.0 * LENGTH_RATIO
    preview_pure_pursuit_blend_fraction: float = 0.0
    preview_pure_pursuit_blend_start_speed_mps: float = 0.0
    preview_pure_pursuit_blend_full_speed_mps: float = 0.0
    steer_excess_limit_rad: float = 0.0
    mpc_lateral_mode: str = "off"            # "off", "shadow" (solve and log) or "apply"
    mpc_horizon_steps: int = 15
    mpc_dt_s: float = 0.1                    # the stack tick
    mpc_steer_lag_s: float = 0.08            # ~183 deg/s slew (S1 M0) as a first-order lag
    mpc_q_lateral: float = 1.0 / LENGTH_RATIO ** 2
    mpc_q_heading: float = 10.0
    mpc_r_feedforward: float = 20.0
    mpc_r_rate: float = 200.0
    mpc_delay_s: float = 0.3                 # observation age at request (S2: <= 345 ms)
    mpc_understeer_gradient_s2pm: float = 0.0
    mpc_slide_blend_start_rad: float = 0.0
    mpc_slide_blend_full_rad: float = 0.10
    tracking_safe_stop_min_speed_mps: float = 0.0   # A2RL: 7 m/s; active at all speeds here
    safe_stop_lateral_error_m: float = 2.5 * LENGTH_RATIO
    safe_stop_yaw_error_rad: float = 0.2
    speed_cap_mps: float = 0.3               # the approved motion envelope (D33 raises it in stages)


class RacingLineController(ControlStrategy):
    """Tracks the global plan (A2RL tracking mode "legacy"); needs an ego pose and speed."""

    def __init__(self, *args, config: RacingControllerConfig | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = config or RacingControllerConfig()
        self.reset()

    def reset(self):
        self.cmd = ControlCommand()
        self.last = None
        self.safe_stop_reason = ""
        self._mpc = None
        self._mpc_previous_command_rad = 0.0
        self._mpc_steer_estimate_rad = 0.0
        self._mpc_steer_history: deque[tuple[float, float]] = deque(maxlen=100)

    # --- path lookups (A2RL helpers, unchanged) ---
    @staticmethod
    def _is_closed_loop(tj) -> bool:
        return (tj.is_initialized and len(tj.path_x) > 2
                and math.hypot(float(tj.path_x[0] - tj.path_x[-1]), float(tj.path_y[0] - tj.path_y[-1])) < 1e-6)

    def _wrap_s(self, tj, s: float) -> float:
        path_s = np.asarray(tj.path_s, dtype=float)
        if len(path_s) == 0:
            return 0.0
        start_s, end_s = float(path_s[0]), float(path_s[-1])
        if self._is_closed_loop(tj) and end_s > start_s:
            return start_s + ((float(s) - start_s) % (end_s - start_s))
        return float(np.clip(s, start_s, end_s))

    def _value_at_s(self, tj, values, s: float) -> float:
        path_s = np.asarray(tj.path_s, dtype=float)
        array = np.asarray(values, dtype=float)
        if len(path_s) == 0 or len(array) == 0:
            return 0.0
        n = min(len(path_s), len(array))
        path_s, array = path_s[:n], array[:n]
        target_s = self._wrap_s(tj, s)
        if self._is_closed_loop(tj) and len(path_s) > 1:
            lap = float(path_s[-1] - path_s[0])
            if lap > 0.0 and target_s > path_s[-2]:
                extended_s = np.concatenate((path_s[:-1], [path_s[-1]]))
                extended_values = np.concatenate((array[:-1], [array[0]]))
                return float(np.interp(target_s, extended_s, extended_values))
        return float(np.interp(target_s, path_s, array))

    def _heading_at_s(self, tj, s: float) -> float:
        path_s = np.asarray(tj.path_s, dtype=float)
        headings = np.unwrap(np.asarray(tj.path_heading, dtype=float))
        n = min(len(path_s), len(headings))
        if n == 0:
            return 0.0
        return float(np.interp(self._wrap_s(tj, s), path_s[:n], headings[:n]))

    def _curvature_at_s(self, tj, s: float) -> float:
        path_s = np.asarray(tj.path_s, dtype=float)
        headings = np.unwrap(np.asarray(tj.path_heading, dtype=float))
        n = min(len(path_s), len(headings))
        if n < 3:
            return 0.0
        target_s = self._wrap_s(tj, s)
        idx = int(np.searchsorted(path_s[:n], target_s))
        prev_idx, next_idx = max(0, idx - 1), min(n - 1, idx + 1)
        ds = float(path_s[next_idx] - path_s[prev_idx])
        if abs(ds) <= 1e-9:
            return 0.0
        return float((headings[next_idx] - headings[prev_idx]) / ds)

    # --- lateral chain ---
    def _preview_pure_pursuit(self, tj, ego, s_m: float, target_speed: float, raw_steer: float) -> float:
        """A2RL ``_preview_pure_pursuit_shadow``: the pure-pursuit candidate minus the raw steer."""
        cfg = self.config
        if not cfg.preview_pure_pursuit_enabled:
            return 0.0
        lookahead = max(cfg.preview_pure_pursuit_min_distance_m,
                        max(0.0, target_speed) * max(0.0, cfg.preview_pure_pursuit_lookahead_time_s))
        target_s = self._wrap_s(tj, s_m + lookahead)
        dx = self._value_at_s(tj, tj.path_x, target_s) - float(ego.x)
        dy = self._value_at_s(tj, tj.path_y, target_s) - float(ego.y)
        bearing = _normalize_angle(math.atan2(dy, dx) - float(ego.theta))
        candidate = math.atan2(2.0 * cfg.wheelbase_m * math.sin(bearing), max(math.hypot(dx, dy), 1.0e-9))
        candidate = _clamp(candidate, -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad)
        return candidate - raw_steer

    def _preview_pure_pursuit_blend_alpha(self, speed: float) -> float:
        cfg = self.config
        if not cfg.preview_pure_pursuit_enabled:
            return 0.0
        maximum = _clamp(cfg.preview_pure_pursuit_blend_fraction, 0.0, 1.0)
        start = max(0.0, cfg.preview_pure_pursuit_blend_start_speed_mps)
        full = max(start, cfg.preview_pure_pursuit_blend_full_speed_mps)
        if maximum <= 0.0 or speed <= start:
            return 0.0
        if full <= start or speed >= full:
            return maximum
        progress = _clamp((speed - start) / (full - start), 0.0, 1.0)
        return maximum * progress * progress * (3.0 - 2.0 * progress)

    def _lateral_mpc(self, tj, s_m, speed, lateral_error_m, yaw_error):
        cfg = self.config
        if cfg.mpc_lateral_mode not in ("shadow", "apply"):
            return None
        mpc_config = LateralMpcConfig(
            horizon_steps=int(cfg.mpc_horizon_steps), dt_s=float(cfg.mpc_dt_s), wheelbase_m=float(cfg.wheelbase_m),
            steer_lag_s=float(cfg.mpc_steer_lag_s), q_lateral=float(cfg.mpc_q_lateral),
            q_heading=float(cfg.mpc_q_heading), r_feedforward=float(cfg.mpc_r_feedforward),
            r_rate=float(cfg.mpc_r_rate), max_wheel_angle_rad=float(cfg.max_wheel_angle_rad),
            understeer_gradient_s2pm=float(cfg.mpc_understeer_gradient_s2pm))
        if self._mpc is None or self._mpc.config != mpc_config:
            self._mpc = LateralMpc(mpc_config)
        dead_time, remaining = [], max(0.0, float(cfg.mpc_delay_s))
        for step_dt, wheel_angle in reversed(self._mpc_steer_history):
            if remaining <= 1.0e-9:
                break
            used = min(step_dt, remaining)
            dead_time.append((used, wheel_angle))
            remaining -= used
        dead_time.reverse()
        travelled, steps = 0.0, []
        for step_dt, wheel_angle in dead_time:
            steps.append((step_dt, wheel_angle, self._curvature_at_s(tj, s_m + travelled)))
            travelled += max(0.0, float(speed)) * step_dt
        lateral_now, heading_now = self._mpc.advance(speed, lateral_error_m, yaw_error, steps)
        step = max(0.5, float(speed)) * mpc_config.dt_s
        preview = [self._curvature_at_s(tj, s_m + travelled + step * (k + 1)) for k in range(mpc_config.horizon_steps)]
        return self._mpc.solve(speed, lateral_now, heading_now, self._mpc_steer_estimate_rad,
                               self._mpc_previous_command_rad, preview)

    def _mpc_slide_blend_alpha(self, curvature: float, yaw_error: float) -> float:
        cfg = self.config
        if cfg.mpc_slide_blend_start_rad <= 0.0:
            return 0.0
        oversteer_index = (1.0 if curvature > 0.0 else -1.0 if curvature < 0.0 else 0.0) * yaw_error
        span = max(1.0e-6, cfg.mpc_slide_blend_full_rad - cfg.mpc_slide_blend_start_rad)
        return min(1.0, max(0.0, (oversteer_index - cfg.mpc_slide_blend_start_rad) / span))

    def _track_sent_steer(self, sent_steer_rad: float, dt: float) -> None:
        cfg = self.config
        if cfg.mpc_lateral_mode not in ("shadow", "apply"):
            return
        self._mpc_previous_command_rad = float(sent_steer_rad)
        self._mpc_steer_estimate_rad += (float(sent_steer_rad) - self._mpc_steer_estimate_rad) * min(
            1.0, max(0.0, float(dt)) / max(1.0e-3, float(cfg.mpc_steer_lag_s)))
        if dt > 0.0:
            self._mpc_steer_history.append((float(dt), self._mpc_steer_estimate_rad))

    def _tracking_safe_stop_reason(self, speed: float, yaw_error: float, lateral_error_m: float) -> str:
        cfg = self.config
        if speed < cfg.tracking_safe_stop_min_speed_mps:
            return ""
        if abs(yaw_error) > cfg.safe_stop_yaw_error_rad:
            return "yaw_error"
        if abs(lateral_error_m) > cfg.safe_stop_lateral_error_m:
            return "lateral_error"
        return ""

    def steer_and_speed(self, tj, ego, dt: float) -> tuple[float, float, dict]:
        """One control step on tracker ``tj`` for ``ego`` (x, y, theta, velocity)."""
        cfg = self.config
        tj.update_waypoint_by_xy(float(ego.x), float(ego.y))
        s_m, lateral_error_m = tj.convert_xy_to_sd(float(ego.x), float(ego.y))
        s_m, lateral_error_m = float(s_m), float(lateral_error_m)
        yaw_error = _normalize_angle(float(ego.theta) - self._heading_at_s(tj, s_m))
        curvature = self._curvature_at_s(tj, s_m)
        speed = max(0.0, float(getattr(ego, "velocity", 0.0) or 0.0))
        profile_speed = max(0.0, self._value_at_s(tj, tj.velocity, s_m))
        detail = {"s_m": s_m, "lateral_error_m": lateral_error_m, "yaw_error_rad": yaw_error,
                  "curvature": curvature, "speed": speed, "profile_speed": profile_speed}
        reason = self.safe_stop_reason or self._tracking_safe_stop_reason(speed, yaw_error, lateral_error_m)
        if reason:
            # A2RL ``_safe_stop_command``: keep steering on the current-curvature law while stopping.
            # Deviation: the stop latches (A2RL re-evaluates each tick); reset() clears it.
            self.safe_stop_reason = reason
            fb = cfg.kp_steer_fb * (lateral_error_m
                                    + cfg.lookahead_distance_yaw_m * (yaw_error + cfg.rear_axle_to_cg_m * curvature))
            steer = _clamp(math.atan(cfg.wheelbase_m * curvature) - fb + cfg.steering_offset_rad,
                           -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad)
            return 0.0, steer, dict(detail, safe_stop=reason, target_speed=0.0, steer=steer)

        ff_curvature = curvature
        if cfg.lat_ff_preview_time_s > 0.0:
            ff_curvature = self._curvature_at_s(tj, s_m + speed * cfg.lat_ff_preview_time_s)
        lat_ff = math.atan(cfg.wheelbase_m * ff_curvature)
        lat_fb = cfg.kp_steer_fb * (lateral_error_m
                                    + cfg.lookahead_distance_yaw_m * (yaw_error + cfg.rear_axle_to_cg_m * curvature))
        raw_steer = _clamp(lat_ff - lat_fb + cfg.steering_offset_rad, -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad)
        steer = _clamp(raw_steer + self._preview_pure_pursuit_blend_alpha(speed)
                       * self._preview_pure_pursuit(tj, ego, s_m, profile_speed, raw_steer),
                       -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad)
        mpc = self._lateral_mpc(tj, s_m, speed, lateral_error_m, yaw_error)
        if cfg.mpc_lateral_mode == "apply" and mpc is not None:
            mpc_steer = _clamp(mpc["steer_rad"] + cfg.steering_offset_rad, -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad)
            steer = mpc_steer + self._mpc_slide_blend_alpha(curvature, yaw_error) * (steer - mpc_steer)
        if cfg.steer_excess_limit_rad > 0.0:
            steer = _clamp(steer, lat_ff - cfg.steer_excess_limit_rad, lat_ff + cfg.steer_excess_limit_rad)
        self._track_sent_steer(steer, dt)
        target_speed = min(profile_speed, cfg.speed_cap_mps)
        return target_speed, steer, dict(detail, lat_ff=lat_ff, lat_fb=lat_fb, raw_steer=raw_steer,
                                         mpc=mpc, target_speed=target_speed, steer=steer)

    def control(self, ego, plan=None, control_dt=None, perception_model=None, sensors=None):
        if plan is not None:
            self.tj = plan.as_trajectory() if hasattr(plan, "as_trajectory") else plan
        tj = getattr(self, "tj", None)
        if tj is None or not tj.is_initialized:
            speed, steer, detail = 0.0, 0.0, {"reason": "no plan"}
        else:
            reference = tj.parent_trajectory or tj  # A2RL tracking mode "legacy": track the global line
            speed, steer, detail = self.steer_and_speed(reference, ego, float(control_dt or 0.1))
        self.last = detail
        self.cmd = ControlCommand(steer=steer, acceleration=0.0)  # gauge mirror
        return TargetSpeedSteeringCommand(target_speed=speed, steer=steer)
