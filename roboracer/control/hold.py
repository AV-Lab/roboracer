"""A controller that always requests a standstill: zero target speed, straight wheels."""

from __future__ import annotations

from avlite.c30_control.c31_control_model import ControlCommand
from avlite.c30_control.c32_control_strategy import ControlStrategy

from ..runtime.commands import TargetSpeedSteeringCommand


class HoldController(ControlStrategy):
    """Safe default and command-path probe; needs no plan or localization."""

    stack_requirements = frozenset()

    def control(self, ego, plan=None, control_dt=None, perception_model=None, sensors=None):
        if plan is not None:
            self.set_plan(plan)
        cmd = TargetSpeedSteeringCommand(target_speed=0.0, steer=0.0)
        # The stock GUI gauges read ``controller.cmd.acceleration``/``.steer``; mirror the
        # steering and show no acceleration (none is commanded). The returned command is
        # the actual request.
        self.cmd = ControlCommand(steer=cmd.steer, acceleration=0.0)
        return cmd

    def reset(self):
        self.cmd = ControlCommand()
