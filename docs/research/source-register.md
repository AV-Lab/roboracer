# Research Source Register

Access date for every entry: **2026-09-28**. Local source paths refer to the inspected working trees. Web publication/update dates are distinguished from this access date. Only primary project, event, repository and ROS sources inform the technical conclusions.

## Local authority and evidence

AVLite baseline: `50dcd0043db0cc17efbe82bda81cd0e8875810a0`, clean `dev`, `/home/a2rl/Workspace/avlite`. A2RL reference: `ae5436d80d909bd04808107f0bafe58956da817b` plus existing local changes, `/home/a2rl/avlite/community_plugins/a2rl`. Exact states and commands are preserved in [inventory](evidence/local-inventory.json).

| Source | Research use |
| --- | --- |
| [Plugin development guide](/home/a2rl/Workspace/avlite/docs/plugin-development.md) | Entire guide read; official structure, exports, registration, capabilities and distribution. SHA256 `42caaa115200bc338a61bd86a04d066ec9455abbc62fc0e2bc35743e9d8cab0b`. |
| [Architecture](/home/a2rl/Workspace/avlite/docs/architecture.md), [settings conventions](/home/a2rl/Workspace/avlite/docs/settings-naming.md) | Layer/data flow; source discrepancies; current profile organization. |
| [README](/home/a2rl/Workspace/avlite/README.md:132), [pyproject](/home/a2rl/Workspace/avlite/pyproject.toml) | Installation, Python/dependency constraints, test conventions and version. |
| [Factory](/home/a2rl/Workspace/avlite/avlite/c60_apps/c62_factory.py:76), [loader](/home/a2rl/Workspace/avlite/avlite/c60_apps/c63_plugins.py:196) | Construction signatures, discovery, exceptions, unload behavior. |
| [Settings persistence](/home/a2rl/Workspace/avlite/avlite/c60_apps/c65_setting_utils.py:59), [paths](/home/a2rl/Workspace/avlite/avlite/c60_apps/c68_paths.py:18) | Profile sections, file paths, isolated validation requirements. |
| [Sensor types](/home/a2rl/Workspace/avlite/avlite/c50_common/c52_world_sensor_datatypes.py:67), [state](/home/a2rl/Workspace/avlite/avlite/c10_perception/c11_perception_model.py:149), [control payload](/home/a2rl/Workspace/avlite/avlite/c30_control/c31_control_model.py:11) | Mounts, snapshots, timestamps, footprint origin and command units. |
| [World bridge](/home/a2rl/Workspace/avlite/avlite/c40_execution/c41_world_bridge.py:30), [execution base](/home/a2rl/Workspace/avlite/avlite/c40_execution/c42_execution_strategy.py:129), [Sync](/home/a2rl/Workspace/avlite/avlite/c40_execution/c44_sync_executer.py:74) | Actuation/localization gate, GT selection, step/reset/stop and clock ownership. |
| [Tasks](/home/a2rl/Workspace/avlite/avlite/c40_execution/c47_execution_tasks.py:67), [headless](/home/a2rl/Workspace/avlite/avlite/plugins/p60_headless_mode/p61_headless.py:397) | Mapping truth/snapshot path, launch and exception behavior. |
| [Pure Pursuit/FTG](/home/a2rl/Workspace/avlite/avlite/c30_control/c35_pure_pursuit.py:220), [localization](/home/a2rl/Workspace/avlite/avlite/c10_perception/c16_localization_algs.py:85) | Bounded reuse assessment, source limitations; not executed benchmarks. |
| [A2RL bridge](/home/a2rl/avlite/community_plugins/a2rl/integration/autoverse_bridge.py:1408), [executor](/home/a2rl/avlite/community_plugins/a2rl/execution/executer.py:3659) | Injected transport, coherent inputs, actuation coupling/private scheduling. |
| [A2RL settings](/home/a2rl/avlite/community_plugins/a2rl/core/settings.py:44), [exports](/home/a2rl/avlite/community_plugins/a2rl/_exports.py:5), [manifest](/home/a2rl/avlite/community_plugins/a2rl/analysis/experiment_manifest.py:161) | Legacy configuration, dependency surface and provenance practices. |

## Official RoboRacer material

