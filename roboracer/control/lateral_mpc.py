"""Linear time-varying lateral MPC (S3, D30/D31: ported from A2RL).

Port of ``control/lateral_mpc.py`` in the A2RL plugin (AV-Lab/a2rl ``dev`` 0b5cfa8); the algorithm and
code are unchanged, only the defaults are C0 values (wheelbase 0.324 m, 30 deg wheel limit; A2RL:
3.1 m, 0.342 rad). A2RL's description follows.

Linear time-varying lateral MPC on path-relative error states.

States x = [e_y, e_psi, delta]: lateral error (m, positive left of the path),
heading error (rad, vehicle heading minus path heading) and the actual road-wheel
angle, which follows the command through a first-order lag. The kinematic
bicycle, linearised about the path, gives over one step of length dt:

    e_y'   = v * e_psi
    e_psi' = v / L * delta - v * kappa_us(s),   kappa_us = (1 + K_us v^2 / L) kappa
    delta' = (u - delta) / tau

Understeer is load dependent: the car needs more wheel angle than the
geometric atan(L kappa) to hold a corner, but responds to steering on a
straight with the plain kinematic gain. So K_us scales the curvature the
wheels must produce (the feedforward becomes atan((L + K_us v^2) kappa))
rather than weakening the steering gain, which on straights would over-drive
the car. The pose the controller receives is ~0.1 s old, so ``advance`` rolls the
measured errors forward through that dead time with the wheel angles applied
meanwhile before the horizon is solved.

The previewed path curvature enters as a known disturbance, so the controller
starts turning before the curvature arrives. The finite-horizon cost

    sum_k  q_y e_y^2 + q_psi e_psi^2 + r_ff (u_k - u_ff,k)^2 + r_du (u_k - u_{k-1})^2

is minimised in closed form (dense least squares; no QP solver needed for a
3-state, ~25-step horizon). The road-wheel limit is applied by clipping the
first move, which is what the controller sends.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class LateralMpcConfig:
    horizon_steps: int = 25
    dt_s: float = 0.02
    wheelbase_m: float = 0.324
    steer_lag_s: float = 0.08
    q_lateral: float = 1.0
    q_heading: float = 10.0
    r_feedforward: float = 20.0
    r_rate: float = 200.0
    max_wheel_angle_rad: float = 0.5236
    understeer_gradient_s2pm: float = 0.0


class LateralMpc:
    def __init__(self, config: LateralMpcConfig | None = None):
        self.config = config or LateralMpcConfig()

    def effective_wheelbase_m(self, speed_mps: float) -> float:
        return self.config.wheelbase_m + self.config.understeer_gradient_s2pm * float(speed_mps) ** 2

    def advance(
        self,
        speed_mps: float,
        lateral_error_m: float,
        heading_error_rad: float,
        steps: list[tuple[float, float, float]],
    ) -> tuple[float, float]:
        """Roll path errors forward through ``steps`` of (dt, wheel angle, curvature)."""
        v = max(0.0, float(speed_mps))
        wheelbase = self.config.wheelbase_m
        scale = self.effective_wheelbase_m(v) / wheelbase
        e_y, e_psi = float(lateral_error_m), float(heading_error_rad)
        for dt, delta, kappa in steps:
            e_y += v * math.sin(e_psi) * dt
            e_psi += (v / wheelbase * math.tan(delta) - v * scale * kappa) * dt
        return e_y, e_psi

    def solve(
        self,
        speed_mps: float,
        lateral_error_m: float,
        heading_error_rad: float,
        current_steer_rad: float,
        previous_command_rad: float,
        preview_curvature_1pm: list[float],
    ) -> dict[str, float]:
        """Return the first steering move and the predicted terminal errors.

        ``preview_curvature_1pm`` holds the path curvature at each of the next
        ``horizon_steps`` steps (s + v * k * dt).
        """
        cfg = self.config
        n = int(cfg.horizon_steps)
        if len(preview_curvature_1pm) < n:
            raise ValueError("preview curvature must cover the horizon")
        v = max(1.0, float(speed_mps))
        dt = float(cfg.dt_s)
        lag = max(dt, float(cfg.steer_lag_s))
        wheelbase = cfg.wheelbase_m
        a = np.array([
            [1.0, v * dt, 0.0],
            [0.0, 1.0, v / wheelbase * dt],
            [0.0, 0.0, 1.0 - dt / lag],
        ])
        b = np.array([0.0, 0.0, dt / lag])
        kappa = np.asarray(preview_curvature_1pm[:n], dtype=float) * (self.effective_wheelbase_m(v) / wheelbase)
        disturbance = np.zeros((n, 3))
        disturbance[:, 1] = -v * kappa * dt

        # Predicted state k+1 = A^(k+1) x0 + sum_j A^(k-j) (B u_j + d_j).
        x0 = np.array([lateral_error_m, heading_error_rad, current_steer_rad], dtype=float)
        powers = [np.eye(3)]
        for _ in range(n):
            powers.append(a @ powers[-1])
        free = np.zeros((n, 3))
        forced = np.zeros((n, 3, n))
        for k in range(n):
            free[k] = powers[k + 1] @ x0
            for j in range(k + 1):
                free[k] += powers[k - j] @ disturbance[j]
                forced[k, :, j] = powers[k - j] @ b

        # Stack weighted residuals: tracking errors, deviation from feedforward,
        # and command rate (first move measured against the previous command).
        rows = []
        targets = []
        sq_y, sq_psi = math.sqrt(cfg.q_lateral), math.sqrt(cfg.q_heading)
        for k in range(n):
            rows.append(sq_y * forced[k, 0]); targets.append(-sq_y * free[k, 0])
            rows.append(sq_psi * forced[k, 1]); targets.append(-sq_psi * free[k, 1])
        feedforward = np.arctan(wheelbase * kappa)
        sq_ff = math.sqrt(cfg.r_feedforward)
        for k in range(n):
            row = np.zeros(n); row[k] = sq_ff
            rows.append(row); targets.append(sq_ff * feedforward[k])
        sq_du = math.sqrt(cfg.r_rate)
        for k in range(n):
            row = np.zeros(n); row[k] = sq_du
            if k:
                row[k - 1] = -sq_du
                targets.append(0.0)
            else:
                targets.append(sq_du * previous_command_rad)
            rows.append(row)
        u, *_ = np.linalg.lstsq(np.vstack(rows), np.asarray(targets), rcond=None)

        first = float(np.clip(u[0], -cfg.max_wheel_angle_rad, cfg.max_wheel_angle_rad))
        terminal = free[-1] + forced[-1] @ u
        return {
            "steer_rad": first,
            "unclipped_steer_rad": float(u[0]),
            "predicted_lateral_error_m": float(terminal[0]),
            "predicted_heading_error_rad": float(terminal[1]),
        }
