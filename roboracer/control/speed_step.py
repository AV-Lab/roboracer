"""Test controller for S1-03 stage M4: steering 0, target speed set from outside (the runner's
schedule). Speed control itself lives in the supervisor (D5); this only emits requests."""

from __future__ import annotations

from avlite.c30_control.c31_control_model import ControlCommand
from avlite.c30_control.c32_control_strategy import ControlStrategy

from ..runtime.commands import TargetSpeedSteeringCommand


class SpeedStepController(ControlStrategy):
    """Emits ``TargetSpeedSteeringCommand(target_speed, 0)``; ``target_speed`` is assigned by the
    test runner. Defaults to a standstill request."""

    stack_requirements = frozenset()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_speed = 0.0

    def control(self, ego, plan=None, control_dt=None, perception_model=None, sensors=None):
        if plan is not None:
            self.set_plan(plan)
        cmd = TargetSpeedSteeringCommand(target_speed=float(self.target_speed), steer=0.0)
        self.cmd = ControlCommand(steer=0.0, acceleration=0.0)  # gauge mirror; no acceleration is commanded
        return cmd

    def reset(self):
        self.target_speed = 0.0
        self.cmd = ControlCommand()
