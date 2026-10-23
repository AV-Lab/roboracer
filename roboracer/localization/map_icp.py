"""S3-02: map-based ICP localization for B, extending AVLite's ``LidarLocalization``.

Reused unchanged from AVLite (``avlite.c10_perception.c16_localization_algs.LidarLocalization``): the
scan squashing, the point-to-point ICP loop (``_icp``) and the SVD rigid fit (``_best_fit_transform``).

Extended:
- **Map target, not the first scan.** The stock strategy aligns every scan to the first scan placed at the
  seed pose (so errors in the seed or drift are never corrected). Here the reference is the committed,
  validated C0 target (``roboracer/data/c0-icp-map.json``, S3-01), hash-checked on load.
- **KD-tree correspondences** instead of the stock brute-force search (3,152 map points, ~1,000 scan points).
- **Initialization by operator/configuration only** (``initialize(x, y, theta)``); no simulator pose is
  read. Until initialized, nothing is estimated.
- **Prediction from wheel odometry** (encoder travel since the last scan, along the estimated heading; heading
  change from the last two estimates), falling back to constant velocity when no odometry is fed. A straight
  corridor gives ICP no along-track information (found on the first offline evaluation: the estimate stood
  still while the car moved 0.5 m down the opening straight), so odometry carries that direction.
- **Initialization check** (``verify_initialization``), required before any estimate: at the configured pose
  the forward beams (+-15 deg) are compared with ranges ray-cast into the map target from the LiDAR, and the
  scan's inlier fraction is checked. The forward ranges see the end of a straight, so an along-track
  initialization error -- which a straight corridor otherwise hides from ICP (offline: a 0.5 m along-track
  offset stayed "valid but wrong" for 43 scans) -- is rejected before driving. Rejection is sticky until
  ``initialize`` is called again.
- **Degeneracy report.** The matched map normals give a 2x2 information matrix; the ratio of its eigenvalues
  says whether both directions are constrained. Below ``min_constraint_ratio`` the scan is reported
  ``degenerate`` (the weak direction rests on odometry); this is a diagnostic, not a failure by itself.
- **Match validity and loss.** Per scan: inlier fraction (points within ``inlier_m`` of the map), inlier RMS,
  and the correction from the prediction. A scan is valid when all are inside their limits; ``loss_after``
  consecutive invalid scans declare the localization lost, which is sticky until ``initialize`` is called
  again. These are match diagnostics, not a calibrated covariance.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
from scipy.spatial import cKDTree

from avlite.c10_perception.c16_localization_algs import LidarLocalization
from avlite.c10_perception.c19_settings import PerceptionSettings

MAP_FILE = Path(__file__).resolve().parents[1] / "data/c0-icp-map.json"
MAP_PROVENANCE = Path(__file__).resolve().parents[1] / "data/c0-icp-map.provenance.json"


def load_map(map_file: Path = MAP_FILE, provenance_file: Path = MAP_PROVENANCE) -> tuple[np.ndarray, str]:
    raw = Path(map_file).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if json.loads(Path(provenance_file).read_text()).get("map_sha256") != digest:
        raise ValueError(f"{Path(map_file).name} does not match its provenance record")
    points = np.asarray(json.loads(raw)["points"], dtype=float)
    if points.ndim != 2 or points.shape[1] != 2 or len(points) < 100:
        raise ValueError("ICP map must hold at least 100 (x, y) points")
    return points, digest


def _map_normals(points: np.ndarray, tree) -> np.ndarray:
    """Unit normal of the map at every target point, from its local neighbourhood (PCA, 5 neighbours)."""
    _, idx = tree.query(points, k=5)
    normals = np.empty_like(points)
    for i, neighbours in enumerate(idx):
        local = points[neighbours] - points[neighbours].mean(axis=0)
        _, vectors = np.linalg.eigh(local.T @ local)
        normals[i] = vectors[:, 0]
    return normals


def _wrap(angle: float) -> float:
    return math.remainder(angle, math.tau)


class MapIcpLocalization(LidarLocalization):
    """Scan-to-map ICP on the validated C0 target, with validity and loss reporting."""

    stack_requirements = frozenset()  # carries its own validated map target

    def __init__(self, perception_model, setting=PerceptionSettings, *, map_file: Path = MAP_FILE,
                 provenance_file: Path = MAP_PROVENANCE, max_correspondence_m: float = 0.3, max_iterations: int = 30,
                 tolerance_m: float = 1e-4, inlier_m: float = 0.05, min_inlier_fraction: float = 0.7,
                 max_inlier_rms_m: float = 0.03, max_correction_m: float = 0.25, max_correction_rad: float = 0.2,
                 loss_after: int = 3, min_constraint_ratio: float = 0.05):
        super().__init__(perception_model, setting)
        self._max_correspondence_dist = max_correspondence_m
        self._max_iterations = max_iterations
        self._tolerance = tolerance_m
        map_points, self.map_sha256 = load_map(map_file, provenance_file)
        self._map = map_points
        self._tree = cKDTree(map_points)
        self._normals = _map_normals(map_points, self._tree)
        self._odometry_m = 0.0
        self._odometry_used = False  # set once odometry is fed; then prediction uses it
        self.limits = {"inlier_m": inlier_m, "min_inlier_fraction": min_inlier_fraction,
                       "max_inlier_rms_m": max_inlier_rms_m, "max_correction_m": max_correction_m,
                       "max_correction_rad": max_correction_rad, "loss_after": loss_after,
                       "min_constraint_ratio": min_constraint_ratio}
        self._initialized = False
        self._history: list[tuple[float, float, float, float]] = []  # (stamp, x, y, theta)
        self.status = {"state": "uninitialized"}

    # -- operator/configuration initialization -------------------------------------------------
    def initialize(self, x: float, y: float, theta: float, source: str = "configuration") -> None:
        """Operator/configuration pose; estimation starts only after ``verify_initialization`` accepts it."""
        self._x, self._y, self._theta = float(x), float(y), float(theta)
        self._history = []
        self._invalid_run = 0
        self._odometry_m = 0.0
        self._initialized = True
        self._verified = False
        self.status = {"state": "initialized", "source": source, "pose": [self._x, self._y, self._theta]}

    def _ray_range(self, origin: np.ndarray, direction: np.ndarray, max_range: float = 10.0,
                   half_width: float = 0.03) -> float:
        """Range from ``origin`` along unit ``direction`` to the nearest map point within ``half_width`` of the ray."""
        rel = self._map - origin
        t = rel @ direction
        lateral = np.abs(rel[:, 0] * direction[1] - rel[:, 1] * direction[0])
        hit = (t > 0.05) & (t <= max_range) & (lateral <= half_width)
        return float(t[hit].min()) if hit.any() else math.inf

    def verify_initialization(self, sensors, forward_deg: float = 15.0, max_range_error_m: float = 0.10,
                              min_inlier_fraction: float = 0.7) -> dict:
        """Check the configured pose against the first scan before any estimate (see module notes)."""
        if not self._initialized:
            raise RuntimeError("initialize() first")
        lidar = sensors.get_lidar() if sensors is not None else None
        if lidar is None or lidar.points is None or len(lidar.points) < 10:
            return {"accepted": False, "reason": "no scan"}
        body = lidar.to_base(lidar.points)[:, :2]
        # ICP from the configured pose first (small offsets are corrected); the checks run at the refined pose.
        # Along a straight ICP cannot move the pose along-track, so an along-track error survives to the
        # forward-range check below.
        x, y, theta = self._icp(body, self._map, self._x, self._y, self._theta)
        theta = _wrap(theta)
        correction_m = math.hypot(x - self._x, y - self._y)
        correction_rad = abs(_wrap(theta - self._theta))
        c, s = math.cos(theta), math.sin(theta)
        rot = np.array([[c, s], [-s, c]])
        pose_xy = np.array([x, y])
        mount = np.asarray(lidar.base_to_sensor[:2, 3], dtype=float)
        world = body @ rot + pose_xy
        origin = mount @ rot + pose_xy
        rel_body = body - mount
        bearing = np.degrees(np.arctan2(rel_body[:, 1], rel_body[:, 0]))
        errors = []
        for point in world[np.abs(bearing) <= forward_deg]:
            measured = float(np.linalg.norm(point - origin))
            predicted = self._ray_range(origin, (point - origin) / max(measured, 1e-9))
            if math.isfinite(predicted):
                errors.append(measured - predicted)
        d, _ = self._tree.query(world)
        fraction = float(np.mean(d <= self.limits["inlier_m"]))
        median_error = float(np.median(np.abs(errors))) if errors else math.inf
        accepted = (bool(errors) and median_error <= max_range_error_m and fraction >= min_inlier_fraction
                    and correction_m <= self.limits["max_correction_m"]
                    and correction_rad <= self.limits["max_correction_rad"])
        result = {"accepted": accepted, "refined_pose": [x, y, theta], "correction_m": correction_m,
                  "correction_rad": correction_rad,
                  "forward_beams": len(errors), "forward_range_error_median_m": median_error,
                  "forward_range_error_signed_median_m": float(np.median(errors)) if errors else None,
                  "inlier_fraction": fraction, "limits": {"forward_deg": forward_deg,
                  "max_range_error_m": max_range_error_m, "min_inlier_fraction": min_inlier_fraction}}
        self._verified = accepted
        if accepted:
            self._x, self._y, self._theta = x, y, theta
        self.status = dict(self.status, state="verified" if accepted else "init-rejected", initialization=result)
        return result

    def reset(self):
        """Forget the estimate; the map target stays (unlike the stock reset, which drops its first-scan map)."""
        self._x = self._y = self._theta = None
        self._initialized = False
        self._verified = False
        self._history = []
        self.status = {"state": "uninitialized"}

    @property
    def valid(self) -> bool:
        return self.status.get("state") == "valid"

    @property
    def lost(self) -> bool:
        return self.status.get("state") == "lost"

    # -- AVLite hooks --------------------------------------------------------------------------
    def _nearest_neighbours(self, src: np.ndarray, dst: np.ndarray):
        """KD-tree over the map target (``dst`` is always the target here)."""
        dists, idx = self._tree.query(src)
        return idx, dists

    def add_odometry(self, travel_m: float) -> None:
        """Wheel-encoder travel (m, signed) since the previous call; consumed by the next scan's prediction."""
        if math.isfinite(travel_m):
            self._odometry_m += float(travel_m)
            self._odometry_used = True

    def _predict(self, stamp: float) -> tuple[float, float, float]:
        yaw_rate_step = 0.0
        if len(self._history) >= 2:
            (t0, _, _, th0), (t1, _, _, th1) = self._history[-2:]
            if t1 - t0 > 1e-3:
                yaw_rate_step = _wrap(th1 - th0) / (t1 - t0) * max(0.0, stamp - t1)
        if self._odometry_used:
            d, heading = self._odometry_m, self._theta + yaw_rate_step / 2
            return self._x + d * math.cos(heading), self._y + d * math.sin(heading), self._theta + yaw_rate_step
        if len(self._history) < 2:
            return self._x, self._y, self._theta
        (t0, x0, y0, th0), (t1, x1, y1, th1) = self._history[-2:]
        dt_hist = t1 - t0
        if dt_hist <= 1e-3:
            return x1, y1, th1
        k = (stamp - t1) / dt_hist
        return x1 + k * (x1 - x0), y1 + k * (y1 - y0), th1 + k * _wrap(th1 - th0)

    def localize(self, perception_model=None, sensors=None) -> None:
        if perception_model is not None:
            self.perception_model = perception_model
        if not self._initialized or not getattr(self, "_verified", False) or self.lost:
            return
        lidar = sensors.get_lidar() if sensors is not None else None
        if lidar is None or lidar.points is None:
            return
        scan = self._squash(lidar.to_base(lidar.points))
        if scan is None or len(scan) < 10:
            return
        stamp = float(getattr(lidar, "stamp", None) or time.monotonic())
        started = time.perf_counter()
        px, py, pth = self._predict(stamp)
        odometry_m, self._odometry_m = self._odometry_m, 0.0
        x, y, theta = self._icp(scan, self._map, px, py, pth)
        theta = _wrap(theta)

        c, s = math.cos(theta), math.sin(theta)
        d, idx = self._tree.query(scan @ np.array([[c, s], [-s, c]]) + np.array([x, y]))
        inliers = d <= self.limits["inlier_m"]
        normals = self._normals[idx[inliers]]
        info = normals.T @ normals if len(normals) else np.zeros((2, 2))
        eig = np.linalg.eigvalsh(info)
        constraint_ratio = float(eig[0] / eig[1]) if eig[1] > 0 else 0.0
        weak_axis = np.linalg.eigh(info)[1][:, 0] if eig[1] > 0 else np.array([1.0, 0.0])
        fraction = float(inliers.mean())
        rms = float(np.sqrt(np.mean(d[inliers] ** 2))) if inliers.any() else math.inf
        correction_m = math.hypot(x - px, y - py)
        correction_rad = abs(_wrap(theta - pth))
        checks = {"inlier_fraction": fraction >= self.limits["min_inlier_fraction"],
                  "inlier_rms": rms <= self.limits["max_inlier_rms_m"],
                  "correction_m": correction_m <= self.limits["max_correction_m"],
                  "correction_rad": correction_rad <= self.limits["max_correction_rad"]}
        valid = all(checks.values())
        self._invalid_run = 0 if valid else self._invalid_run + 1
        state = "valid" if valid else ("lost" if self._invalid_run >= self.limits["loss_after"] else "invalid")
        self.status = {"state": state, "stamp": stamp, "pose": [x, y, theta], "predicted": [px, py, pth],
                       "inlier_fraction": fraction, "inlier_rms_m": rms, "correction_m": correction_m,
                       "correction_rad": correction_rad, "failed": [k for k, ok in checks.items() if not ok],
                       "constraint_ratio": constraint_ratio, "degenerate": constraint_ratio < self.limits["min_constraint_ratio"],
                       "weak_axis": [float(weak_axis[0]), float(weak_axis[1])], "odometry_m": odometry_m,
                       "points": int(len(scan)), "compute_s": time.perf_counter() - started}
        if valid:
            self._x, self._y, self._theta = x, y, theta
            self._history = (self._history + [(stamp, x, y, theta)])[-2:]
            ego = self.perception_model.ego_vehicle
            ego.x, ego.y, ego.theta = x, y, theta
