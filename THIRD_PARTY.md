# Third-party code, patches and licences

This repository contains no third-party source tree. It does contain ports, subclasses and patches of the projects below; their licences apply to those parts.

| Project | Used how | Licence (as found in the pinned source) |
| --- | --- | --- |
| **AVLite** (AV-Lab), 0.6.3, commit `50dcd00` | Dependency. The plugin subclasses its classes (`GreedyLatticePlanner`, `LidarLocalization`, the strategy bases); no AVLite source is copied | MIT, © 2025 AV-Lab |
| **A2RL** (AV-Lab/a2rl `dev` `0b5cfa8`) | **Ported** (each file names its source): `roboracer/control/racing_controller.py`, `roboracer/control/lateral_mpc.py`, `roboracer/planning/race_global_planner.py`, `racing_line.py`, `velocity_profile.py` and `trajectory_tracker.py` | **No licence file in the source export.** Its terms must be confirmed with AV-Lab before this repository is shared outside AV-Lab |
| **AutoDRIVE simulator** (Tinker Twins), source `635dbb6` | `integration/autodrive/sim1/vendor-sim1-01…04.patch`, plus the guard and provenance C# sources added to it | BSD 2-Clause, © 2021 Tinker Twins |
| **AutoDRIVE Devkit** 0.3.0 (Tinker Twins), commit `4abf7cd` | `release/patches/devkit-loopback.patch`, `devkit-tf-lifecycle.patch` | BSD 2-Clause, © 2021 Tinker Twins |
| **attrdict** 2.0.1 | `release/patches/attrdict-python310.patch` (Python 3.10 overlay for the Devkit) | MIT-style, © 2013 Brendan Curran-Johnson |

**Not included or redistributed:**
- the built simulator player, which is provided separately and verified by a sha256 list;
- Unity;
- any wheel or package. The release locks pin them by hash and download them from PyPI.

**This repository's own licence:** none is declared. Choosing one is the owner's decision.
