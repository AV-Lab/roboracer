"""AVLite world bridge for the source-built AutoDRIVE F1TENTH player (SIM1-02 build).

Construction has no side effects (no sockets, ROS, threads or processes). ``connect()``
creates a private rclpy context, subscribes to the provenance-enabled Devkit topics and spins
them on one daemon thread; ``close()`` tears that down. Observations are committed as whole
snapshots by ``SnapshotAssembler`` and swapped in atomically, so a sensor frame and the GT pose
always come from the same telemetry frame.

Commands are validated and recorded only. The supervisor-owned command path is separate
(S1 supervisor skeleton); nothing here can move the vehicle.
"""

from __future__ import annotations

from dataclasses import replace
import logging
import threading
import time

from avlite.c10_perception.c11_perception_model import EgoState
from avlite.c30_control.c31_control_model import ControlCommandBase
from avlite.c40_execution.c41_world_bridge import WorldBridge
from avlite.c50_common.c51_capabilities import StackCapability, WorldCapability
from avlite.c50_common.c52_world_sensor_datatypes import Imu, Lidar, SensorFrame

from ..runtime.commands import TargetSpeedSteeringCommand
from ..settings import PluginSettings
from .autodrive_observation import (IMU_MOUNT_M, LIDAR_MOUNT_M, HEADER_SOURCES, Snapshot, SnapshotAssembler,
                                    translation)

log = logging.getLogger(__name__)

NAMESPACE = "/autodrive/f1tenth_1/"


class AutoDriveBridge(WorldBridge):
    world_capabilities = frozenset({WorldCapability.LIDAR_2D, WorldCapability.IMU})
    stack_requirements = frozenset({StackCapability.CONTROL})

    def __init__(self, ego_state: EgoState | None = None, pm=None):
        self.ego_state = ego_state if ego_state is not None else EgoState()
        self.connected = False
        self.accepted = 0
        self.rejections: dict[str, int] = {}
        self.last_request: TargetSpeedSteeringCommand | None = None
        self.assembler = SnapshotAssembler()
        self._lock = threading.Lock()
        self._snapshot: Snapshot | None = None
        self._transport = None

    @property
    def stack_capabilities(self) -> frozenset:
        """GT localization only when explicitly enabled; it is simulator truth, never an estimate."""
        return frozenset({StackCapability.LOCALIZATION}) if PluginSettings.gt_localization else frozenset()

    # -- observation path --------------------------------------------------------------------
    def connect(self, timeout_s: float = 0.0) -> bool:
        """Start the ROS subscriptions. With ``timeout_s`` > 0, wait for the first snapshot."""
        if self._transport is None:
            self._transport = _RosTransport(self)
        if timeout_s > 0:
            deadline = time.monotonic() + timeout_s
            while self.latest() is None and time.monotonic() < deadline:
                time.sleep(0.01)
        return self.latest() is not None

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        self.connected = False

    def _offer(self, topic: str, message) -> None:
        now = time.monotonic_ns()
        with self._lock:
            if topic == "provenance":
                snapshots = self.assembler.offer_provenance(message.data, now)
            else:
                snapshots = self.assembler.offer(topic, message, now)
            if snapshots:
                self._snapshot = snapshots[-1]
                self.connected = True

    def latest(self) -> Snapshot | None:
        with self._lock:
            return self._snapshot

    def observation_age_s(self, now_s: float | None = None) -> float | None:
        """Age of the newest committed pose acquisition on CLOCK_MONOTONIC; None before the first."""
        snapshot = self.latest()
        if snapshot is None:
            return None
        return (time.monotonic() if now_s is None else now_s) - snapshot.pose.stamp

    def statistics(self) -> dict:
        with self._lock:
            a = self.assembler
            return {"committed": a.committed, "rejections": dict(a.rejections), "dropped": a.dropped,
                    "last_rejection": a.last_rejection, "pending": len(a.pending)}

    def get_sensor_frame(self, agent_id: int = 0) -> SensorFrame:
        """One atomic snapshot: fresh sensor objects every call, shared read-only buffers."""
        if agent_id != 0:
            raise NotImplementedError(f"{type(self).__name__} does not support sensors for agent {agent_id}")
        snapshot = self.latest()
        if snapshot is None:
            lidar = Lidar(sensor_name="lidar", base_to_sensor=translation(LIDAR_MOUNT_M))
            frame = SensorFrame(lidars={"lidar": lidar}, primary_lidar_name="lidar", stamp=time.monotonic(),
                                frame_id="base_link")
        else:
            frame = SensorFrame(lidars={"lidar": replace(snapshot.lidar)}, primary_lidar_name="lidar",
                                imu=replace(snapshot.imu), stamp=time.monotonic(), frame_id="base_link")
        return self._apply_world_capability_filter(frame)

    def get_lidar_sensor(self, agent_id: int = 0) -> Lidar:
        return Lidar(sensor_name="lidar", base_to_sensor=translation(LIDAR_MOUNT_M))

    def get_imu(self, agent_id: int = 0) -> Imu | None:
        snapshot = self.latest()
        return replace(snapshot.imu) if snapshot is not None else None

    def get_ego_state(self) -> EgoState:
        """With GT localization enabled, pose comes from the latest snapshot. Velocity is not
        observed by this bridge and is left unchanged."""
        snapshot = self.latest()
        if PluginSettings.gt_localization and snapshot is not None:
            self.ego_state.x, self.ego_state.y, self.ego_state.z = snapshot.pose.x, snapshot.pose.y, snapshot.pose.z
            self.ego_state.theta = snapshot.pose.yaw
        return self.ego_state

    # -- command validation (no actuation) ---------------------------------------------------
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


class _RosTransport:
    """Private rclpy context, one node, one executor thread. Imported only on connect()."""

    def __init__(self, bridge: AutoDriveBridge):
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
        from geometry_msgs.msg import Point
        from sensor_msgs.msg import Imu as ImuMsg, JointState, LaserScan
        from std_msgs.msg import String

        self.context = rclpy.Context()
        rclpy.init(context=self.context)
        self.node = rclpy.create_node("roboracer_autodrive_bridge", context=self.context)
        qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=10)
        kinds = {"lidar": LaserScan, "imu": ImuMsg, "left_encoder": JointState, "right_encoder": JointState,
                 "ips": Point, "provenance": String}
        assert set(kinds) == set(HEADER_SOURCES) | {"ips", "provenance"}
        self.subscriptions = [
            self.node.create_subscription(kind, NAMESPACE + topic,
                                          lambda message, topic=topic: bridge._offer(topic, message), qos)
            for topic, kind in kinds.items()]
        self.executor = SingleThreadedExecutor(context=self.context)
        self.executor.add_node(self.node)
        self.thread = threading.Thread(target=self._spin, name="roboracer-autodrive-bridge", daemon=True)
        self.thread.start()

    def _spin(self):
        from rclpy.executors import ExternalShutdownException
        try:
            while self.context.ok():
                self.executor.spin_once(timeout_sec=0.1)
        except ExternalShutdownException:
            pass

    def close(self):
        self.context.try_shutdown()
        self.thread.join(timeout=2.0)
        self.executor.shutdown()
        self.node.destroy_node()
