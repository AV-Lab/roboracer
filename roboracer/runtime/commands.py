"""Approved S1 command semantics: target speed and steering angle.

AVLite's stock ``AckermannControlCommand`` carries *acceleration*. The approved design
commands a target speed instead, so this plugin uses its own ``ControlCommandBase``
subclass rather than relabelling acceleration. Conversion to the simulator's normalized
throttle/steering belongs to the backend actuation layer (S1-02 onward).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from avlite.c30_control.c31_control_model import ControlCommandBase


@dataclass
class TargetSpeedSteeringCommand(ControlCommandBase):
    """One controller request.

    - ``target_speed``: requested speed along the vehicle heading [m/s], never negative.
    - ``steer``: front steering angle [rad], positive turns left (AVLite heading convention).
    - ``generated_mono_ns``: generation time on this host's monotonic clock; expiry is
      measured from it and forwarding never refreshes it.
    """

    target_speed: float = 0.0
    steer: float = 0.0
    generated_mono_ns: int = field(default_factory=time.monotonic_ns)

    def problems(self, max_target_speed_mps: float, max_steer_rad: float) -> list[str]:
        """Reasons this request must be rejected under the given limits (empty when valid)."""
        found = []
        for name in ("target_speed", "steer"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                found.append(f"{name} is not a finite number")
        if found:
            return found
        if self.target_speed < 0:
            found.append("target_speed is negative")
        elif self.target_speed > max_target_speed_mps:
            found.append(f"target_speed {self.target_speed} exceeds {max_target_speed_mps} m/s")
        if abs(self.steer) > max_steer_rad:
            found.append(f"steer {self.steer} exceeds ±{max_steer_rad} rad")
        if not isinstance(self.generated_mono_ns, int) or self.generated_mono_ns <= 0:
            found.append("generated_mono_ns is not a positive integer")
        return found
