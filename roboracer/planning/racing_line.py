"""Minimum-curvature racing line (S3, D30/D31: ported from A2RL).

Port of ``planning/racing_line.py`` in the A2RL plugin (AV-Lab/a2rl ``dev`` 0b5cfa8):
``_normal_at`` and ``generate_min_curvature_racing_line_candidate``. Unchanged algorithm: the line is
the reference moved along its normals by offsets d; minimise the summed squared second differences of
the moved points (a curvature proxy) with L-BFGS-B, each offset bounded by the track bounds less a
margin; optional pinned offset windows (e.g. at the start) and curvature reweighting toward a min-max
curvature line. Only the default margin differs (A2RL: 2.5 m on a ~3 km track).
"""

from __future__ import annotations

import math

from .velocity_profile import build_path_curvature_envelope, is_closed_path


def _normal_at(path, idx: int, closed: bool) -> tuple[float, float]:
    """Unit left normal of the central difference at ``idx``."""
    n_points = len(path)
    if n_points < 2:
        return (0.0, 1.0)
    if closed:
        prev_idx = (idx - 1) % n_points
        next_idx = (idx + 1) % n_points
    else:
        prev_idx = max(0, idx - 1)
        next_idx = min(n_points - 1, idx + 1)
    dx = path[next_idx][0] - path[prev_idx][0]
    dy = path[next_idx][1] - path[prev_idx][1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (0.0, 1.0)
    return (-dy / length, dx / length)


def generate_min_curvature_racing_line_candidate(
    path,
    left_bound,
    right_bound,
    *,
    boundary_margin_m: float = 0.3,
    pinned_offsets: dict[int, tuple[float, float]] | None = None,
    reweight_iterations: int = 0,
    reweight_window_m: float = 0.4,
) -> dict:
    """``path`` is closed (last point == first); ``left_bound``/``right_bound`` are signed lateral
    offsets of the edges along the left normal (left > 0 > right), one per path point."""
    import numpy as np
    from scipy.optimize import minimize

    if not is_closed_path(path):
        raise ValueError("min-curvature racing line requires a closed path")
    base_path = path[:-1]
    n = len(base_path)
    base = np.array(base_path, dtype=float)
    normals = np.array([_normal_at(base_path, idx, True) for idx in range(n)])
    margin = max(0.0, float(boundary_margin_m))
    lower = np.array(right_bound[:n], dtype=float) + margin
    upper = np.array(left_bound[:n], dtype=float) - margin
    for idx, (low, high) in (pinned_offsets or {}).items():
        lower[idx] = max(lower[idx], float(low))
        upper[idx] = min(upper[idx], float(high))
    if np.any(lower > upper):
        raise ValueError("boundary margin leaves no feasible offset at some points")

    index = np.arange(n)
    ax = np.zeros((n, n))
    ay = np.zeros((n, n))
    for coefficient, shift in ((1.0, -1), (-2.0, 0), (1.0, 1)):
        column = (index + shift) % n
        ax[index, column] += coefficient * normals[column, 0]
        ay[index, column] += coefficient * normals[column, 1]
    second_difference = np.roll(base, 1, 0) - 2.0 * base + np.roll(base, -1, 0)
    operator = np.vstack([ax, ay])
    target = np.r_[second_difference[:, 0], second_difference[:, 1]]

    def solve(weights, start):
        root = np.sqrt(np.r_[weights, weights])
        weighted = operator * root[:, None]
        hessian = weighted.T @ weighted
        linear = weighted.T @ (target * root)
        return minimize(
            lambda x: (float(x @ hessian @ x / 2.0 + linear @ x), hessian @ x + linear),
            start, jac=True, method="L-BFGS-B", bounds=list(zip(lower, upper)),
            options={"maxiter": 20000, "maxfun": 40000})

    result = solve(np.ones(n), np.clip(np.zeros(n), lower, upper))
    converged = bool(result.success)
    for _ in range(max(0, int(reweight_iterations))):
        line = base + normals * result.x[:, None]
        closed_line = [tuple(point) for point in line] + [tuple(line[0])]
        curvature = np.array(
            build_path_curvature_envelope(closed_line, curvature_window_m=reweight_window_m, curvature_hold_m=0.0)[:-1])
        weights = np.clip(curvature / max(float(np.mean(curvature)), 1.0e-9), 0.2, 50.0)
        result = solve(weights, result.x)
        converged = converged and bool(result.success)
    offsets = [float(value) for value in result.x]
    candidate_path = [(float(base[idx, 0] + normals[idx, 0] * offsets[idx]),
                       float(base[idx, 1] + normals[idx, 1] * offsets[idx])) for idx in range(n)]
    candidate_path.append(candidate_path[0])
    offsets.append(offsets[0])
    return {"schema_version": 1, "method": "min_curvature_l_bfgs_b", "boundary_margin_m": margin,
            "reweight_iterations": max(0, int(reweight_iterations)), "optimizer_converged": converged,
            "offset_d_m": offsets, "candidate_path": candidate_path}
