# 自动驾驶栈概览 — AVLite 运行了什么，roboracer 插件提供了什么

截至 **2026-10-06**（S1-06，M1 进行中）。[英文版](stack-overview.md)。本页描述 M4–M6 运行、D13 计时跑圈和 F1 故障案例所用的栈。内容已对照 AVLite 源码（`avlite/c60_apps/c62_factory.py`、`avlite/c40_execution/c44_sync_executer.py`、`avlite/c40_execution/c42_execution_strategy.py`）和已记录的运行核实。

**简短回答。** AVLite 确实在运行，但作为框架运行：它的插件加载器、`executor_factory`、`SyncExecuter` 的 10 Hz tick 循环，以及它的接口和数据模型。**AVLite 的算法一个都没有运行。** 感知、定位、建图和规划都没有实例化，控制器来自插件。所有驾驶逻辑都是 roboracer 插件代码。监督器是插件代码，运行在独立进程中；守卫位于仿真器内。

## 1. 数据与命令路径

```
AutoDRIVE 仿真器（Unity 播放器，带 roboracer 厂商补丁：来源标记、守卫、D1）
   │  遥测约 5.8 Hz：LiDAR、IMU、编码器、IPS 位姿，以及来源时间戳
   ▼
Devkit 桥接进程（AutoDRIVE 的 Python Devkit，由我们的运行器作为独立子进程运行）
   │  ROS 2 话题；在节奏化回复中把守卫命令带回仿真器
   ▼
AVLite 栈进程
   ├─ AVLite：插件加载器 → executor_factory → SyncExecuter.step()（10 Hz）
   ├─ 插件  ：AutoDriveBridge     （AVLite WorldBridge）     ROS 话题 → 每个 tick 一个传感器快照
   └─ 插件  ：GapFollowController （AVLite ControlStrategy）LiDAR → 目标速度 + 转向
   │  请求 {目标速度, 转向, 计算所依据的观测}（抽象 Unix 套接字）
   ▼
监督器进程（插件代码，roboracer.runtime）：检查 + 速度环 → 归一化油门/转向
   ▼
守卫（仿真器内的 C#，roboracer 补丁）：武装 epoch、租约 ≤ 1 s、限制 → 车轮
```

## 2. 来自 AVLite 的部分（`/home/a2rl/avlite`）

| 组件 | 在我们的运行中的作用 |
| --- | --- |
| 插件系统 | 将 `roboracer` 作为社区插件加载（`AppSettings.c62_community_plugins`，`executor_factory(load_plugins=True)`），与 AVLite 应用使用的路径相同。 |
| `executor_factory` | 按注册名称构建栈。我们传入 `executer_type="SyncExecuter"`、`bridge="AutoDriveBridge"` 和 `controller_strategy_name="GapFollowController"`，早期阶段还用过 `HoldController` / `SpeedStepController`。感知、定位、建图、全局规划器和局部规划器的名称都为空，因此工厂不会创建其中任何一个。 |
| `SyncExecuter.step()` | AVLite 的 tick。每个 tick 它：(1) 从桥接取一个传感器帧（`get_sensor_frame()`）；(2) 因为桥接声明了 `StackCapability.LOCALIZATION`，把真值位姿复制到自车状态；(3) 调用 `controller.control(ego, plan, sensors=...)`（`_control_step`）；(4) 通过 `world.control_ego_state()` 施加保持的命令（`_simulate_step`，每个 tick 零阶保持）。 |
| 接口与数据模型 | `WorldBridge`、`ControlStrategy`、`ControlCommand`、`EgoState`、`PerceptionModel`，以及能力标志（`WorldCapability.LIDAR_2D`、`StackCapability.LOCALIZATION`）。插件实现这些接口。 |

## 3. 来自 roboracer 插件的部分（`roboracer/`）

