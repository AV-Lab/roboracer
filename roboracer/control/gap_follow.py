"""Reactive baseline A (S1-03 proposal v0.2, D6): follow-the-gap with disparity extension.

Uses only the LiDAR in the sensor frame (no map, no path, no GT pose). Emits the approved
``TargetSpeedSteeringCommand``; speed control is the supervisor's (D5).

Steering: beams within +-100 deg; obstacles are inflated by half the vehicle width plus a
margin (disparity extension); the vehicle steers toward the deepest free direction with a
pure-pursuit-style geometry, steer = atan(2 L sin(alpha) / l_d), clamped to +-0.35 rad.
Target speed: min(0.3, 0.3 (1 - |steer| / 0.6), 0.25 (d_front - 0.5)), floored at 0, where
d_front is the nearest return within +-10 deg.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from avlite.c30_control.c31_control_model import ControlCommand
from avlite.c30_control.c32_control_strategy import ControlStrategy
from avlite.c50_common.c51_capabilities import WorldCapability

from ..runtime.commands import TargetSpeedSteeringCommand

FIELD_DEG = 100.0
INFLATE_M = 0.15 + 0.10       # half vehicle width + margin
WHEELBASE_M = 0.324
LOOKAHEAD_M = 1.0
MAX_STEER_RAD = 0.35
MAX_SPEED_MPS = 0.3
FRONT_DEG = 10.0
MAX_RANGE_M = 10.0
BIN_RAD = math.radians(0.25)


def ranges_from_points(points) -> tuple[np.ndarray, np.ndarray]:
    """Per-beam (angle, range) on the 0.25 deg grid within +-FIELD_DEG; beams with no return
    are treated as free to MAX_RANGE_M (the scan reports nothing beyond 10 m)."""
    angles = np.arange(-math.radians(FIELD_DEG), math.radians(FIELD_DEG) + BIN_RAD / 2, BIN_RAD)
    ranges = np.full(len(angles), MAX_RANGE_M)
    if points is not None and len(points):
        a = np.arctan2(points[:, 1], points[:, 0])
        r = np.hypot(points[:, 0], points[:, 1])
        index = np.round((a - angles[0]) / BIN_RAD).astype(int)
        keep = (index >= 0) & (index < len(angles))
        np.minimum.at(ranges, index[keep], r[keep])
    return angles, ranges


def extend_disparities(ranges: np.ndarray) -> np.ndarray:
    """At each jump, extend the nearer range over the beams the vehicle would clip."""
    out = ranges.copy()
    for i in range(len(ranges) - 1):
        near, far = min(ranges[i], ranges[i + 1]), max(ranges[i], ranges[i + 1])
        if far - near < 0.1:
            continue
        width = int(math.ceil(math.atan2(INFLATE_M, near) / BIN_RAD))
        if ranges[i] < ranges[i + 1]:
            lo, hi = i + 1, min(len(out), i + 1 + width)
        else:
            lo, hi = max(0, i - width + 1), i + 1
        out[lo:hi] = np.minimum(out[lo:hi], near)
    return out


@dataclass(frozen=True)
class GapFollowParams:
    """Defaults are the approved baseline A (D6). Non-default sets are proposals only.

    centering_gain: adds atan2(gain * (d_left - d_right) / 2, l_d) to the gap heading, with
    d_left/d_right the nearest returns within 80..100 deg either side (0 = A, no centering).
    side_speed_gain: also caps speed at gain * (min(d_left, d_right) - side_floor_m) (0 = off).
    """
    max_steer_rad: float = MAX_STEER_RAD
    max_speed_mps: float = MAX_SPEED_MPS
    steer_slowdown_rad: float = 0.6
    centering_gain: float = 0.0
    side_speed_gain: float = 0.0
    side_floor_m: float = 0.15


def side_minima(angles: np.ndarray, ranges: np.ndarray) -> tuple[float, float]:
    left = ranges[(angles >= math.radians(80)) & (angles <= math.radians(100))]
    right = ranges[(angles <= math.radians(-80)) & (angles >= math.radians(-100))]
    return float(left.min()), float(right.min())


def gap_follow(points, params: GapFollowParams = GapFollowParams()) -> tuple[float, float, dict]:
    """(target speed m/s, steer rad, details) from a LiDAR cloud in the vehicle-aligned frame."""
    angles, ranges = ranges_from_points(points)
    extended = extend_disparities(ranges)
    best = np.flatnonzero(extended == extended.max())
    target = best[np.argmin(np.abs(angles[best]))]   # deepest; ties -> straightest
    alpha = float(angles[target])
    left, right = side_minima(angles, ranges)
    if params.centering_gain:
        alpha += math.atan2(params.centering_gain * (min(left, 2.0) - min(right, 2.0)) / 2, LOOKAHEAD_M)
    steer = math.atan2(2 * WHEELBASE_M * math.sin(alpha), LOOKAHEAD_M)
    steer = max(-params.max_steer_rad, min(params.max_steer_rad, steer))
    front = float(ranges[np.abs(angles) <= math.radians(FRONT_DEG)].min())
    speed = min(params.max_speed_mps, params.max_speed_mps * (1 - abs(steer) / params.steer_slowdown_rad),
                0.25 * (front - 0.5))
    if params.side_speed_gain:
        speed = min(speed, params.side_speed_gain * (min(left, right) - params.side_floor_m))
    speed = max(0.0, speed)
    return speed, steer, {"alpha_rad": alpha, "depth_m": float(extended[target]), "front_m": front,
                          "left_m": left, "right_m": right}


# Lap candidate (S1-05 proposal; not approved for motion). Tuned only in the offline rollout.
LAP_PARAMS = GapFollowParams(max_steer_rad=0.35, steer_slowdown_rad=0.8, centering_gain=0.5, side_speed_gain=1.0)


class GapFollowController(ControlStrategy):
    """Reactive baseline A. Needs a 2D LiDAR; never reads the ego pose."""

    world_requirements = frozenset({WorldCapability.LIDAR_2D})
    stack_requirements = frozenset()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last = None
        self.enabled = True  # a runner may hold it at standstill (e.g. before/after a test window)
        self.params = GapFollowParams()  # baseline A; a confirmed stage may select another set (M6: LAP_PARAMS)

    def control(self, ego, plan=None, control_dt=None, perception_model=None, sensors=None):
        lidar = sensors.lidar if sensors is not None else None
        if not self.enabled:
            speed, steer, detail = 0.0, 0.0, {"reason": "disabled"}
        elif lidar is None or lidar.points is None:
            speed, steer, detail = 0.0, 0.0, {"reason": "no lidar"}
        else:
            speed, steer, detail = gap_follow(lidar.points, self.params)
        self.last = dict(detail, target_speed=speed, steer=steer)
        self.cmd = ControlCommand(steer=steer, acceleration=0.0)  # gauge mirror
        return TargetSpeedSteeringCommand(target_speed=speed, steer=steer)

    def reset(self):
        self.last = None
        self.cmd = ControlCommand()
