"""Coherent observation snapshots from the AutoDRIVE Devkit topics (S1-02). ROS-free.

The provenance-enabled Devkit bridge (``autodrive_neutral.py --provenance``) publishes, for
every simulator telemetry frame, the stock sensor topics and then one
``/autodrive/f1tenth_1/provenance`` JSON message. Separate topics are not ordered relative to
each other, so ``SnapshotAssembler`` keeps provenance records pending, looks up each member and
commits a snapshot only when every member matches that frame's provenance:

- LaserScan, Imu and both encoder JointStates: header stamp equals the source's
  ``ros_stamp_ns`` (acquisition time mapped into ROS time);
- IPS ``Point`` (no header): value equals the provenance ``ips_position``.

Anything else (a member proven missing by a newer stamp or not arriving in time, a first frame
stamped at publication, a session/sequence/episode problem, a scan/pose skew beyond the limit)
rejects that frame and is counted; older unmatched messages are dropped. Nothing from a
rejected frame is ever published. IPS has no stamp, so it is matched by value: while the
vehicle is at rest an identical earlier Point may stand in for the frame's own (same value).
Messages are duck-typed so the analytical fixtures need no ROS installation.

Frames. The body frame is the reported IPS point, which is the rear-axle centre (agrees with
the serialized ``Transforms/Rear Axle Center`` to ~2 mm), +x forward, z up. Mounts come from
the serialized SIM1-02 scene, and the LiDAR mount and beam convention were confirmed by
ray-casting six recorded frames (``scripts/autodrive_scan_check.py``).

Time. Every sensor ``stamp`` is the acquisition time on the bridge host's CLOCK_MONOTONIC in
seconds (``mono_end_ns - clock offset``), the same domain as supervisor request times.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
import math
from collections import deque

import numpy as np

from avlite.c50_common.c52_world_sensor_datatypes import Imu, Lidar

SCHEMA = "roboracer.sim1/1"
HEADER_SOURCES = ("lidar", "imu", "left_encoder", "right_encoder")
TOPICS = HEADER_SOURCES + ("ips",)
FRAME_IDS = {"lidar": "lidar", "imu": "imu", "left_encoder": "left_encoder", "right_encoder": "right_encoder"}

# Serialized F1TENTH LIDAR component and scene mounts (rear-axle centre origin).
SCAN_ANGLE_MIN_RAD = math.radians(-135.0)
SCAN_INCREMENT_RAD = math.radians(0.25)
SCAN_BEAMS = 1081
SCAN_RANGE_MIN_M, SCAN_RANGE_MAX_M = 0.06, 10.0
# The Devkit publishes angle_min as the float32 of the literal -2.35619 (4.5e-6 rad from -135 deg).
ANGLE_MIN_TOLERANCE_RAD = 1e-5
LIDAR_MOUNT_M = (0.2733, 0.0, 0.096)
IMU_MOUNT_M = (0.08, 0.0, 0.055)
WHEELBASE_M = 0.331

# Default largest |sim_time(lidar) - sim_time(ips)|: one 20 Hz scan period plus margin.
MAX_SCAN_POSE_SKEW_S = 0.06
# Unconsumed messages kept per topic before the oldest is dropped.
QUEUE_LIMIT = 8
# A provenance record whose members have not all arrived is rejected after this long, or once
# two newer records are waiting (telemetry runs at ~4 Hz).
PENDING_LIMIT_NS = 500_000_000


class ObservationError(ValueError):
    """A frame that cannot be published as a coherent snapshot."""


def translation(xyz) -> np.ndarray:
    m = np.eye(4)
    m[:3, 3] = xyz
    return m


def stamp_ns(message) -> int:
    return int(message.header.stamp.sec) * 1_000_000_000 + int(message.header.stamp.nanosec)


def yaw_from_quaternion(x, y, z, w) -> float:
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def scan_points(ranges) -> np.ndarray:
    """(N, 4) float32 [x, y, z, intensity] in the LiDAR frame for finite in-range beams.

    Beam i points at angle_min + i * increment, counter-clockwise, x forward. Intensity is
    padded with 0: the vendor reports a constant 47 that carries no measurement.
    """
    r = np.asarray(ranges, dtype=np.float64)
    angles = SCAN_ANGLE_MIN_RAD + SCAN_INCREMENT_RAD * np.arange(len(r))
    keep = np.isfinite(r) & (r >= SCAN_RANGE_MIN_M) & (r <= SCAN_RANGE_MAX_M)
    points = np.zeros((int(keep.sum()), 4), dtype=np.float32)
    points[:, 0] = r[keep] * np.cos(angles[keep])
    points[:, 1] = r[keep] * np.sin(angles[keep])
    return points


@dataclass(frozen=True)
class GroundTruthPose:
    """Simulator truth (IPS + IMU orientation), labelled as such. Never an estimate."""

    x: float
    y: float
    z: float
    yaw: float
    stamp: float  # IPS acquisition, CLOCK_MONOTONIC seconds
    position_resolution_m: float = 0.001  # IPS is reported with 3 decimals
    label: str = "ground-truth"


@dataclass(frozen=True)
class Snapshot:
    """One committed telemetry frame. Treat as immutable; copy before handing out sensors."""

    session: str
    episode: int
    telemetry_seq: int
    lidar: Lidar
    imu: Imu
    pose: GroundTruthPose
    encoder_angles_rad: tuple[float, float]
    scan_ranges: np.ndarray = field(repr=False)  # (1081,) float32 as published, read-only
    sources: dict = field(repr=False)  # provenance per source: seq, sim_time, reused, stamp, bound
    clock_bound_s: float
    scan_pose_skew_s: float
    committed_monotonic_ns: int


class SnapshotAssembler:
    """Matches sensor messages to provenance records. Not thread-safe; callers serialize."""

    def __init__(self, max_scan_pose_skew_s: float = MAX_SCAN_POSE_SKEW_S,
                 pending_limit_ns: int = PENDING_LIMIT_NS):
        self.max_scan_pose_skew_s = max_scan_pose_skew_s
        self.pending_limit_ns = pending_limit_ns
        self.queues = {name: deque() for name in TOPICS}
        self.pending: deque = deque()  # (record, arrival ns), oldest first
        self.session: str | None = None
        self.episode = 0
        self.last_seq = 0
        self.committed = 0
        self.rejections: dict[str, int] = {}
        self.last_rejection: str | None = None
        self.dropped = 0

    # -- input -----------------------------------------------------------------------------
    def offer(self, topic: str, message, now_ns: int) -> list[Snapshot]:
        queue = self.queues[topic]
        if len(queue) >= QUEUE_LIMIT:
            queue.popleft()
            self.dropped += 1
        queue.append(message)
        return self._drain(now_ns)

    def offer_provenance(self, text: str, now_ns: int) -> list[Snapshot]:
        try:
            self.pending.append((self._admit(text), now_ns))
        except ObservationError:
            pass
        return self._drain(now_ns)

    # -- internals -------------------------------------------------------------------------
    def _reject(self, reason: str):
        key = reason.split(":")[0]
        self.rejections[key] = self.rejections.get(key, 0) + 1
        self.last_rejection = reason
        raise ObservationError(reason)

    def _admit(self, text: str) -> dict:
        """Frame-level checks done on arrival, so identity is enforced in arrival order."""
        try:
            record = json.loads(text)
        except ValueError:
            record = None
        if not isinstance(record, dict):
            self._reject("malformed provenance")
        session, seq, episode = record.get("session"), record.get("telemetry_seq"), record.get("episode")
        if not isinstance(session, str) or not isinstance(seq, int) or not isinstance(episode, int) \
                or not isinstance(record.get("sources"), dict):
            self._reject("malformed provenance")
        if self.session is not None and session != self.session:
            self._reject("session changed")
        if self.session is not None and seq <= self.last_seq:
            self._reject(f"telemetry sequence not increasing: {seq} after {self.last_seq}")
        if episode < self.episode:
            self._reject("episode moved backwards")
        self.session, self.last_seq, self.episode = session, seq, episode
        if record.get("stamp_basis") != "acquisition" or not record.get("clock"):
            self._reject("stamp basis is not acquisition (no clock exchange yet)")
        for name in TOPICS:
            entry = record["sources"].get(name)
            if not isinstance(entry, dict) or not entry.get("acquired"):
                self._reject(f"source not acquired: {name}")
            if entry.get("episode") != episode:
                self._reject(f"source from another episode: {name}")
        if not isinstance(record.get("ips_position"), list) or len(record["ips_position"]) != 3:
            self._reject("provenance carries no ips_position")
        return record

    def _locate(self, record):
        """Queue index per topic for this record, None to wait, or raise when proven missing."""
        found = {}
        for name in HEADER_SOURCES:
            expected = record["sources"][name].get("ros_stamp_ns")
            stamps = [stamp_ns(m) for m in self.queues[name]]
            if expected in stamps:
                found[name] = stamps.index(expected)
            elif any(s > expected for s in stamps):
                self._reject(f"stamp mismatch: {name}")
            else:
                return None
        expected = [float(v) for v in record["ips_position"]]
        matches = [i for i, m in enumerate(self.queues["ips"]) if [m.x, m.y, m.z] == expected]
        if not matches:
            return None
        found["ips"] = matches[0]
        return found

    def _consume(self, found) -> dict:
        members = {}
        for name, index in found.items():
            queue = self.queues[name]
            for _ in range(index):  # older, unmatched messages can never match a later frame
                queue.popleft()
                self.dropped += 1
            members[name] = queue.popleft()
        return members

    def _drain(self, now_ns: int) -> list[Snapshot]:
        out = []
        while self.pending:
            record, arrived = self.pending[0]
            try:
                found = self._locate(record)
                if found is None:
                    if len(self.pending) > 2 or now_ns - arrived > self.pending_limit_ns:
                        self.pending.popleft()
                        self._reject("incomplete frame")
                    break
                self.pending.popleft()
                out.append(self._build(record, self._consume(found), now_ns))
            except ObservationError:
                if self.pending and self.pending[0][0] is record:
                    self.pending.popleft()
        return out

    def _build(self, record, members, now_ns: int) -> Snapshot:
        sources = record["sources"]
        for name in HEADER_SOURCES:
            if members[name].header.frame_id != FRAME_IDS[name]:
                self._reject(f"unexpected frame id: {name}")
        scan, imu_msg, ips = members["lidar"], members["imu"], members["ips"]
        ranges = np.asarray(scan.ranges, dtype=np.float64)
        if len(ranges) != SCAN_BEAMS or not math.isclose(scan.angle_min, SCAN_ANGLE_MIN_RAD, abs_tol=ANGLE_MIN_TOLERANCE_RAD) \
                or not math.isclose(scan.angle_increment, SCAN_INCREMENT_RAD, abs_tol=1e-8) \
                or np.isnan(ranges).any() or (ranges < 0).any():
            self._reject("scan layout differs from the qualified convention")
        values = [imu_msg.orientation.x, imu_msg.orientation.y, imu_msg.orientation.z, imu_msg.orientation.w,
                  imu_msg.angular_velocity.x, imu_msg.angular_velocity.y, imu_msg.angular_velocity.z,
                  imu_msg.linear_acceleration.x, imu_msg.linear_acceleration.y, imu_msg.linear_acceleration.z,
                  ips.x, ips.y, ips.z]
        encoders = [float(members[n].position[0]) if len(members[n].position) == 1 else math.nan
                    for n in ("left_encoder", "right_encoder")]
        if not all(math.isfinite(v) for v in values + encoders):
            self._reject("non-finite reading")
        skew = abs(sources["lidar"]["sim_time"] - sources["ips"]["sim_time"])
        if skew > self.max_scan_pose_skew_s:
            self._reject(f"scan/pose skew: {skew:.3f} s")

        offset, bound = record["clock"]["offset_ns"], record["clock"]["bound_ns"]
        stamps = {name: (sources[name]["mono_end_ns"] - offset) / 1e9 for name in TOPICS}
        points = scan_points(ranges)
        points.setflags(write=False)  # shared by every SensorFrame built from this snapshot
        lidar = Lidar(sensor_name="lidar", sensor_id="autodrive-f1tenth-lidar", stamp=stamps["lidar"],
                      base_to_sensor=translation(LIDAR_MOUNT_M), points=points)
        imu = Imu(sensor_name="imu", sensor_id="autodrive-f1tenth-imu", stamp=stamps["imu"],
                  base_to_sensor=translation(IMU_MOUNT_M),
                  linear_accel=tuple(values[7:10]), angular_velocity=tuple(values[4:7]))
        pose = GroundTruthPose(x=ips.x, y=ips.y, z=ips.z, yaw=yaw_from_quaternion(*values[:4]), stamp=stamps["ips"])
        summary = {name: {"seq": sources[name]["seq"], "sim_time": sources[name]["sim_time"],
                          "reused": bool(sources[name].get("reused")), "stamp": stamps[name],
                          "ros_stamp_ns": sources[name].get("ros_stamp_ns")} for name in TOPICS}
        published = np.asarray(scan.ranges, dtype=np.float32).copy()
        published.setflags(write=False)
        self.committed += 1
        return Snapshot(session=record["session"], episode=record["episode"], telemetry_seq=record["telemetry_seq"],
                        lidar=lidar, imu=imu, pose=pose, encoder_angles_rad=tuple(encoders), scan_ranges=published,
                        sources=summary,
                        clock_bound_s=bound / 1e9, scan_pose_skew_s=skew, committed_monotonic_ns=now_ns)