| 组件 | 源码 | 作用 |
| --- | --- | --- |
| `AutoDriveBridge` | `roboracer/integration/autodrive_bridge.py` | AVLite 面向 AutoDRIVE 的世界桥接。它订阅 Devkit 的 ROS 2 话题并计算编码器速度。它把每个请求连同所用的观测发送给监督器，并拒绝 `TargetSpeedSteeringCommand` 以外的任何命令类型。 |
| `SnapshotAssembler` | `roboracer/integration/autodrive_observation.py` | 每个遥测帧组装一个一致的快照：扫描、IMU、编码器和位姿具有匹配的采集来源。它拒绝过期、格式错误或不一致的帧（会话、序号、扫描布局、非有限读数、扫描/位姿偏差）。 |
| `GapFollowController`（A；A-lap 使用 `LAP_PARAMS`） | `roboracer/control/gap_follow.py` | **唯一的驾驶算法。** 带视差扩展的跟随间隙算法，只用 LiDAR，从不读取位姿或地图。A-lap（M6、M1）增加了居中和侧向余量限速。 |
| `SpeedStepController`、`HoldController` | `roboracer/control/` | M4（脚本化速度阶跃）和零命令阶段使用的测试控制器。 |
| `TargetSpeedSteeringCommand` | `roboracer/runtime/commands.py` | 已批准的命令类型，带自身的校验（有限值、限制、生成时间戳）。 |
| 监督器 | `roboracer/runtime/supervisor_core.py`、`supervisor_process.py` | 独立进程。它检查来源、序号、请求寿命（500 ms）、观测年龄（500 ms）和运行器租约（500 ms）。它运行 D5 速度环（目标速度 → 油门，自有的编码器反馈订阅，反馈过期/丢失截断），并精确换算转向。 |

## 4. 不属于插件的部分

| 组件 | 源码 | 作用 |
| --- | --- | --- |
| 守卫 | `integration/autodrive/sim1/RoboRacer/GuardCore.cs`（在播放器中） | 施加执行前的最后一道关卡：武装 epoch、来源、序号、租约、时钟界和限制。租约到期或解除武装时以零油门制动。 |
| 运行器与阶段脚本 | `scripts/autodrive_neutral.py` | 测试框架。它管理进程、Connect 前检查和阶段安排。其中止监视器是唯一使用真值位姿的部分。 |
| 评分器与测量工具 | `scripts/roboracer_scoring.py`、`roboracer_episode.py`、`roboracer_timing.py`、`roboracer_f1.py` | 独立评估：依据仿真器真值判定圈数、接触和出界；时序与资源；F1 故障检查。 |

## 5. AVLite 确实在执行（而不只是被导入）的证据

- **从 AVLite 环境加载。** 栈状态记录了从 AVLite 环境加载的 `avlite/__init__.py`，以及从 `roboracer/` 加载的插件。
- **每个请求都在它的 tick 中生成。** 所有监督器请求（一圈 M6 中 1,446 个）都在 `SyncExecuter.step()` 内生成。tick 周期为 100.0 ms（p95 100.4 ms），tick → 请求约 1 ms（[S1-06 测量](../stages/S1-06-measurements.zh-CN.md)）。
- **它的保持行为可见。** AVLite 每个 tick 重新施加保持的命令。桥接把这些重复计为 `held_resend`，不重复发送，与 `_simulate_step` 一致。
- **自车状态标注为真值**，通过 `LOCALIZATION` 能力。A-lap 从不读取它。

## 6. 已验证范围的局限

- **AVLite 算法：** 它的感知、定位、建图、规划和控制都尚未使用。
- **AVLite 应用与 GUI：** 没有运行。栈进程（`scripts/autodrive_neutral.py` 中的 `plugin_observe`）通过 AVLite 自己的工厂构建执行器，然后自己每 100 ms 调用一次 `executer.step()`。这是 AVLite 的无界面执行路径，而不是 AVLite 应用。
- **速度设置：** 0.3 m/s 的目标速度上限只在已批准阶段期间、在栈进程内设置；发布的插件默认值为 0。
- **后续工作：** 在 AVLite 应用下运行，以及用 AVLite 或其他模块替换真值定位或跟随间隙算法。这属于后续阶段的工作（A/B 栈阶段，即计划中的 M3）。
