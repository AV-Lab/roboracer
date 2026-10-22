"""Fresh-process S1-01 probe: ``python s1_01_probe.py <case> <plugin_dir>`` prints one JSON result.

Run by test_s1_01_plugin.py under the AVLite interpreter with isolated AVLite/XDG
directories in the environment. Each case uses a new process because AVLite registries
are process-global and their cleanup is incomplete.
"""

import json
import math
import os
import sys
import threading
from pathlib import Path

CASE, PLUGIN = sys.argv[1], str(Path(sys.argv[2]).resolve())
WATCHED = ("rclpy", "socketio", "engineio", "gevent", "zmq", "autodrive_f1tenth")


def host_snapshot():
    fds = Path("/proc/self/fd")
    sockets = 0
    for fd in fds.iterdir():
        try:
            sockets += os.readlink(fd).startswith("socket:")
        except OSError:
            pass
    children = []
    for task in Path("/proc/self/task").iterdir():
        try:
            children += (task / "children").read_text().split()
        except OSError:
            pass
    return {"threads": threading.active_count(), "sockets": sockets, "children": sorted(children),
            "watched_modules": sorted(m for m in sys.modules if m.split(".")[0] in WATCHED)}


def load_plugin():
    from avlite.c60_apps.c63_plugins import import_plugin_modules
    import_plugin_modules(PLUGIN, pkg_name="roboracer")
    return sys.modules["avlite.plugins.roboracer"]


def case_import():
    import avlite.c60_apps.c63_plugins  # noqa: F401  (baseline: AVLite itself)
    from avlite.c30_control.c32_control_strategy import ControlStrategy
    from avlite.c40_execution.c41_world_bridge import WorldBridge
    before = host_snapshot()
    plugin = load_plugin()
    after = host_snapshot()
    settings = plugin.PluginSettings
    return {"before": before, "after": after, "exports": sorted(plugin.__all__),
            "loaded_modules": sorted(m for m in sys.modules if m.startswith("avlite.plugins.roboracer")),
            "registered_bridge": "AutoDriveBridge" in WorldBridge.registry,
            "registered_controller": "HoldController" in ControlStrategy.registry,
            "settings_filepath": getattr(type(settings), "filepath", None) or getattr(settings, "filepath", None)}


def run_ticks(executer, ticks=3):
    for _ in range(ticks):
        executer.step(sim_dt=0.01)


def factory_run(gt_filter=None):
    """The real registration path: AVLite's factory loads the community plugin itself.
    ``gt_filter`` is AVLite's Bridge Setting filter (``c41_world_stack_capabilities``)."""
    from avlite.c40_execution.c49_settings import ExecutionSettings
    from avlite.c60_apps.c62_factory import executor_factory
    from avlite.c60_apps.c69_settings import AppSettings
    AppSettings.c62_default_plugins = []
    AppSettings.c62_community_plugins = {"roboracer": PLUGIN}
    ExecutionSettings.c41_world_stack_capabilities = gt_filter
    executer = executor_factory(
        executer_type="SyncExecuter", bridge="AutoDriveBridge", perception_strategy_name="",
        localization_strategy_name="", mapping_strategy_name="", global_planner_strategy_name="",
        local_planner_strategy_name="", controller_strategy_name="HoldController", execution_task_names=[],
        default_global_trajectory_file="", map_file="", load_plugins=True)
    run_ticks(executer)
    world, last = executer.world, executer.world.last_request
    gauge = executer.controller.cmd
    return {"bridge": type(world).__name__, "controller": type(executer.controller).__name__,
            "stack_capabilities": sorted(c.name for c in world.stack_capabilities),
            "can_actuate": executer._can_actuate(), "accepted": world.accepted, "rejections": world.rejections,
            "last_request": None if last is None else
                {"type": type(last).__name__, "target_speed": last.target_speed, "steer": last.steer},
            "gauge": {"acceleration": gauge.acceleration, "steer": gauge.steer}}


def case_factory():
    """Default filter: the bridge's ground-truth LOCALIZATION enables control; commands reach
    the bridge through the real execution path (validated and recorded only)."""
    return factory_run(None)


def case_factory_gt_filtered():
    """AVLite's GT filter with LOCALIZATION removed: the executer must never actuate."""
    return factory_run([])


