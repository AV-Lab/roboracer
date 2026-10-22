"""C0 (Proto Track) driving plan for B (S3): reference, bounds, A2RL racing line and velocity profile.

Inputs: a closed reference polyline in driving order and the drivable region (a polygon with holes),
both from the collider-extracted C0 geometry. Output: an AVLite ``GlobalPlan`` file payload
(``ReferenceLine``, ``LeftBound``/``RightBound`` as signed offsets along the left normal, left > 0 >
right, and ``ReferenceSpeed``), with provenance. The A2RL generator then moves the reference onto the
min-curvature line and the A2RL profile fills the speeds (racing_line.py, velocity_profile.py).
"""

from __future__ import annotations

import math

from .racing_line import _normal_at, generate_min_curvature_racing_line_candidate
from .velocity_profile import (VelocityProfileConfig, build_friction_limited_velocity_profile,
                               estimate_profile_time_sec, is_closed_path)


def resample_closed(points, spacing_m: float):
    """Closed polyline resampled at (about) ``spacing_m`` by arc length; last point == first."""
    pts = [tuple(map(float, p[:2])) for p in points]
    if math.dist(pts[0], pts[-1]) > 1e-9:
        pts.append(pts[0])
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a, b))
    count = max(8, int(round(s[-1] / spacing_m)))
    step = s[-1] / count
    out, j = [], 0
    for k in range(count):
        target = k * step
        while s[j + 1] < target:
            j += 1
        t = (target - s[j]) / max(1e-12, s[j + 1] - s[j])
        out.append((pts[j][0] + t * (pts[j + 1][0] - pts[j][0]), pts[j][1] + t * (pts[j + 1][1] - pts[j][1])))
    out.append(out[0])
    return out


def lateral_bounds(path, region, max_ray_m: float = 5.0, step_m: float = 0.005):
    """Signed distances along each point's left normal to the region boundary: (left > 0, right < 0).
    Found by marching the normal ray until it leaves the region, then bisecting to ``step_m``."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    inside = prep(region)
    base = path[:-1]
    left, right = [], []
    for idx, (x, y) in enumerate(base):
        nx, ny = _normal_at(base, idx, True)
        if not inside.contains(Point(x, y)):
            raise ValueError(f"reference point {idx} lies outside the drivable region")
        for sign, out in ((1.0, left), (-1.0, right)):
            lo, hi = 0.0, None
            d = 0.05
            while d <= max_ray_m:
                if not inside.contains(Point(x + sign * d * nx, y + sign * d * ny)):
                    hi = d
                    break
                lo = d
                d += 0.05
            if hi is None:
                raise ValueError(f"no boundary within {max_ray_m} m at point {idx}")
            while hi - lo > step_m:
                mid = 0.5 * (lo + hi)
                if inside.contains(Point(x + sign * mid * nx, y + sign * mid * ny)):
                    lo = mid
                else:
                    hi = mid
            out.append(sign * lo)
    left.append(left[0])
    right.append(right[0])
    return left, right


def build_c0_plan(reference, region, *, spacing_m: float, boundary_margin_m: float, profile: VelocityProfileConfig,
                  start_pin_m: float | None = None, reweight_iterations: int = 0, reweight_window_m: float = 0.4):
    """Reference → bounds → A2RL min-curvature line (margin from each edge) → A2RL velocity profile.

    ``start_pin_m`` keeps the line's offset at the first point within +-start_pin_m of the reference,
    so the line starts where the car is spawned (A2RL pins its start the same way)."""
    path = resample_closed(reference, spacing_m)
    left, right = lateral_bounds(path, region)
    pins = {0: (-start_pin_m, start_pin_m)} if start_pin_m is not None else None
    line = generate_min_curvature_racing_line_candidate(
        path, left, right, boundary_margin_m=boundary_margin_m, pinned_offsets=pins,
        reweight_iterations=reweight_iterations, reweight_window_m=reweight_window_m)
    race = line["candidate_path"]
    offsets = line["offset_d_m"]
    # Bounds move with the line (as A2RL's export_candidate_trajectory_payload does).
    race_left = [l - o for l, o in zip(left, offsets)]
    race_right = [r - o for r, o in zip(right, offsets)]
    speed = build_friction_limited_velocity_profile(race, profile)
    assert is_closed_path(race) and len(speed) == len(race)
    # Points within bounds do not keep the segments between them inside: check the whole polyline.
    from shapely.geometry import LineString
    polyline = LineString(race)
    if not region.contains(polyline):
        raise ValueError("racing line leaves the drivable region between points; use a finer spacing")
    if polyline.distance(region.boundary) < boundary_margin_m - 0.02:
        raise ValueError("racing line segments come closer to an edge than the margin; use a finer spacing")
    payload = {"ReferenceLine": [[x, y, 0.0] for x, y in race], "LeftBound": race_left, "RightBound": race_right,
               "ReferenceSpeed": speed, "Direction": "driving order", "Environment": "C0 Proto Track"}
    report = {"points": len(race) - 1, "spacing_m": spacing_m, "boundary_margin_m": boundary_margin_m,
              "optimizer_converged": line["optimizer_converged"], "reweight_iterations": reweight_iterations,
              "reference_length_m": _length(path), "line_length_m": _length(race),
              "min_edge_clearance_m": min(min(l, -r) for l, r in zip(race_left, race_right)),
              "min_polyline_clearance_m": polyline.distance(region.boundary),
              "max_abs_offset_m": max(abs(o) for o in offsets),
              "profile": {"min_mps": min(speed), "max_mps": max(speed),
                          "estimated_lap_s": estimate_profile_time_sec(race, speed)}}
    return payload, report


def _length(path) -> float:
    return sum(math.dist(a, b) for a, b in zip(path, path[1:]))
