"""Scan-derived static obstacles on C0 (S4-01, D56).

AVLite's ``FastBEVLidarDetection`` (ordered-scan gap segmentation + rotating-calipers rectangle, in the map
frame through the stack's own pose estimate) is reused, with three C0 additions:

- **Wall subtraction.** Scan points within ``wall_band_m`` (0.05 m) of the validated S3 ICP wall map are walls,
  not obstacles, and are removed before segmentation.
- **Quality.** A cluster needs ``min_points`` (4) points, and an obstacle is reported only once a cluster within
  ``confirm_radius_m`` of it was also seen on the previous scan (2 consecutive scans).
- **Freshness.** Each result carries the stamp of the scan it came from (``obstacles_stamp``); the stage stops
  the car when it is older than 0.5 s (D56).

Obstacles go into ``PerceptionModel.agent_vehicles`` as stationary agents (velocity 0): that is the list AVLite's
lattice collision check reads (``c55_collision_checking``). The scan is the only input besides the stack's pose;
no obstacle geometry or simulator truth is read here.

One deviation from ``FastBEVLidarDetection``: when a cluster is seen edge-on (a sliver), AVLite substitutes a
default car-sized box. On C0 the obstacles are boxes and a barrier, so the observed face length is kept and only
the unseen depth is defaulted (``default_depth_m``), extending away from the car. A fitted extent below
``min_extent_m`` (0.15 m) counts as unseen: in the S4 stationary check a 0.25 m box seen nearly face-on fitted
0.08 m deep, which put its centre 8 cm towards the car.
"""

from __future__ import annotations

import math

import numpy as np

from avlite.c10_perception.c11_perception_model import AgentState
from avlite.c10_perception.c15_perception_algs import FastBEVLidarDetection

from ..localization.map_icp import load_map


class ScanObstacleDetection(FastBEVLidarDetection):
    """D56 obstacle detection: wall-map subtraction + AVLite BEV detection, with confirmation and a stamp."""

    def __init__(self, wall_band_m: float = 0.05, min_points: int = 4, confirm_radius_m: float = 0.15,
                 max_range_m: float = 10.0, mu: float = 0.10, delta_min: float = 0.05, delta_max: float = 3.0,
                 min_extent_m: float = 0.15, default_depth_m: float = 0.25):
        super().__init__(mu=mu, delta_min=delta_min, delta_max=delta_max, min_length=min_extent_m,
                         min_width=min_extent_m, default_length=default_depth_m, default_width=default_depth_m)
        from scipy.spatial import cKDTree
        points, self.map_sha256 = load_map()
        self._walls = cKDTree(points)
        self.wall_band_m, self.min_points = float(wall_band_m), int(min_points)
        self.confirm_radius_m, self.max_range_m = float(confirm_radius_m), float(max_range_m)
        self.default_depth_m = float(default_depth_m)
        self.reset()

    def reset(self):
        self._previous: list[tuple[float, float]] = []
        self._last_stamp = None
        self.obstacles: list[AgentState] = []
        self.obstacles_stamp = None
        self.status = {"scans": 0, "candidates": 0, "confirmed": 0, "wall_points": 0, "free_points": 0}

    def _fit_rectangle(self, cluster: np.ndarray, ego=(0.0, 0.0, 0.0)) -> AgentState | None:
        if len(cluster) < 2:
            return None
        hull = self._convex_hull(cluster)
        cx, cy, theta, length, width = self._min_bounding_rect(hull)
        if length < self._min_length or width < self._min_width:
            # Edge-on: keep the seen face, default only the unseen depth, behind the face as seen from the car.
            face = max(length, width)
            face_dir = (math.cos(theta), math.sin(theta)) if length >= width else (-math.sin(theta), math.cos(theta))
            normal = (-face_dir[1], face_dir[0])
            if normal[0] * (cx - ego[0]) + normal[1] * (cy - ego[1]) < 0.0:
                normal = (-normal[0], -normal[1])
            cx += normal[0] * self.default_depth_m / 2
            cy += normal[1] * self.default_depth_m / 2
            theta = math.atan2(face_dir[1], face_dir[0])
            length, width = face, self.default_depth_m
        return AgentState(x=cx, y=cy, theta=theta, length=length, width=width, velocity=0.0)

    def candidates(self, points_map: np.ndarray, ego) -> list[tuple[AgentState, int]]:
        """Obstacle candidates (with their point counts) from ordered map-frame scan points."""
        xy = np.asarray(points_map, dtype=float)[:, :2]
        if len(xy) == 0:
            return []
        near = np.hypot(xy[:, 0] - ego.x, xy[:, 1] - ego.y) <= self.max_range_m
        distance, _ = self._walls.query(xy)
        free = near & (distance > self.wall_band_m)
        self.status["wall_points"] = int(np.count_nonzero(near & ~free))
        self.status["free_points"] = int(np.count_nonzero(free))
        out = []
        # Segment on the free points in scan order; a removed wall point between two free points splits them too.
        index = np.flatnonzero(free)
        if len(index) == 0:
            return out
        runs = np.split(index, np.flatnonzero(np.diff(index) > 1) + 1)
        for run in runs:
            for cluster in self._segment(xy[run]):
                if len(cluster) < self.min_points:
                    continue
                agent = self._fit_rectangle(cluster, (ego.x, ego.y, ego.theta))
                if agent is not None:
                    out.append((agent, len(cluster)))
        return out

    def detect(self, perception_model=None, sensors=None, rgb_img=None, depth_img=None, lidar_data=None):
        if perception_model is None:
            raise ValueError("perception_model is required for detection")
        lidar = sensors.get_lidar() if sensors is not None else None
        if lidar is None or lidar.points is None:
            perception_model.agent_vehicles = []
            return perception_model
        if lidar.stamp != self._last_stamp:  # each scan once: the stack ticks faster than scans arrive
            self._last_stamp = lidar.stamp
            ego = perception_model.ego_vehicle
            points = np.asarray(lidar.to_map(lidar.points, ego), dtype=float)
            found = self.candidates(points, ego)
            confirmed = [a for a, _ in found
                         if any(math.hypot(a.x - px, a.y - py) <= self.confirm_radius_m for px, py in self._previous)]
            self._previous = [(a.x, a.y) for a, _ in found]
            self.obstacles = confirmed
            self.obstacles_stamp = lidar.stamp
            self.status.update(scans=self.status["scans"] + 1, candidates=len(found), confirmed=len(confirmed))
        perception_model.agent_vehicles = list(self.obstacles)
        return perception_model