def case_settings():
    import yaml
    from avlite.c60_apps.c64_settings_schema import SettingsValidationError
    from avlite.c60_apps.c65_setting_utils import load_setting, profile_file_path, save_setting
    plugin = load_plugin()
    s = plugin.PluginSettings
    defaults = s.model_dump()
    changed = {"autodrive_port": 4570, "request_life_ms": 250.0, "max_steer_rad": 0.3}
    for k, v in changed.items():
        setattr(s, k, v)
    save_setting(s, profile="s1test")
    path = profile_file_path("s1test")
    for k, v in defaults.items():
        setattr(s, k, v)
    loaded = load_setting(s, profile="s1test")
    round_trip = {k: getattr(s, k) for k in changed}

    with open(path) as stream:
        profile = yaml.safe_load(stream)
    # Locate this plugin's section without assuming the profile layout.
    def find(node, trail=()):
        if isinstance(node, dict):
            if "autodrive_port" in node:
                return trail
            for key, value in node.items():
                hit = find(value, trail + (key,))
                if hit is not None:
                    return hit
        return None
    trail = find(profile)
    invalid_cases = {"port 80": {"autodrive_port": 80}, "non-loopback host": {"autodrive_host": "0.0.0.0"},
                     "life 2000 ms": {"request_life_ms": 2000}, "nan life": {"request_life_ms": float("nan")},
                     "negative speed limit": {"max_target_speed_mps": -1}, "steer above 30 deg": {"max_steer_rad": 0.6},
                     "inf speed limit": {"max_target_speed_mps": float("inf")}}
    results = {}
    for name, bad in invalid_cases.items():
        data = yaml.safe_load(yaml.safe_dump(profile))
        section = data
        for key in trail:
            section = section[key]
        section.update(bad)
        with open(path, "w") as stream:
            yaml.safe_dump(data, stream)
        snapshot = s.model_dump()
        ok = load_setting(s, profile="s1test")
        try:
            load_setting(s, profile="s1test", strict=True)
            strict = "accepted"
        except SettingsValidationError:
            strict = "SettingsValidationError"
        results[name] = {"load_returned": ok, "unchanged": s.model_dump() == snapshot, "strict": strict}
    return {"section_path": list(trail), "round_trip_loaded": loaded, "round_trip": round_trip,
            "expected": changed, "invalid": results,
            "config_dir": os.environ.get("AVLITE_CONFIG_DIR"), "profile_path": path}


def case_consumers():
    plugin = load_plugin()
    from avlite.c10_perception.c11_perception_model import EgoState
    from avlite.c30_control.c31_control_model import ControlCommand
    from avlite.c40_execution.c46_basic_sim import BasicSim
    Cmd = plugin.TargetSpeedSteeringCommand
    limit = plugin.PluginSettings.max_steer_rad
    bridge = plugin.AutoDriveBridge()
    cases = {
        "gui manual accel (Ackermann)": ControlCommand(acceleration=3),
        "gui manual steer (Ackermann)": ControlCommand(steer=-0.7),
        "nan speed": Cmd(target_speed=float("nan")),
        "inf steer": Cmd(steer=float("inf")),
        "negative speed": Cmd(target_speed=-0.1),
        "speed above limit (0 until protocol)": Cmd(target_speed=0.1),
        "steer above limit": Cmd(steer=limit + 1e-6),
        "bool speed": Cmd(target_speed=True),
        "bad generation stamp": Cmd(generated_mono_ns=0),
    }
    outcome = {}
    for name, cmd in cases.items():
        before = (bridge.accepted, sum(bridge.rejections.values()))
        bridge.control_ego_state(cmd)
        outcome[name] = "accepted" if bridge.accepted > before[0] else "rejected"
    bridge.control_ego_state(Cmd(target_speed=0.0, steer=limit))
    outcome["zero speed at steering limit"] = "accepted" if bridge.last_request is not None else "rejected"
    try:
        BasicSim(ego_state=EgoState()).control_ego_state(Cmd())
        basic_sim = "accepted silently"
    except AttributeError as exc:
        basic_sim = "AttributeError: " + str(exc)
    controller = plugin.HoldController()
    returned = controller.control(EgoState())
    return {"bridge": outcome, "rejection_reasons": bridge.rejections,
            "basic_sim_with_plugin_command": basic_sim,
            "hold_returns": type(returned).__name__,
            "hold_values": [returned.target_speed, returned.steer],
            "gauge_numeric": all(isinstance(getattr(controller.cmd, a), (int, float)) and
                                 math.isfinite(getattr(controller.cmd, a)) for a in ("acceleration", "steer")),
            "headless_acceleration_display": getattr(returned, "acceleration", 0.0)}


def case_s1_02_bridge():
    """S1-02 observation surface without ROS: messages are fed to the bridge's offer hook."""
    plugin = load_plugin()
    sys.path.insert(0, str(Path(PLUGIN).parent))
    from roboracer.tests import s1_02_fixtures as fx
    bridge = plugin.AutoDriveBridge()

    def view():
        frame = bridge.get_sensor_frame()
        lidar = frame.lidar
        return {"lidar_points": None if lidar.points is None else len(lidar.points),
                "imu": None if frame.imu is None else list(frame.imu.linear_accel)}

    result = {"world_capabilities": sorted(c.name for c in bridge.world_capabilities),
              "stack_capabilities": sorted(c.name for c in bridge.stack_capabilities),
              "class_attributes": all(isinstance(type(bridge).__dict__.get(name), frozenset) for name in (
                  "world_capabilities", "stack_capabilities", "stack_requirements")),
              "before": view(), "ego_before": [bridge.get_ego_state().x, bridge.get_ego_state().y],
              "lidar_data_before": bridge.get_lidar_data()}
    messages, provenance = fx.frame(2)
    for name, message in messages.items():
        bridge._offer(name, message)
    bridge._offer("provenance", fx.NS(data=provenance))
    after = view()
    first, second = bridge.get_sensor_frame(), bridge.get_sensor_frame()
    after.update(lidar_mount=first.lidar.base_to_sensor[:3, 3].tolist(),
                 fresh_objects=first.lidar is not second.lidar and first.imu is not second.imu,
                 committed=bridge.statistics()["committed"],
                 lidar_data_is_snapshot=bridge.get_lidar_data() is first.lidar.points)
    ego = bridge.get_ego_state()
    after.update(ego_xy=[ego.x, ego.y], gt_theta=ego.theta)
    result.update(after=after, watched_modules=host_snapshot()["watched_modules"])
    return result


