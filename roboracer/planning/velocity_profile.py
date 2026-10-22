"""Friction-limited velocity profile (S3, D30/D31: ported from A2RL).

Port of ``planning/velocity_profile.py`` in the A2RL plugin (AV-Lab/a2rl ``dev`` 0b5cfa8):
``is_closed_path``, ``normalize_angle``, ``path_s_values``, ``path_segment_headings``,
``build_path_curvature_envelope``, ``VelocityProfileConfig``, ``build_friction_limited_velocity_profile``
and ``estimate_profile_time_sec``. The algorithm is unchanged: a windowed heading-change curvature
envelope with a backward hold, a lateral-acceleration speed limit (optionally a second, short-window
peak-curvature limit), then backward braking and forward acceleration passes, optionally scaled by the
friction ellipse. Removed: the YasMarina per-distance speed caps/floors used as defaults and the
Autoverse environment-variable overrides; caps/floors remain available, empty by default.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class VelocityProfileConfig:
    top_speed_mps: float
    min_speed_mps: float
    lateral_accel_mps2: float
    brake_decel_mps2: float
    accel_limit_mps2: float
    curvature_window_m: float
    curvature_hold_m: float
    local_speed_caps: tuple[tuple[float, float, float], ...] = ()
    local_speed_floors: tuple[tuple[float, float, float], ...] = ()
    friction_ellipse: bool = False
    friction_ellipse_min_fraction: float = 0.15
    peak_lateral_accel_mps2: float = 0.0
    peak_curvature_window_m: float = 4.0
    friction_ellipse_lookahead_m: float = 0.0
    downforce_reference_speed_mps: float = 0.0
    brake_decel_max_mps2: float = 0.0


def _downforce_gain(speed_mps: float, reference_speed_mps: float) -> float:
    if reference_speed_mps <= 0.0:
        return 1.0
    return 1.0 + (speed_mps / reference_speed_mps) ** 2


def _lateral_speed_limit(curve: float, lateral_accel: float, reference_speed_mps: float, top_speed: float) -> float:
    """Speed where v^2 * curve equals the (downforce-scaled) lateral limit."""
    if reference_speed_mps <= 0.0:
        return math.sqrt(lateral_accel / curve)
    denominator = curve - lateral_accel / reference_speed_mps**2
    if denominator <= 0.0:
        return top_speed
    return math.sqrt(lateral_accel / denominator)


def _ellipse_fraction(speed_mps: float, curve: float, lateral_accel: float, min_fraction: float) -> float:
    if lateral_accel <= 0.0:
        return 1.0
    used = min(1.0, speed_mps * speed_mps * curve / lateral_accel)
    return max(min_fraction, math.sqrt(max(0.0, 1.0 - used * used)))


def normalize_angle(angle: float) -> float:
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def is_closed_path(path) -> bool:
    if len(path) < 2:
        return False
    return math.hypot(path[0][0] - path[-1][0], path[0][1] - path[-1][1]) < 1e-6


def path_s_values(path, closed: bool) -> list[float]:
    if not path:
        return []
    base = path[:-1] if closed and len(path) > 1 else path
    s_values = [0.0]
    for point_a, point_b in zip(base, base[1:]):
        s_values.append(s_values[-1] + math.hypot(point_b[0] - point_a[0], point_b[1] - point_a[1]))
    if closed and len(base) > 1:
        s_values.append(s_values[-1] + math.hypot(base[0][0] - base[-1][0], base[0][1] - base[-1][1]))
    return s_values


def path_segment_headings(path, closed: bool) -> list[float]:
    base = path[:-1] if closed and len(path) > 1 else path
    if len(base) < 2:
        return [0.0] * len(base)
    headings = []
    for idx, point in enumerate(base):
        next_idx = (idx + 1) % len(base) if closed else min(idx + 1, len(base) - 1)
        next_point = base[next_idx]
        headings.append(math.atan2(next_point[1] - point[1], next_point[0] - point[0]))
    return headings


def build_path_curvature_envelope(path, *, curvature_window_m: float, curvature_hold_m: float) -> list[float]:
    """Unsigned curvature from the heading change over +-window, held backwards over ``curvature_hold_m``
    (so the speed limit applies before a corner starts). Closed paths repeat the first value at the end."""
    closed = is_closed_path(path)
    base_path = path[:-1] if closed and len(path) > 1 else path
    n_points = len(base_path)
    if n_points == 0:
        return []
    if n_points == 1:
        return [0.0, 0.0] if closed else [0.0]

    s_values = path_s_values(path, closed)
    base_s = s_values[:-1] if closed else s_values
    lap_length = s_values[-1] if closed else base_s[-1]
    headings = path_segment_headings(path, closed)
    curvature_window_m = max(1e-6, float(curvature_window_m))

    def distance_forward(i: int, j: int) -> float:
        if j >= i:
            return base_s[j] - base_s[i]
        if not closed:
            return 0.0
        return lap_length - base_s[i] + base_s[j]

    def distance_backward(i: int, j: int) -> float:
        if i >= j:
            return base_s[i] - base_s[j]
        if not closed:
            return 0.0
        return base_s[i] + lap_length - base_s[j]

    curvature = [0.0] * n_points
    for idx in range(n_points):
        prev_idx = idx
        next_idx = idx
        while prev_idx > 0 and base_s[idx] - base_s[prev_idx] < curvature_window_m:
            prev_idx -= 1
        while next_idx < n_points - 1 and base_s[next_idx] - base_s[idx] < curvature_window_m:
            next_idx += 1
        if closed:
            while distance_forward(prev_idx, idx) < curvature_window_m:
                prev_idx = (prev_idx - 1) % n_points
                if prev_idx == idx:
                    break
            while distance_forward(idx, next_idx) < curvature_window_m:
                next_idx = (next_idx + 1) % n_points
                if next_idx == idx:
                    break
        span = distance_forward(prev_idx, next_idx) if closed else max(0.0, base_s[next_idx] - base_s[prev_idx])
        if span > 1e-6:
            curvature[idx] = abs(normalize_angle(headings[next_idx] - headings[prev_idx])) / span

    curvature_hold_m = max(0.0, float(curvature_hold_m))
    if curvature_hold_m > 0.0:
        envelope = [0.0] * n_points
        for idx in range(n_points):
            max_curve = curvature[idx]
            lookback_idx = idx
            while True:
                if distance_backward(idx, lookback_idx) > curvature_hold_m:
                    break
                max_curve = max(max_curve, curvature[lookback_idx])
                if not closed and lookback_idx == 0:
                    break
                lookback_idx = (lookback_idx - 1) % n_points
                if lookback_idx == idx:
                    break
            envelope[idx] = max_curve
        curvature = envelope

    if closed:
        curvature.append(curvature[0])
    return curvature


def build_friction_limited_velocity_profile(path, config: VelocityProfileConfig) -> list[float]:
    """Per-point target speed: curvature limits, then braking (backward) and acceleration (forward)
    feasibility passes, twice around a closed lap. Closed paths repeat the first value at the end."""
    closed = is_closed_path(path)
    base_path = path[:-1] if closed and len(path) > 1 else path
    n_points = len(base_path)
    if n_points == 0:
        return []
    if n_points == 1:
        return [config.top_speed_mps]

    top_speed = config.top_speed_mps
    min_speed = config.min_speed_mps
    lateral_accel = config.lateral_accel_mps2
    braking_decel = config.brake_decel_mps2
    accel_limit = config.accel_limit_mps2

    s_values = path_s_values(path, closed)
    base_s = s_values[:-1] if closed else s_values
    lap_length = s_values[-1] if closed else base_s[-1]

    def distance_forward(i: int, j: int) -> float:
        if j >= i:
            return base_s[j] - base_s[i]
        if not closed:
            return 0.0
        return lap_length - base_s[i] + base_s[j]

    curvature_profile = build_path_curvature_envelope(
        path, curvature_window_m=config.curvature_window_m, curvature_hold_m=config.curvature_hold_m)
    curvature = curvature_profile[:-1] if closed else curvature_profile

    velocity = []
    for curve in curvature:
        if curve <= 1e-6:
            velocity.append(top_speed)
        else:
            limit = _lateral_speed_limit(curve, lateral_accel, config.downforce_reference_speed_mps, top_speed)
            velocity.append(min(top_speed, max(min_speed, limit)))
    if config.peak_lateral_accel_mps2 > 0.0:
        peak_curvature_profile = build_path_curvature_envelope(
            path, curvature_window_m=config.peak_curvature_window_m, curvature_hold_m=0.0)
        peak_curvature = peak_curvature_profile[:-1] if closed else peak_curvature_profile
        for idx, curve in enumerate(peak_curvature):
            if curve > 1e-6:
                limit = _lateral_speed_limit(
                    curve, config.peak_lateral_accel_mps2, config.downforce_reference_speed_mps, top_speed)
                velocity[idx] = min(velocity[idx], max(min_speed, limit))

    for start_m, end_m, cap_mps in config.local_speed_caps:
        if cap_mps <= 0.0:
            continue
        for idx, s_m in enumerate(base_s):
            if start_m <= s_m <= end_m:
                velocity[idx] = min(velocity[idx], cap_mps)

    for start_m, end_m, floor_mps in config.local_speed_floors:
        if floor_mps <= 0.0:
            continue
        for idx, s_m in enumerate(base_s):
            if start_m <= s_m <= end_m:
                velocity[idx] = max(velocity[idx], min(floor_mps, top_speed))

    ellipse_curvature = curvature
    if config.friction_ellipse and config.friction_ellipse_lookahead_m > 0.0:
        ellipse_curvature = []
        for idx in range(n_points):
            worst = curvature[idx]
            ahead = (idx + 1) % n_points
            while ahead != idx and distance_forward(idx, ahead) <= config.friction_ellipse_lookahead_m:
                worst = max(worst, curvature[ahead])
                if not closed and ahead == n_points - 1:
                    break
                ahead = (ahead + 1) % n_points
            ellipse_curvature.append(worst)

    passes = 2 if closed else 1
    for _ in range(passes):
        for offset in range(n_points):
            idx = (n_points - 1 - offset) % n_points
            next_idx = (idx + 1) % n_points
            if not closed and idx == n_points - 1:
                continue
            ds = distance_forward(idx, next_idx)
            decel = braking_decel
            grip_gain = _downforce_gain(velocity[next_idx], config.downforce_reference_speed_mps)
            if grip_gain != 1.0:
                decel *= grip_gain
            if config.friction_ellipse:
                decel *= _ellipse_fraction(velocity[next_idx], ellipse_curvature[idx], lateral_accel * grip_gain,
                                           config.friction_ellipse_min_fraction)
            if config.brake_decel_max_mps2 > 0.0:
                decel = min(decel, config.brake_decel_max_mps2)
            velocity[idx] = min(velocity[idx], math.sqrt(max(0.0, velocity[next_idx] ** 2 + 2.0 * decel * ds)))

    for _ in range(passes):
        for idx in range(1, n_points + (n_points if closed else 0)):
            current_idx = idx % n_points
            prev_idx = (current_idx - 1) % n_points
            if not closed and current_idx == 0:
                continue
            ds = distance_forward(prev_idx, current_idx)
            accel = accel_limit
            if config.friction_ellipse:
                accel *= _ellipse_fraction(
                    velocity[prev_idx], curvature[prev_idx],
                    lateral_accel * _downforce_gain(velocity[prev_idx], config.downforce_reference_speed_mps),
                    config.friction_ellipse_min_fraction)
            velocity[current_idx] = min(velocity[current_idx],
                                        math.sqrt(max(0.0, velocity[prev_idx] ** 2 + 2.0 * accel * ds)))

    velocity = [max(min_speed, min(top_speed, value)) for value in velocity]
    if closed:
        velocity.append(velocity[0])
    return velocity


def estimate_profile_time_sec(path, velocity) -> float:
    """Profile time as in A2RL: per base segment, length over the speed at its start (floored at
    0.1 m/s). On a closed path the closing segment is not counted (unchanged from A2RL)."""
    closed = is_closed_path(path)
    s_values = path_s_values(path, closed)
    if len(s_values) < 2 or not velocity:
        return 0.0
    base_s = s_values[:-1] if closed else s_values
    base_velocity = list(velocity[:-1] if closed and len(velocity) == len(base_s) + 1 else velocity)
    if len(base_velocity) < len(base_s):
        return math.inf
    return sum((base_s[index + 1] - base_s[index]) / max(float(base_velocity[index]), 0.1)
               for index in range(len(base_s) - 1))
