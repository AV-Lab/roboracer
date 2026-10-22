"""Closed-lap s/d projection on AVLite's tracker (S3, D30/D31: ported from A2RL).

Port of ``planning/trajectory_tracker.py`` ``A2RLTrajectoryTracker`` in the A2RL plugin (AV-Lab/a2rl
``dev`` 0b5cfa8), unchanged: nearest waypoint by KD-tree, then the best projection over the five
neighbouring segments (plus the closing segment near the seam), so s does not jump at the lap seam.
"""

from __future__ import annotations

import math

import numpy as np
from scipy.spatial import KDTree

from avlite.c50_common.c54_trajectory_tracker import TrajectoryTracker


class LapTrajectoryTracker(TrajectoryTracker):
    """Resolve nearest-segment ambiguity around a duplicated lap seam."""

    def initialize_trajectory(self, reference_xy_path, velocity):
        super().initialize_trajectory(reference_xy_path, velocity)
        self._lap_path = np.asarray(reference_xy_path, dtype=float)
        self._lap_kdtree = KDTree(self._lap_path) if len(self._lap_path) else None

    def _is_closed_loop(self) -> bool:
        return len(self._lap_path) > 2 and np.linalg.norm(self._lap_path[0] - self._lap_path[-1]) < 1e-6

    def _candidate_segments(self, closest_wp: int) -> list[tuple[int, int]]:
        n = len(self._lap_path)
        candidates = {(previous, previous + 1) for previous in range(closest_wp - 2, closest_wp + 3)
                      if 0 <= previous < n - 1}
        if self._is_closed_loop() and closest_wp <= 1:
            candidates.add((n - 2, n - 1))
        return sorted(candidates)

    def _project_segment(self, point, previous_wp: int, next_wp: int) -> tuple[float, float, float]:
        start = self._lap_path[previous_wp]
        segment = self._lap_path[next_wp] - start
        segment_len_sq = float(np.dot(segment, segment))
        offset = point - start
        if segment_len_sq <= 1e-12:
            return float(self.path_s[previous_wp]), 0.0, float(np.dot(offset, offset))
        projection_ratio = float(np.dot(offset, segment) / segment_len_sq)
        clamped_ratio = max(0.0, min(1.0, projection_ratio))
        projection = start + clamped_ratio * segment
        residual = point - projection
        segment_length = math.sqrt(segment_len_sq)
        normal = np.array([-segment[1], segment[0]])
        s_m = float(self.path_s[previous_wp] + projection_ratio * segment_length)
        d_m = float(np.dot(residual, normal) / segment_length)
        return s_m, d_m, float(np.dot(residual, residual))

    def _project_points(self, points) -> np.ndarray:
        points_array = np.asarray(points, dtype=float)
        if points_array.ndim == 1:
            points_array = points_array.reshape(1, 2)
        sample_count = points_array.shape[0]
        path_count = len(self._lap_path)
        if path_count == 0:
            return np.zeros((sample_count, 2))
        if path_count == 1:
            lateral = np.linalg.norm(points_array - self._lap_path[0], axis=1)
            return np.column_stack((np.zeros(sample_count), lateral))
        _, closest_waypoints = self._lap_kdtree.query(points_array)
        output = np.empty((sample_count, 2), dtype=float)
        for index, point in enumerate(points_array):
            candidates = self._candidate_segments(int(closest_waypoints[index]))
            best = min((self._project_segment(point, p, n) for p, n in candidates), key=lambda pr: pr[2])
            output[index] = best[:2]
        return output

    def convert_xy_path_to_sd_path(self, points):
        projected = self._project_points(points)
        return projected[:, 0], projected[:, 1]

    def convert_xy_path_to_sd_path_np(self, points):
        return self._project_points(points)

    def update_waypoint_by_xy(self, x_current: float, y_current: float) -> None:
        if self._lap_kdtree is None:
            return
        _, closest_wp = self._lap_kdtree.query((x_current, y_current))
        closest_wp = int(closest_wp)
        s_values, _ = self.convert_xy_path_to_sd_path([(x_current, y_current)])
        s_m = float(s_values[0])
        if closest_wp == 0 and self._is_closed_loop() and len(self.path_s) > 1 and s_m > self.path_s[1]:
            closest_wp = int(self.get_closest_waypoint_frm_sd(s_m, 0.0))
        if self.path_s[closest_wp] <= s_m:
            self.current_wp = closest_wp
            self.next_wp = min(closest_wp + 1, len(self._lap_path) - 1)
        elif closest_wp > 0:
            self.current_wp = closest_wp - 1
            self.next_wp = closest_wp
