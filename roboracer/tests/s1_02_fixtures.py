"""Synthetic Devkit messages for S1-02 tests (duck-typed like the ROS messages; no ROS needed)."""

import json
import math
from types import SimpleNamespace as NS

SESSION = "f6cb2168761c44c797636f91a2c2776c"
OFFSET_NS = -38_740_261.5
BOUND_NS = 57_465_096.5
ROS_MINUS_MONO_NS = 1_789_968_000_000_000_000  # arbitrary fixed ROS-minus-bridge-monotonic offset


def header(stamp, frame):
    return NS(stamp=NS(sec=stamp // 1_000_000_000, nanosec=stamp % 1_000_000_000), frame_id=frame)


def frame(seq, ranges=None, position=(0.741, 3.158, 0.059), quaternion=(0.011, 0.011, -0.707, 0.707),
          episode=1, lidar_lag_s=0.017, basis="acquisition", encoder=0.0):
    """Messages of one telemetry frame plus its provenance JSON (as the runner publishes it)."""
    step = 17000 + 300 * seq
    sim_time = step / 1000.0
    mono = 1_216_405_000_000_000 + seq * 250_000_000
    times = {"lidar": (sim_time - lidar_lag_s, mono - int(lidar_lag_s * 1e9))}
    for name in ("ips", "imu", "left_encoder", "right_encoder"):
        times[name] = (sim_time, mono)
    sources, messages = {}, {}
    for name, (t, m) in times.items():
        ros = int(round(m - OFFSET_NS + ROS_MINUS_MONO_NS))
        sources[name] = {"seq": step, "episode": episode, "step": step, "sim_time": t, "mono_ns": m,
                         "mono_end_ns": m, "acquired": True, "reused": False, "ros_stamp_ns": ros}
    ranges = [5.0] * 1081 if ranges is None else ranges
    messages["lidar"] = NS(header=header(sources["lidar"]["ros_stamp_ns"], "lidar"), ranges=ranges,
                           angle_min=-2.3561899662017822, angle_increment=0.004363323096185923)
    messages["imu"] = NS(header=header(sources["imu"]["ros_stamp_ns"], "imu"),
                         orientation=NS(**dict(zip("xyzw", quaternion))),
                         angular_velocity=NS(x=0.0, y=0.0, z=0.0), linear_acceleration=NS(x=0.001, y=0.0, z=-0.001))
    for name in ("left_encoder", "right_encoder"):
        messages[name] = NS(header=header(sources[name]["ros_stamp_ns"], name), position=[encoder])
    messages["ips"] = NS(x=position[0], y=position[1], z=position[2])
    clock = {"offset_ns": OFFSET_NS, "bound_ns": BOUND_NS} if basis == "acquisition" else None
    record = {"session": SESSION, "telemetry_seq": seq, "episode": episode, "clock": clock, "sources": sources,
              "stamp_basis": basis, "ips_position": list(position)}
    return messages, json.dumps(record)


def deliver(assembler, messages, provenance, now_ns=0, provenance_first=False, skip=()):
    out = []
    if provenance_first:
        out += assembler.offer_provenance(provenance, now_ns)
    for name, message in messages.items():
        if name not in skip:
            out += assembler.offer(name, message, now_ns)
    if not provenance_first:
        out += assembler.offer_provenance(provenance, now_ns)
    return out


def yaw_quaternion(yaw):
    return (0.0, 0.0, math.sin(yaw / 2), math.cos(yaw / 2))
