"""Global planner for B (S3, D30/D31: ported from A2RL).

Port of ``RaceGlobalPlanner`` in ``planning/strategies.py`` of the A2RL plugin (AV-Lab/a2rl ``dev``
0b5cfa8): the configured race trajectory (AVLite's default global trajectory file; for stage s3b the
committed C0 plan) is the global plan. Renamed so it cannot collide with the A2RL plugin's registry
entry if both plugins are loaded in one AVLite.
"""

from __future__ import annotations

from avlite.c20_planning.c21_planning_model import GlobalPlan
from avlite.c20_planning.c22_global_planning_strategy import GlobalPlannerStrategy


class RaceLineGlobalPlanner(GlobalPlannerStrategy):
    """Use the configured race trajectory as the global plan."""

    def plan(self, perception_model=None, sensors=None) -> GlobalPlan:
        del perception_model, sensors
        return self.global_plan