| Source | Version/context and use |
| --- | --- |
| [RoboRacer](https://roboracer.ai/) | Official entry-point navigation. |
| [Build home](https://f1tenth.readthedocs.io/en/main/), [BOM](https://f1tenth.readthedocs.io/en/main/getting_started/build_car/bom.html), [hardware](https://f1tenth.readthedocs.io/en/main/getting_started/build_car/index.html) | ROS 2 `main` documentation; retrieved footer July 1, 2026; reference build only. |
| [Build FAQ](https://f1tenth.readthedocs.io/en/main/getting_started/faq.html), [system connections](https://f1tenth.readthedocs.io/en/main/getting_started/software_setup/index.html) | Hardware alternatives and physical data/actuation connections. |
| [Driver setup](https://f1tenth.readthedocs.io/en/main/getting_started/firmware/drive_workspace.html), [calibration](https://f1tenth.readthedocs.io/en/main/getting_started/driving/drive_calib_odom.html), [autonomous driving](https://f1tenth.readthedocs.io/en/main/getting_started/driving/drive_autonomous.html) | ROS/driver/calibration workflow; no installation or hardware operation performed. |
| [Driver source README](https://raw.githubusercontent.com/f1tenth/f1tenth_system/humble-devel/README.md) | Retrieved `humble-devel` snapshot; topic/message names and dependencies. Not pinned/installed. |
| [Learn](https://f1tenth-coursekit.readthedocs.io/en/latest/), [labs](https://f1tenth-coursekit.readthedocs.io/en/latest/assignments/labs/index.html), [FTG](https://f1tenth-coursekit.readthedocs.io/en/latest/assignments/labs/lab4.html), [SLAM/Pure Pursuit](https://f1tenth-coursekit.readthedocs.io/en/latest/assignments/labs/lab5.html), [SLAM tutorial](https://f1tenth-coursekit.readthedocs.io/en/latest/lectures/ModuleC/tutorial5.html) | `latest`, footer October 16, 2025; educational baselines. Older `stable` differs. |
| [IROS 2026 event](https://iros2026-race.roboracer.ai/), [resources](https://iros2026-race.roboracer.ai/race_resources.html), [FAQ](https://iros2026-race.roboracer.ai/faq.html) | 31st physical event, September 27–30, 2026; not assumed to be the future target. |
| [General rules](https://iros2026-race.roboracer.ai/rules.html) | Explicit `3.2026-draft`; subject to changes. Immutable rules-repository revision not established. |
| [Competition rules](https://iros2026-race.roboracer.ai/competition_rules.html) | IROS 2026 only, no explicit version string retrieved; overrides general rules. |

## Simulator and middleware sources

The [remote-ref record](evidence/remote-refs.txt) identifies advertised SHAs. Cached branch files below were **not conclusively matched to those SHAs**. Their source behavior is evidence from the retrieved snapshots, not proof of current installed behavior.

| Source | Version/context and use |
| --- | --- |
| [Dedicated multi-car guide](https://iros2026-race.roboracer.ai/multi_car_sim.html) | Current event recommendation and Humble alternative; branch pairing authority. |
| [Event getting started](https://iros2026-race.roboracer.ai/roboracer_resources.html), [Build simulator introduction](https://f1tenth.readthedocs.io/en/main/going_forward/intro.html) | Older instructions; documented inconsistency. |
| [Gym repository](https://github.com/f1tenth/f1tenth_gym), [legacy setup](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/main/setup.py), [bridge repository](https://github.com/f1tenth/f1tenth_gym_ros) | Legacy main branches; package/API/dependency distinction. |
| [Humble pyproject](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-humble/pyproject.toml), [Humble bridge README](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/README.md) | Modern non-JAX route. Gym metadata snapshot reported about four weeks old. |
| [JAX pyproject](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-jax/pyproject.toml), [Jazzy README](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-jazzy/README.md) | Python/ROS/CPU/GPU/tooling requirements; JAX source snapshot reported about one week old. |
| [Humble environment](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-humble/f1tenth_gym/envs/f110_env.py) | Reset/step/render contract; flattened retrieval, about three months old. Exact-current-source qualification required. |
| [JAX environment](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-jax/f1tenth_gym/envs/f110_env.py), [observations](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-jax/f1tenth_gym/envs/observation/__init__.py), [configuration](https://raw.githubusercontent.com/f1tenth/f1tenth_gym/dev-jax/f1tenth_gym/envs/env_config.py) | Action order, reset, observations, metrics, perturbations; retrieved source only. |
| [Humble bridge source](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/f1tenth_gym_ros/gym_bridge.py), [Jazzy bridge source](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-jazzy/f1tenth_gym_ros/gym_bridge.py) | Clock/step/reset/telemetry/frame boundary; snapshots reported about one month and two weeks old respectively. |
| [Humble sim profile](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/config/sim.yaml), [launch](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/launch/gym_bridge_launch.py) | Configured sensor values and temporary map/output concerns. |
| [Humble Dockerfile](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/Dockerfile), [package manifest](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-humble/package.xml), [Jazzy compose](https://raw.githubusercontent.com/f1tenth/f1tenth_gym_ros/dev-jazzy/docker-compose.yml) | Installation/build/ROS/network dependencies; no container built or launched. |
| [LaserScan source](https://raw.githubusercontent.com/ros2/common_interfaces/humble/sensor_msgs/msg/LaserScan.msg), [Ackermann source](https://raw.githubusercontent.com/ros-drivers/ackermann_msgs/ros2/msg/AckermannDrive.msg) | Primary message definitions; units and timestamps. |
| [IROS 2026 virtual event](https://autodrive-ecosystem.github.io/competitions/roboracer-sim-racing-iros-2026/), [2026-iros release](https://github.com/AutoDRIVE-Ecosystem/AutoDRIVE-RoboRacer-Sim-Racing/releases/tag/2026-iros) | Separate acceptance environment; release assets/digests not verified locally. |
| [AutoDRIVE 2026 technical guide](https://autodrive-ecosystem.github.io/competitions/roboracer-sim-racing-guide-2026/), [2026 rules](https://autodrive-ecosystem.github.io/competitions/roboracer-sim-racing-rules-2026/) | API restrictions, commands, headless modes and separate scoring. Technical guide reports September 18, 2026 update. |

## Limitations and reproducibility

- The local inventory contains successful read-only Git commands and failed workspace repository detection. No source Git metadata was changed.
- Remote ref inspection succeeded. Source clone/download attempts were blocked by sandbox networking; no bypass was attempted. The partially created scratch checkout directories under `/tmp/roboracer-simulator-sources` are not usable simulator installations.
- ROS documentation pages returned access-denied/error responses; official raw message definitions were used instead. Gym ReadTheDocs/immutable-source retrieval was unavailable during parts of the investigation. Failed pages are not relied on for technical facts.
- The complete AVLite guide was read, and relevant tests were inspected as source. Test presence, official documentation and successful metadata queries are not passing runtime tests.
- The optional [API probe](validation-request.md) is prepared and remains unexecuted pending authorization. Simulator install, input/output, closed-loop and hardware evidence are all absent.
- The source register supports the findings in the [report](report.md). It does not claim that the future target event has adopted any 2026 rule or that branch snapshots form a validated dependency lock.
