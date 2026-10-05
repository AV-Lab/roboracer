"""AVLite world bridge for the source-built AutoDRIVE F1TENTH player (SIM1-02 build).

S1-01 scope: the bridge registers, constructs without side effects (no sockets, ROS,
threads or processes) and validates every command it is handed. It has no transport yet,
so it reports ``connected = False``, provides no sensors and actuates nothing; S1-02
adds the observation path and the supervisor-owned command path.
"""

from __future__ import annotations

import logging

from avlite.c10_perception.c11_perception_model import EgoState
from avlite.c30_control.c31_control_model import ControlCommandBase
from avlite.c40_execution.c41_world_bridge import WorldBridge
from avlite.c50_common.c51_capabilities import StackCapability

from ..runtime.commands import TargetSpeedSteeringCommand
from ..settings import PluginSettings

log = logging.getLogger(__name__)


class AutoDriveBridge(WorldBridge):
    # Nothing is advertised until the S1-02 observation path delivers it.
    world_capabilities = frozenset()
    stack_capabilities = frozenset()
    stack_requirements = frozenset({StackCapability.CONTROL})

    def __init__(self, ego_state: EgoState | None = None, pm=None):
        self.ego_state = ego_state if ego_state is not None else EgoState()
        self.connected = False
        self.accepted = 0
        self.rejections: dict[str, int] = {}
        self.last_request: TargetSpeedSteeringCommand | None = None

    def _reject(self, reason: str) -> None:
        if reason not in self.rejections:
            log.warning("AutoDriveBridge rejected a command: %s", reason)
        self.rejections[reason] = self.rejections.get(reason, 0) + 1

    def control_ego_state(self, cmd: ControlCommandBase, dt=0.01):
        """Validate a stack request. Only ``TargetSpeedSteeringCommand`` is accepted; stock
        Ackermann commands (including the GUI's manual buttons) carry acceleration and are
        refused, never converted."""
        if not isinstance(cmd, TargetSpeedSteeringCommand):
            self._reject(f"unsupported command type {type(cmd).__name__}")
            return
        problems = cmd.problems(PluginSettings.max_target_speed_mps, PluginSettings.max_steer_rad)
        if problems:
            self._reject("; ".join(problems))
            return
        self.accepted += 1
        self.last_request = cmd

    def reset(self):
        self.last_request = None