def case_s1_supervisor_client():
    """The bridge's request path, received on a plain test socket (no ROS, no supervisor)."""
    import socket as socket_module
    plugin = load_plugin()
    sys.path.insert(0, str(Path(PLUGIN).parent))
    from roboracer.tests import s1_02_fixtures as fx
    Command = plugin.TargetSpeedSteeringCommand
    name = f"rr-probe-{os.getpid()}"
    receiver = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_DGRAM)
    receiver.bind("\0" + name)
    receiver.settimeout(2.0)
    bridge = plugin.AutoDriveBridge()
    bridge.connect_supervisor(name)

    def offer(frame):
        messages, provenance = frame
        for topic, message in messages.items():
            bridge._offer(topic, message)
        bridge._offer("provenance", fx.NS(data=provenance))

    bridge.control_ego_state(Command())  # before any snapshot
    before = "no_observation" if bridge.request_io["no_observation"] == 1 else "sent"
    offer(fx.frame(2))
    bridge.get_sensor_frame()  # tick uses frame 2
    first = Command()
    bridge.control_ego_state(first)
    bridge.control_ego_state(first)  # AVLite's held re-send
    offer(fx.frame(3, position=(0.8, 3.0, 0.059)))  # committed mid-tick
    ego = bridge.get_ego_state()
    bridge.control_ego_state(Command())
    bridge.get_sensor_frame()  # next tick uses frame 3
    bridge.control_ego_state(Command())
    requests = [json.loads(receiver.recv(4096)) for _ in range(3)]
    receiver.close()
    return {"before_snapshot": before, "requests": requests, "generated": [first.generated_mono_ns],
            "ego_mid_tick": [ego.x, ego.y], "io": bridge.request_io}


def case_factory_s3b():
    """S3 stage s3b assembly as the runner does it: AVLite's factory loads RacingLineController from the
    plugin, then the committed hash-checked C0 plan and the M6-envelope config are installed."""
    import importlib
    from avlite.c40_execution.c49_settings import ExecutionSettings
    from avlite.c60_apps.c62_factory import executor_factory
    from avlite.c60_apps.c69_settings import AppSettings
    AppSettings.c62_default_plugins = []
    AppSettings.c62_community_plugins = {"roboracer": PLUGIN}
    ExecutionSettings.c41_world_stack_capabilities = None
    executer = executor_factory(
        executer_type="SyncExecuter", bridge="AutoDriveBridge", perception_strategy_name="",
        localization_strategy_name="", mapping_strategy_name="", global_planner_strategy_name="RaceLineGlobalPlanner",
        local_planner_strategy_name="", controller_strategy_name="RacingLineController", execution_task_names=[],
        default_global_trajectory_file=str(Path(PLUGIN) / "data/c0-s3b-plan.json"), map_file="", load_plugins=True)
    s3b = importlib.import_module("avlite.plugins.roboracer.planning.s3b")
    tracker, info = s3b.load_plan()
    same_plan = [tuple(p) for p in executer.global_planner.global_plan.path] == [tuple(p) for p in tracker.path]
    ctl = executer.controller
    ctl.config, ctl.tj = s3b.controller_config(), tracker
    ctl.reset()
    ctl.enabled = False
    run_ticks(executer)
    disabled = dict(ctl.last)
    ctl.enabled = True
    run_ticks(executer)  # no telemetry: ego at the origin, far off the line
    last = executer.world.last_request
    return {"controller": type(ctl).__name__, "global_planner": type(executer.global_planner).__name__,
            "same_plan": same_plan, "plan": {k: info[k] for k in ("points", "lap_m", "max_speed_mps")},
            "config": {"speed_cap_mps": ctl.config.speed_cap_mps, "max_wheel_angle_rad": ctl.config.max_wheel_angle_rad,
                       "mpc_lateral_mode": ctl.config.mpc_lateral_mode},
            "disabled": disabled, "enabled_last": {k: ctl.last.get(k) for k in ("safe_stop", "target_speed")},
            "accepted": executer.world.accepted, "rejections": executer.world.rejections,
            "last_request": None if last is None else {"target_speed": last.target_speed, "steer": last.steer}}

if __name__ == "__main__":
    print(json.dumps(globals()["case_" + CASE.replace("-", "_")]()))
