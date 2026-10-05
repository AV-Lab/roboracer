"""AVLite world bridge for the source-built AutoDRIVE F1TENTH player (SIM1-02 build).

Construction has no side effects (no sockets, ROS, threads or processes). ``connect()``
creates a private rclpy context, subscribes to the provenance-enabled Devkit topics and spins
them on one daemon thread; ``close()`` tears that down. Observations are committed as whole
snapshots by ``SnapshotAssembler`` and swapped in atomically, so a sensor frame and the GT pose
always come from the same telemetry frame.

Contracts follow the AVLite plugin guide: public ``frozenset`` class attributes. Like the
built-in ``BasicSim``, the bridge advertises ground-truth ``LOCALIZATION``; switch it off with
AVLite's own Bridge Setting filter (``c40_execution.c41_world_stack_capabilities``).

Commands are validated here and, when ``connect(supervisor=...)`` named a supervisor, sent to
that separate process (``runtime/supervisor_process.py``), which owns the only path to the
simulator. Each distinct command is sent once, tagged with the identity of the snapshot the
tick used; AVLite's held re-sends of the same command are not re-sent.
"""

from __future__ import annotations

from dataclasses import replace
import json
import logging
import socket
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
    # Simulator truth (IPS + IMU orientation), labelled as such on every snapshot.
    stack_capabilities = frozenset({StackCapability.LOCALIZATION})
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
        self._tick_snapshot: Snapshot | None = None  # the snapshot this tick's sensor frame used
        self._supervisor = None  # (socket, abstract name) once connect(supervisor=...) is called
        self._request_seq = 0
        self._last_sent_gen: int | None = None
        self.request_io = {"sent": 0, "refused": 0, "dropped": 0, "held_resend": 0, "no_observation": 0}
        # Optional callable(snapshot), invoked on the transport thread under the bridge lock for
        # every committed snapshot. It must be quick and must not call back into the bridge.
        self.snapshot_listener = None

    # -- observation path --------------------------------------------------------------------
    def connect(self, timeout_s: float = 0.0, supervisor: str | None = None) -> bool:
        """Start the ROS subscriptions and, optionally, the request path to the supervisor's
        abstract socket ``supervisor``. With ``timeout_s`` > 0, wait for the first snapshot."""
        if supervisor is not None:
            self.connect_supervisor(supervisor)
        if self._transport is None:
            self._transport = _RosTransport(self)
        if timeout_s > 0:
            deadline = time.monotonic() + timeout_s
            while self.latest() is None and time.monotonic() < deadline:
                time.sleep(0.01)
        return self.latest() is not None

    def connect_supervisor(self, name: str) -> None:
        """Open the non-blocking request path to the supervisor's abstract socket ``name``."""
        if self._supervisor is None:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            sock.setblocking(False)  # never block the executor on the supervisor
            self._supervisor = (sock, name)

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()
            self._transport = None
        if self._supervisor is not None:
            self._supervisor[0].close()
            self._supervisor = None
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
                if self.snapshot_listener is not None:
                    for snapshot in snapshots:
                        self.snapshot_listener(snapshot)

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
                    "last_rejection": a.last_rejection, "pending": len(a.pending),
                    "requests": dict(self.request_io), "command_rejections": dict(self.rejections)}

    def get_sensor_frame(self, agent_id: int = 0) -> SensorFrame:
        """One atomic snapshot: fresh sensor objects every call, shared read-only buffers."""
        if agent_id != 0:
            raise NotImplementedError(f"{type(self).__name__} does not support sensors for agent {agent_id}")
        snapshot = self._tick_snapshot = self.latest()
        if snapshot is None:
            lidar = Lidar(sensor_name="lidar", base_to_sensor=translation(LIDAR_MOUNT_M))
            frame = SensorFrame(lidars={"lidar": lidar}, primary_lidar_name="lidar", stamp=time.monotonic(),
                                frame_id="base_link")
        else:
            frame = SensorFrame(lidars={"lidar": replace(snapshot.lidar)}, primary_lidar_name="lidar",
                                imu=replace(snapshot.imu), stamp=time.monotonic(), frame_id="base_link")
        return self._apply_world_capability_filter(frame)

    def get_lidar_data(self, agent_id: int = 0):
        """Points of the latest snapshot in the LiDAR frame, (N, 4) float32, read-only."""
        snapshot = self.latest()
        return snapshot.lidar.points if snapshot is not None else None

    def get_lidar_sensor(self, agent_id: int = 0) -> Lidar:
        return Lidar(sensor_name="lidar", base_to_sensor=translation(LIDAR_MOUNT_M))

    def get_imu(self, agent_id: int = 0) -> Imu | None:
        snapshot = self.latest()
        return replace(snapshot.imu) if snapshot is not None else None

    def get_ego_state(self) -> EgoState:
        """Ground-truth pose (unchanged before the first snapshot). Within a tick it comes from
        the snapshot ``get_sensor_frame()`` used, so pose and sensors never mix frames. Velocity
        is not observed by this bridge and is left unchanged."""
        snapshot = self._tick_snapshot or self.latest()
        if snapshot is not None:
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
        if cmd.generated_mono_ns == self._last_sent_gen:
            self.request_io["held_resend"] += 1  # AVLite re-applies its held command every tick
            return
        self._last_sent_gen = cmd.generated_mono_ns
        if self._supervisor is not None:
            self._send(cmd)

    def _send(self, cmd: TargetSpeedSteeringCommand) -> None:
        snapshot = self._tick_snapshot or self.latest()
        if snapshot is None:
            self.request_io["no_observation"] += 1
            return
        self._request_seq += 1
        message = {"kind": "request", "origin": "avlite", "seq": self._request_seq,
                   "gen_ns": cmd.generated_mono_ns, "target_speed": cmd.target_speed, "steer": cmd.steer,
                   "observation": {"telemetry_seq": snapshot.telemetry_seq, "session": snapshot.session,
                                   "episode": snapshot.episode, "stamp_ns": int(round(snapshot.pose.stamp * 1e9)),
                                   "lidar_stamp_ns": int(round(snapshot.lidar.stamp * 1e9))}}
        sock, name = self._supervisor
        try:
            sock.sendto(json.dumps(message).encode(), "\0" + name)
            self.request_io["sent"] += 1
        except (ConnectionRefusedError, FileNotFoundError):
            self.request_io["refused"] += 1
        except BlockingIOError:
            self.request_io["dropped"] += 1

    def reset(self):
        self.last_request = None
        self._tick_snapshot = None
        self._last_sent_gen = None


class _RosTransport:
    """Private rclpy context, one node, one executor thread. Imported only on connect()."""

    def __init__(self, bridge: AutoDriveBridge):
        import rclpy
        from rclpy.executors import SingleThreadedExecutor
        from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
        from geometry_msgs.msg import Point
        from sensor_msgs.msg import Imu as ImuMsg, JointState, LaserScan
        from std_msgs.msg import String

        from rclpy.signals import SignalHandlerOptions

        self.context = rclpy.Context()
        # Never take over the host application's SIGINT/SIGTERM handling.
        rclpy.init(context=self.context, signal_handler_options=SignalHandlerOptions.NO)
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
