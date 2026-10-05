#!/usr/bin/env python3
"""Bounded SIM0 stationary qualification through the already qualified Devkit.

The run mode owns fresh player/bridge/observer processes. A PID-bound screenshot
review file enables only the Connect click. Replies are guarded to exact zero;
changed reported position or encoder values terminate an incomplete attempt.
The explicitly selected drift-diagnostic profile instead stops position changes
at 10 mm, keeps encoder/zero guards, and cannot complete a P0 observation.
The p0-creep profile is the amended P0 contract (user-approved 2026-10-05):
the same inclusive 10 mm bound for the inherited passive creep (SIM0-B06),
unchanged encoder/zero guards, and normal P0 completion.
No source acquisition timestamps, autonomous motion or stop response are claimed.
"""

import argparse
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path
import resource
import signal
import socket
import subprocess
import sys
import time


PLUGIN_DIRECTORY = Path(__file__).resolve().parents[1] / "roboracer"
MOTION_APPROVAL = Path(__file__).resolve().parents[1] / "docs/planning/s1-motion-approval.json"
TOPICS = ("throttle", "steering", "left_encoder", "right_encoder", "ips", "imu", "lidar", "front_camera")
PROFILES = ("p0", "p0-creep", "drift-diagnostic")
CREEP_BOUNDED = ("p0-creep", "drift-diagnostic")


def profile_record(profile):
    if profile not in PROFILES:
        raise ValueError("Unknown neutral profile")
    return {"name": profile, "diagnostic_only": profile == "drift-diagnostic",
            "position_stop_m": 0.010 if profile in CREEP_BOUNDED else 0.0,
            "position_stop_comparison": ">= cap" if profile in CREEP_BOUNDED else "any change",
            "encoder_stop": "any change", "commands": "exact zero only"}


def rejected_motion_fields(reference, motion, profile="p0"):
    profile_record(profile)  # Reject unknown profiles instead of relaxing a guard.
    changed = [key for key in ("Position", "Encoder Angles", "Encoder Ticks")
               if motion[key] != reference[key]]
    if profile in CREEP_BOUNDED:
        # Compare the decimal telemetry exactly: binary subtraction can otherwise
        # classify e.g. 0.060 - 0.050 just below the approved 0.010 boundary.
        squared = sum((Decimal(str(a)) - Decimal(str(b))) ** 2
                      for a, b in zip(motion["Position"], reference["Position"]))
        if squared < Decimal("0.010") ** 2:
            changed = [key for key in changed if key != "Position"]
    return changed


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def read(path):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def check_kinematics_status(state, pid, now_ns, closed=False):
    """Fail a diagnostic on the wrong producer, failed logging or stale heartbeat."""
    required = ("heartbeat_monotonic_ns", "last_sample_ns", "samples", "fixed_samples",
                "late_samples", "trace_bytes", "max_trace_bytes")
    if state.get("schema") != 1 or state.get("pid") != pid:
        raise RuntimeError("Kinematics status has the wrong schema or owned PID")
    if state.get("state") != ("closed" if closed else "ready") or state.get("error"):
        raise RuntimeError("Kinematics probe failed or unexpectedly closed: " + str(state.get("error")))
    if any(type(state.get(k)) is not int or state[k] < 0 for k in required):
        raise RuntimeError("Malformed kinematics status counters")
    if not state["samples"] or not state["fixed_samples"] or not state["late_samples"]:
        raise RuntimeError("Kinematics probe has no complete phase observations")
    if state["samples"] != state["fixed_samples"] + state["late_samples"]:
        raise RuntimeError("Kinematics sample counters disagree")
    if state["max_trace_bytes"] != 1024 * 1024 * 1024 or state["trace_bytes"] > state["max_trace_bytes"]:
        raise RuntimeError("Kinematics output exceeded the diagnostic bound")
    if not closed and any(not 0 <= now_ns - state[k] <= 3_000_000_000
                          for k in ("heartbeat_monotonic_ns", "last_sample_ns")):
        raise RuntimeError("Kinematics heartbeat/sample is stale or uses a different clock")


def check_kinematics_prefix(directory, pid):
    def invalid(value):
        raise ValueError("Nonfinite JSON constant: " + value)
    with (directory / "samples.jsonl").open() as stream:
        rows = [json.loads(stream.readline(32768), parse_constant=invalid) for _ in range(2)]
    header, sample = rows
    if header.get("kind") != "binding" or header.get("schema") != 1 or header.get("pid") != pid:
        raise RuntimeError("Kinematics trace binding does not match the owned process")
    if sample.get("kind") != "sample" or sample.get("index") != 0 or sample.get("phase") not in ("FixedUpdate", "LateUpdate"):
        raise RuntimeError("Kinematics trace lacks a valid first sample")
    return {"binding": header, "first_sample_monotonic_ns": sample["monotonic_ns"],
            "first_sample_phase": sample["phase"]}


SIM1_REPLY_FIELDS = {"RR Ping Mono", "RR Test Freeze", "RR Reply To", "RR Reply Frame Receipt",
                     "RR Guard Arm", "RR Guard Request", "RR Guard Envelope"}


# Confirmed motion-protocol stages (s1-motion-protocol.md v0.1); mirrors
# roboracer.runtime.supervisor_core.STAGES (a test checks they are equal).
MOTION_STAGES = {"m0": {"throttle": (0.0,), "steering": (0.0, 0.1, -0.1, 0.5, -0.5, 1.0, -1.0)},
                 "m1": {"throttle": (0.0, 0.002, 0.005, 0.01, 0.02), "steering": (0.0,)}}
# M1 hard containment in the bridge (fails closed): four pulses at the 0.5 m per-pulse cap.
# The calibration source applies the finer protocol abort rules (speed, travel, yaw, lateral, clearance).
M1_CONTAINMENT_M = 2.0
# 30 degrees (the controller's SteeringLimit, 0.5235988 rad) as telemetry reports it: rounded to
# 3 decimals, so full lock arrives as 0.524 (found in the first M0 attempt).
STEERING_FEEDBACK_LIMIT_RAD = 0.5245


def check_guard_request(text, stage):
    """Motion-stage runs: every outbound guard request must lie in the confirmed stage profile
    (throttle exactly 0 in M0). Raises before anything is sent otherwise."""
    fields = text.split(" ")
    if len(fields) != 8:
        raise ValueError("Malformed guard request in a motion stage")
    throttle, steering = float(fields[5]), float(fields[6])
    profile = MOTION_STAGES[stage]
    if throttle not in profile["throttle"] or steering not in profile["steering"]:
        raise ValueError(f"Guard request outside confirmed stage {stage}: {throttle} {steering}")


def check_zero_reply(event, data, allow_legacy=False):
    """Legacy controls are exact zero. Only the SIM1-02 legacy-bypass probe may send finite
    in-range legacy values, to a player whose guard must ignore them."""
    controls = {"V1 Throttle", "V1 Steering"}
    if event != "Bridge" or not controls <= set(data) or not set(data) - controls <= SIM1_REPLY_FIELDS:
        raise ValueError("Unexpected outbound event or command fields")
    values = [float(data[key]) for key in controls]
    if allow_legacy:
        if not all(math.isfinite(v) and abs(v) <= 1 for v in values):
            raise ValueError("Legacy bypass probe values must be finite and within [-1, 1]")
    elif any(v != 0.0 for v in values):
        raise ValueError("Nonzero/nonfinite control blocked")
    for key in ("RR Ping Mono", "RR Reply To", "RR Reply Frame Receipt"):
        if key in data and not data[key].isdigit():
            raise ValueError("Malformed " + key)
    from autodrive_provenance import FREEZABLE
    if any(kind and kind not in FREEZABLE for kind in data.get("RR Test Freeze", "").split(",")):
        raise ValueError("Unsupported test-hook request")


def motion_fields(data, stage=None):
    """Parsed motion telemetry. Actuator feedback must be exact zero, except steering feedback
    within the 30-degree limit in motion stage M0 (steering only); throttle is always zero."""
    result = {}
    for key, count in (("Position", 3), ("Encoder Angles", 2), ("Encoder Ticks", 2),
                       ("Orientation Quaternion", 4), ("Orientation Euler Angles", 3),
                       ("Angular Velocity", 3), ("Linear Acceleration", 3)):
        values = [float(v) for v in data["V1 " + key].split()]
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise ValueError("Malformed/nonfinite " + key)
        result[key] = values
    for key in ("Throttle", "Steering"):
        value = float(data["V1 " + key])
        if key == "Steering" and stage == "m0" and math.isfinite(value) and abs(value) <= STEERING_FEEDBACK_LIMIT_RAD:
            result["Steering Feedback"] = value
            continue
        # M1: throttle feedback (reported to 3 decimals) must be one of the stage's values.
        if key == "Throttle" and stage == "m1" and math.isfinite(value) and \
                any(abs(value - allowed) <= 0.0005 for allowed in MOTION_STAGES["m1"]["throttle"]):
            result["Throttle Feedback"] = value
            continue
        if value != 0.0:
            raise ValueError("Nonzero/nonfinite actuator feedback: " + key)
    return result


def bridge(args):
    # Imports deliberately stay inside this explicit child entrypoint.
    import gevent
    import numpy as np
    import autodrive_f1tenth.autodrive_incoming_bridge as incoming

    out = args.results
    state = {"pid": os.getpid(), "zero_only": True, "reply_delay_seconds": args.reply_delay,
             "profile": profile_record(args.profile),
             "source_file": incoming.__file__, "connections": 0, "processed": 0,
             "emissions": 0, "errors": [], "ready": True, "transport_requests": []}
    raw_emit, raw_bridge = incoming.sio.emit, incoming.bridge
    raw_wsgi = incoming.socketio.WSGIApp
    reference = None
    trace = (out / "bridge-frames.jsonl").open("w", buffering=1)
    tracker = provenance_publisher = first_frame_ns = None
    acquisition_stamps = {}
    if args.provenance:
        from autodrive_provenance import ProvenanceTracker
        tracker = ProvenanceTracker(expect_test_hooks=bool(args.freeze_test))
        state.update(provenance=True, freeze_test=args.freeze_test, freeze_window=args.freeze_window,
                     hook_rejection_probe=not args.freeze_test, clock_samples=0)

        def restamp(name, factory):
            def wrapper(*positional, **keywords):
                message = factory(*positional, **keywords)
                key = name if isinstance(name, str) else name(*positional)
                if key in acquisition_stamps:
                    message.header.stamp = acquisition_stamps[key]
                return message
            return wrapper

        # Header stamps become acquisition time mapped into ROS time; vendor stamps remain
        # only until the first clock exchange (recorded as stamp_basis).
        incoming.create_laser_scan_msg = restamp("lidar", incoming.create_laser_scan_msg)
        incoming.create_imu_msg = restamp("imu", incoming.create_imu_msg)
        incoming.create_image_msg = restamp("front_camera", incoming.create_image_msg)
        incoming.create_joint_state_msg = restamp(lambda angle, joint, frame: joint, incoming.create_joint_state_msg)

    driver = inbox = guard_tracker = None
    reply_context = {}
    if args.guard:
        from autodrive_guard import GuardTracker, RequestInbox, ScenarioDriver, socket_name
        inbox = RequestInbox(socket_name(os.getpid()))
        # Only a confirmed motion stage runs a motion-authorized player; the mode is checked per frame.
        guard_tracker = GuardTracker(require_interlock=not args.motion_stage)
        driver = ScenarioDriver(inbox, lambda number: str(number) in read(out / "actions-done.json"),
                                mode=args.guard, duration_ns=int(args.duration * 1e9))
        state.update(guard_mode=args.guard, guard_socket=socket_name(os.getpid()))

    def freeze_request():
        if args.freeze_test:
            start, end = args.freeze_window
            elapsed = (time.monotonic_ns() - first_frame_ns) / 1e9 if first_frame_ns else -1
            return args.freeze_test if start <= elapsed < end else ""
        # Clean runs send one hook request, which a hook-less player must reject and count.
        return "lidar" if state["processed"] == 5 else None

    def checkpoint():
        save(out / "bridge-status.json", state)

    def traced_wsgi(*positional, **keywords):
        application = raw_wsgi(*positional, **keywords)

        def dispatch(environ, start_response):
            # Record handshake arrival only; never capture camera/control payloads here.
            from urllib.parse import parse_qs
            query = parse_qs(environ.get("QUERY_STRING", ""))
            state["transport_requests"].append({
                "received_monotonic_ns": time.monotonic_ns(),
                "method": environ.get("REQUEST_METHOD"), "path": environ.get("PATH_INFO"),
                "remote_address": environ.get("REMOTE_ADDR"),
                "engineio": query.get("EIO"), "transport": query.get("transport")})
            checkpoint()
            return application(environ, start_response)

        return dispatch

    pending_provenance = []

    def publish_provenance():
        # D3: the frame's provenance goes out as soon as its sensor topics are published,
        # before the paced reply, so consumers commit snapshots one pacing delay earlier.
        nonlocal provenance_publisher
        if pending_provenance:
            from std_msgs.msg import String
            if provenance_publisher is None:
                provenance_publisher = incoming.autodrive_incoming_bridge.create_publisher(
                    String, "/autodrive/f1tenth_1/provenance", 10)
            message = String()
            message.data = pending_provenance.pop()
            provenance_publisher.publish(message)
            state["provenance_before_reply"] = state.get("provenance_before_reply", 0) + 1

    def guarded_emit(event, data=None, **kwargs):
        publish_provenance()
        check_zero_reply(event, data)
        gevent.sleep(args.reply_delay)
        # Guard replies are chosen after the pacing delay so forwarded requests are as fresh as possible.
        reply = driver.next_reply() if driver is not None else {}
        if reply.get("hold_s"):
            gevent.sleep(reply["hold_s"])
        if tracker is not None:
            data = dict(data)
            request = freeze_request()
            if request is not None:
                data["RR Test Freeze"] = request
            skew = reply.get("ping_skew_ns", 0)
            now = time.monotonic_ns()
            # A skewed ping is injected only for the guard's discontinuity case; it is not registered,
            # so the bridge's own clock estimate ignores its echo.
            data["RR Ping Mono"] = str(now + skew) if skew else tracker.clock.ping(now)  # stamped at send time
            if driver is not None:
                data["RR Reply To"] = str(reply_context["seq"])
                if not reply.get("no_frame_receipt"):
                    data["RR Reply Frame Receipt"] = str(reply_context["received"] + skew)
                for key, field in (("arm", "RR Guard Arm"), ("request", "RR Guard Request"),
                                   ("envelope", "RR Guard Envelope")):
                    if reply.get(key) is not None:
                        data[field] = reply[key]
                if reply.get("legacy"):
                    data["V1 Throttle"], data["V1 Steering"] = reply["legacy"]
            check_zero_reply(event, data, allow_legacy=bool(reply.get("legacy")))
            if args.motion_stage and "RR Guard Request" in data:
                check_guard_request(data["RR Guard Request"], args.motion_stage)
        if driver is not None:
            state.update(action=driver.action, guard=driver.summary(), supervisor_requests_received=inbox.received)
            checkpoint()
        state["emissions"] += 1
        return raw_emit(event, data=data, **kwargs)

    @incoming.sio.on("connect")
    def connected(sid, environ):
        state["connections"] += 1
        if state["connections"] != 1:
            state["errors"].append("Unexpected reconnection in a fresh-process trial")
        checkpoint()

    @incoming.sio.on("Bridge")
    def observed(sid, data):
        nonlocal reference
        if state["errors"]:
            return  # Parent observes failure and contains the owned process group.
        received = time.monotonic_ns()
        try:
            motion = motion_fields(data, args.motion_stage)
            ranges = np.array([float(v) for v in data["V1 LIDAR Range Array"].split()])
            intensities = np.array([float(v) for v in data["V1 LIDAR Intensity Array"].split()])
            if not len(ranges) or len(ranges) != len(intensities) or np.isnan(ranges).any() or (ranges < 0).any():
                raise ValueError("Malformed range/intensity arrays")
            rate = float(data["V1 LIDAR Scan Rate"])
            if not math.isfinite(rate) or rate <= 0:
                raise ValueError("Invalid reported scan rate")
            if reference is None:
                reference = motion
                save(out / "first-raw-frame.json", data)
            changed = rejected_motion_fields(reference, motion, args.profile)
            if args.motion_stage == "m1":
                # Motion is intended: only the hard containment bound stops the bridge here.
                changed = ["Position"] if math.dist(reference["Position"], motion["Position"]) >= M1_CONTAINMENT_M else []
            displacement = math.dist(reference["Position"], motion["Position"])
            row = {"index": state["processed"], "received_monotonic_ns": received,
                   "motion": motion, "position_displacement_m": displacement,
                   "throttle": data["V1 Throttle"], "steering": data["V1 Steering"],
                   "reported_scan_rate": rate, "range_count": len(ranges),
                   "finite_ranges": int(np.isfinite(ranges).sum()),
                   "raw_range_sha256": hashlib.sha256(data["V1 LIDAR Range Array"].encode()).hexdigest()}
            if changed:
                row["unexpected_movement_fields"] = changed
                trace.write(json.dumps(row) + "\n")
                raise ValueError("Unexpected movement in reported fields: " + ", ".join(changed))
            if tracker is not None:
                nonlocal provenance_publisher, first_frame_ns
                first_frame_ns = first_frame_ns or received
                provenance = tracker.check(data, received)  # ProvenanceError fails closed below
                row["provenance"] = provenance
                acquisition_stamps.clear()
                clock = provenance["clock"]
                if clock:
                    import rclpy.time
                    node = incoming.autodrive_incoming_bridge
                    ros_now, mono_now = node.get_clock().now().nanoseconds, time.monotonic_ns()
                    for name, entry in provenance["sources"].items():
                        if entry["acquired"]:
                            acquired = entry["mono_end_ns"] - clock["offset_ns"]
                            entry["ros_stamp_ns"] = int(round(ros_now - (mono_now - acquired)))
                            acquisition_stamps[name] = rclpy.time.Time(nanoseconds=entry["ros_stamp_ns"]).to_msg()
                    state["clock_samples"] = len(tracker.clock.samples)
                row["stamp_basis"] = "acquisition" if clock else "bridge-publication"
                if driver is not None:
                    row["guard"] = guard_tracker.check(data)  # GuardError fails closed below
                    expected = "motion-authorized" if args.motion_stage else "interlock"
                    if row["guard"]["config"]["mode"] != expected:
                        raise ValueError(f"Guard mode {row['guard']['config']['mode']} is not {expected}")
                    driver.on_frame(row["guard"], tracker.session, provenance["episode"])
                    reply_context.update(seq=provenance["telemetry_seq"], received=received)
            if tracker is not None:
                # ips_position lets a consumer match the header-less IPS Point to this frame.
                pending_provenance[:] = [json.dumps({"session": tracker.session, **provenance,
                                                     "stamp_basis": row["stamp_basis"],
                                                     "ips_position": motion["Position"]})]
            raw_bridge(sid, data)  # Official conversion/publishing; guarded reply (emit publishes provenance first).
            publish_provenance()  # only if the official handler did not emit
            row["handler_completed_monotonic_ns"] = time.monotonic_ns()
            row["publisher_count"] = len(list(incoming.autodrive_incoming_bridge.publishers))
            trace.write(json.dumps(row) + "\n")
            state.setdefault("first_complete_frame_ns", row["handler_completed_monotonic_ns"])
            state["last_received_ns"] = received
            state["processed"] += 1
            checkpoint()
        except Exception as exc:
            state["errors"].append(type(exc).__name__ + ": " + str(exc))
            checkpoint()

    incoming.sio.emit = guarded_emit
    incoming.socketio.WSGIApp = traced_wsgi
    checkpoint()
    try:
        incoming.main()
    finally:
        state["completed"] = True
        checkpoint()
        trace.close()


def observe(args):
    import avlite
    import numpy as np
    import rclpy
    from rclpy.executors import ExternalShutdownException
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from std_msgs.msg import Float32
    from geometry_msgs.msg import Point
    from sensor_msgs.msg import JointState, Imu, LaserScan, Image

    rclpy.init()
    node = rclpy.create_node("sim0_neutral_readonly_observer")
    qos = QoSProfile(reliability=ReliabilityPolicy.RELIABLE, history=HistoryPolicy.KEEP_LAST, depth=1)
    trace = (args.results / "ros-messages.jsonl").open("w", buffering=1)
    state = {"pid": os.getpid(), "avlite_file": avlite.__file__, "numpy_version": np.__version__,
             "counts": {}, "last_received_ns": {}, "read_only": True, "ready": False}

    def checkpoint():
        save(args.results / "observer-status.json", state)

    def callback(name, msg):
        now = time.monotonic_ns()
        row = {"topic": name, "index": state["counts"].get(name, 0), "received_monotonic_ns": now}
        if hasattr(msg, "header"):
            row.update(stamp_ns=msg.header.stamp.sec * 1000000000 + msg.header.stamp.nanosec,
                       frame=msg.header.frame_id)
        if name == "lidar":
            values = np.asarray(msg.ranges, dtype=np.float32)
            row.update(count=len(values), finite_count=int(np.isfinite(values).sum()),
                       range_sha256=hashlib.sha256(values.tobytes()).hexdigest(),
                       angle_min=msg.angle_min, angle_max=msg.angle_max, angle_increment=msg.angle_increment,
                       range_min=msg.range_min, range_max=msg.range_max,
                       scan_time=msg.scan_time, time_increment=msg.time_increment)
        elif name == "front_camera":
            row.update(width=msg.width, height=msg.height, step=msg.step, encoding=msg.encoding,
                       byte_count=len(msg.data), data_sha256=hashlib.sha256(bytes(msg.data)).hexdigest())
        elif name == "ips":
            row["position"] = [msg.x, msg.y, msg.z]
        elif name == "imu":
            row["orientation"] = [msg.orientation.x, msg.orientation.y, msg.orientation.z, msg.orientation.w]
            row["angular_velocity"] = [msg.angular_velocity.x, msg.angular_velocity.y, msg.angular_velocity.z]
            row["linear_acceleration"] = [msg.linear_acceleration.x, msg.linear_acceleration.y, msg.linear_acceleration.z]
        elif name.endswith("encoder"):
            row["position"] = list(msg.position)
        else:
            row["value"] = msg.data
        trace.write(json.dumps(row) + "\n")
        state["counts"][name] = row["index"] + 1
        state["last_received_ns"][name] = now
        if set(state["counts"]) == set(TOPICS):
            state.setdefault("first_complete_observation_ns", now)
        checkpoint()

    subscriptions = []
    if args.provenance:
        from std_msgs.msg import String

        def provenance_callback(msg):
            trace.write(json.dumps({"topic": "provenance", "received_monotonic_ns": time.monotonic_ns(),
                                    "data": json.loads(msg.data)}) + "\n")
            state["provenance_count"] = state.get("provenance_count", 0) + 1

        subscriptions.append(node.create_subscription(String, "/autodrive/f1tenth_1/provenance",
                                                      provenance_callback, 10))
    types = (Float32, Float32, JointState, JointState, Point, Imu, LaserScan, Image)
    for name, kind in zip(TOPICS, types):
        subscriptions.append(node.create_subscription(kind, "/autodrive/f1tenth_1/" + name,
                             lambda msg, name=name: callback(name, msg), qos))
    state["ready"] = True
    checkpoint()
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.1)
    except ExternalShutdownException:
        pass
    finally:
        state["completed"] = True
        checkpoint()
        node.destroy_node()
        rclpy.try_shutdown()
        trace.close()


def plugin_observe(args):
    """S1-02: the plugin's AutoDriveBridge, loaded by AVLite's own plugin loader, as one more
    read-only subscriber. Records every committed snapshot; never publishes or commands."""
    import numpy as np
    from avlite.c60_apps.c63_plugins import import_plugin_modules

    executer = None
    if args.supervisor:
        # S1 stack mode: AVLite's own factory and SyncExecuter run HoldController through the
        # bridge; requests go to the separate supervisor process (exact zero only).
        from avlite.c60_apps.c62_factory import executor_factory
        from avlite.c60_apps.c69_settings import AppSettings
        AppSettings.c62_default_plugins = []
        AppSettings.c62_community_plugins = {"roboracer": str(args.plugin)}
        executer = executor_factory(
            executer_type="SyncExecuter", bridge="AutoDriveBridge", perception_strategy_name="",
            localization_strategy_name="", mapping_strategy_name="", global_planner_strategy_name="",
            local_planner_strategy_name="", controller_strategy_name="HoldController", execution_task_names=[],
            default_global_trajectory_file="", map_file="", load_plugins=True)
        plugin = sys.modules["avlite.plugins.roboracer"]
        bridge = executer.world
    else:
        import_plugin_modules(str(args.plugin), pkg_name="roboracer")
        plugin = sys.modules["avlite.plugins.roboracer"]
        bridge = plugin.AutoDriveBridge()
    trace = (args.results / "plugin-snapshots.jsonl").open("w", buffering=1)
    state = {"pid": os.getpid(), "plugin": str(args.plugin), "plugin_file": plugin.__file__,
             "stack_capabilities": sorted(c.name for c in bridge.stack_capabilities),
             "max_target_speed_mps": plugin.PluginSettings.max_target_speed_mps, "ready": False, "snapshots": 0,
             "stack": bool(executer), "supervisor": args.supervisor, "ticks": 0, "tick_overruns": 0}
    stop = []

    def checkpoint():
        state["statistics"] = bridge.statistics()
        save(args.results / "plugin-observer-status.json", state)

    def record(snapshot):
        trace.write(json.dumps({
            "telemetry_seq": snapshot.telemetry_seq, "session": snapshot.session, "episode": snapshot.episode,
            "committed_monotonic_ns": snapshot.committed_monotonic_ns,
            "pose": [snapshot.pose.x, snapshot.pose.y, snapshot.pose.z, snapshot.pose.yaw],
            "pose_label": snapshot.pose.label, "pose_age_at_commit_s": snapshot.committed_monotonic_ns / 1e9 - snapshot.pose.stamp,
            "lidar_stamp_s": snapshot.lidar.stamp, "imu_stamp_s": snapshot.imu.stamp,
            "sources": snapshot.sources, "scan_pose_skew_s": snapshot.scan_pose_skew_s,
            "clock_bound_s": snapshot.clock_bound_s, "points": len(snapshot.lidar.points),
            "scan_sha256": hashlib.sha256(np.ascontiguousarray(snapshot.scan_ranges).tobytes()).hexdigest(),
            "lidar_mount": snapshot.lidar.base_to_sensor[:3, 3].tolist(),
            "imu_mount": snapshot.imu.base_to_sensor[:3, 3].tolist(),
            "encoders": list(snapshot.encoder_angles_rad)}) + "\n")
        state["snapshots"] += 1

    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))
    bridge.snapshot_listener = record
    bridge.connect(supervisor=args.supervisor)
    state["ready"] = True
    checkpoint()
    ticks = (args.results / "plugin-ticks.jsonl").open("w", buffering=1) if executer else None
    try:
        period, next_tick, next_checkpoint = 0.1, time.monotonic(), time.monotonic()
        while not stop:
            if executer is None:
                time.sleep(0.2)
                checkpoint()
                continue
            started = time.monotonic_ns()
            # Stage periods slightly below the tick so AVLite's float time sum never skips control.
            stage = period * 0.99
            executer.step(sim_dt=period, control_dt=stage, replan_dt=stage, perception_dt=stage,
                          localization_dt=stage)
            tick = bridge._tick_snapshot
            ticks.write(json.dumps({"start_ns": started, "end_ns": time.monotonic_ns(),
                                    "telemetry_seq": tick.telemetry_seq if tick else None,
                                    "request_seq": bridge._request_seq}) + "\n")
            state["ticks"] += 1
            next_tick += period
            delay = next_tick - time.monotonic()
            if delay < 0:
                state["tick_overruns"] += 1
                next_tick = time.monotonic()
            else:
                time.sleep(delay)
            if time.monotonic() >= next_checkpoint:
                checkpoint()
                next_checkpoint = time.monotonic() + 0.2
    finally:
        bridge.close()
        state["completed"] = True
        checkpoint()
        trace.close()
        if ticks is not None:
            ticks.close()


M0_SPAWN_XY = (0.741, 3.158)  # recorded spawn IPS (S1-02)
M0_HOLD_S = 1.0
M0_SETTLE_S = 3.0
M0_EXPIRY_WAIT_S = 4.0


def m0_schedule():
    """(start s, end s, steering) after the settle: each value held 1 s with 1 s at zero between,
    then the expiry case: +0.5 held 1 s, after which nothing more is sent."""
    steps, t = [], 0.0
    for value in MOTION_STAGES["m0"]["steering"][1:]:
        steps += [(t, t + M0_HOLD_S, value), (t + M0_HOLD_S, t + 2 * M0_HOLD_S, 0.0)]
        t += 2 * M0_HOLD_S
    steps.append((t, t + M0_HOLD_S, 0.5))
    return steps


def calibrate(args):
    """Motion protocol v0.1 D2: scripted calibration source for a confirmed stage (M0 only).
    Observes through the plugin's AutoDriveBridge, sends normalized requests to the supervisor
    (which bounds them again), and aborts to zero on drift, stale observation or guard fault."""
    import numpy as np
    from avlite.c60_apps.c63_plugins import import_plugin_modules

    if args.motion_stage == "m1":
        return calibrate_m1(args)
    if args.motion_stage != "m0":
        raise SystemExit("Unknown motion stage")
    import_plugin_modules(str(args.plugin), pkg_name="roboracer")
    plugin = sys.modules["avlite.plugins.roboracer"]
    bridge = plugin.AutoDriveBridge()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)
    log = (args.results / "calibration-requests.jsonl").open("w", buffering=1)
    schedule = m0_schedule()
    state = {"pid": os.getpid(), "stage": args.motion_stage, "phase": "wait-armed", "ready": False, "seq": 0,
             "sent": 0, "send_failures": 0, "schedule": schedule, "abort": None, "precheck": None}
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))

    def checkpoint():
        save(args.results / "calibration-status.json", state)

    def send(snapshot, steering):
        state["seq"] += 1
        message = {"kind": "calibration", "origin": "cal", "seq": state["seq"], "gen_ns": time.monotonic_ns(),
                   "throttle": 0.0, "steering": steering,
                   "observation": {"telemetry_seq": snapshot.telemetry_seq,
                                   "stamp_ns": int(round(snapshot.pose.stamp * 1e9))}}
        try:
            sock.sendto(json.dumps(message).encode(), "\0" + args.supervisor)
            state["sent"] += 1
        except (BlockingIOError, ConnectionRefusedError, FileNotFoundError):
            state["send_failures"] += 1
        log.write(json.dumps(dict(message, phase=state["phase"])) + "\n")

    def sector_min(ranges, low_deg, high_deg):
        start, end = int((low_deg + 135) / 0.25), int((high_deg + 135) / 0.25)
        values = np.asarray(ranges[start:end + 1], dtype=float)
        values = values[np.isfinite(values)]
        return float(values.min()) if len(values) else math.inf

    bridge.connect()
    state["ready"] = True
    checkpoint()
    reference = phase_start = None
    last_seq, last_new = None, time.monotonic()
    try:
        while not stop:
            time.sleep(0.1)
            snapshot = bridge.latest()
            now = time.monotonic()
            if snapshot is None:
                continue
            if snapshot.telemetry_seq != last_seq:
                last_seq, last_new = snapshot.telemetry_seq, now
            guard_state = read(args.results / "bridge-status.json").get("guard", {}).get("state")
            phase = state["phase"]
            if phase in ("done", "aborted-done"):
                continue
            moving = phase in ("profile", "expiry-wait")
            if moving and reference is not None:
                drift = math.dist(reference, (snapshot.pose.x, snapshot.pose.y))
                reason = ("displacement %.4f m" % drift if drift > 0.010 else
                          "no new observation for %.2f s" % (now - last_new) if now - last_new > 0.6 else
                          "guard fault" if guard_state == "fault" else None)
                if reason and state["phase"] == "profile":
                    state.update(phase="aborted", abort=reason)
                    phase_start = now
                    checkpoint()
            phase = state["phase"]
            if phase == "wait-armed":
                send(snapshot, 0.0)
                if guard_state == "armed":
                    state["phase"], phase_start = "settle", now
            elif phase == "settle":
                send(snapshot, 0.0)
                if now - phase_start >= M0_SETTLE_S:
                    ranges = snapshot.scan_ranges
                    reference = (snapshot.pose.x, snapshot.pose.y)
                    check = {"spawn_offset_m": math.dist(reference, M0_SPAWN_XY),
                             "left_min_m": sector_min(ranges, 80, 100), "right_min_m": sector_min(ranges, -100, -80),
                             "telemetry_seq": snapshot.telemetry_seq}
                    check["passed"] = check["spawn_offset_m"] <= 0.020 and min(check["left_min_m"], check["right_min_m"]) >= 0.4
                    state["precheck"] = check
                    state["phase"], phase_start = ("profile", now) if check["passed"] else ("aborted", now)
                    if not check["passed"]:
                        state["abort"] = "workspace precheck"
            elif phase == "profile":
                elapsed = now - phase_start
                current = [value for start, end, value in schedule if start <= elapsed < end]
                if current:
                    send(snapshot, current[0])
                else:
                    state["phase"], phase_start = "expiry-wait", now  # stop sending: the lease must expire
            elif phase == "expiry-wait":
                if now - phase_start >= M0_EXPIRY_WAIT_S:
                    state["phase"] = "done"
            elif phase == "aborted":
                if now - phase_start < 1.0:
                    send(snapshot, 0.0)
                else:
                    state["phase"] = "aborted-done"
            checkpoint()
    finally:
        bridge.close()
        sock.close()
        state["completed"] = True
        checkpoint()
        log.close()


M1_PULSES = (0.002, 0.005, 0.01, 0.02)  # 0.02 only if 0.01 stays under the caps
M1_SPEED_CAP_MPS, M1_TRAVEL_CAP_M = 0.5, 0.5
M1_REST_S = 3.0             # from pulse start; covers the 1.5 s stop window with margin
M1_STOP_SPEED_MPS = 0.02
M1_ARMED_LIMIT_S = 18.0     # protocol: at most 20 s armed per trial
M1_TRIAL_TRAVEL_M = 3.0
M1_FRAME_GAP_S = 0.6


def sector_min(ranges, low_deg, high_deg):
    """Minimum finite range in [low, high] degrees of the 1081-beam scan (CCW from -135)."""
    import numpy as np
    start, end = int((low_deg + 135) / 0.25), int((high_deg + 135) / 0.25)
    values = np.asarray(ranges[start:end + 1], dtype=float)
    values = values[np.isfinite(values)]
    return float(values.min()) if len(values) else math.inf


def m1_next_pulse(done):
    """Next throttle of the ascending sequence, or None. A step is taken only if every earlier
    pulse stayed under both caps and the previous peak, scaled linearly by throttle, is under
    the speed cap (a conservative addition that can only skip motion)."""
    if any(p["peak_speed_mps"] > M1_SPEED_CAP_MPS or p["travel_m"] > M1_TRAVEL_CAP_M for p in done):
        return None
    if len(done) >= len(M1_PULSES):
        return None
    candidate = M1_PULSES[len(done)]
    if done and done[-1]["peak_speed_mps"] * candidate / done[-1]["throttle"] > M1_SPEED_CAP_MPS:
        return None
    return candidate


def calibrate_m1(args):
    """M1: forward throttle pulses from rest, steering exactly 0. Event-driven on committed
    snapshots so each nonzero request is forwarded in exactly one reply (one frame interval)."""
    import queue
    from avlite.c60_apps.c63_plugins import import_plugin_modules

    import_plugin_modules(str(args.plugin), pkg_name="roboracer")
    plugin = sys.modules["avlite.plugins.roboracer"]
    bridge = plugin.AutoDriveBridge()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)
    log = (args.results / "calibration-requests.jsonl").open("w", buffering=1)
    frames_log = (args.results / "calibration-frames.jsonl").open("w", buffering=1)
    arrivals = queue.Queue()
    state = {"pid": os.getpid(), "stage": "m1", "phase": "wait-armed", "ready": False, "seq": 0, "sent": 0,
             "send_failures": 0, "pulses": [], "abort": None, "precheck": None, "finish_reason": None}
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))

    def checkpoint():
        save(args.results / "calibration-status.json", state)

    def send(snapshot, throttle):
        state["seq"] += 1
        message = {"kind": "calibration", "origin": "cal", "seq": state["seq"], "gen_ns": time.monotonic_ns(),
                   "throttle": throttle, "steering": 0.0,
                   "observation": {"telemetry_seq": snapshot.telemetry_seq,
                                   "stamp_ns": int(round(snapshot.pose.stamp * 1e9))}}
        try:
            sock.sendto(json.dumps(message).encode(), "\0" + args.supervisor)
            state["sent"] += 1
        except (BlockingIOError, ConnectionRefusedError, FileNotFoundError):
            state["send_failures"] += 1
        log.write(json.dumps(dict(message, phase=state["phase"])) + "\n")

    bridge.snapshot_listener = arrivals.put  # transport thread; the queue hands snapshots over
    bridge.connect()
    state["ready"] = True
    checkpoint()
    previous = pulse = None
    armed_at = phase_start = stopped_at = None
    try:
        while not stop:  # after done, idle until the runner's SIGTERM (an exiting child fails the trial)
            try:
                snapshot = arrivals.get(timeout=M1_FRAME_GAP_S)
                if state["phase"] in ("done", "aborted-done"):
                    continue
            except queue.Empty:
                if state["phase"] in ("done", "aborted-done"):
                    continue
                if state["phase"] in ("pulse", "rest", "ready") and state["abort"] is None:
                    state.update(phase="aborted", abort=f"no new observation for {M1_FRAME_GAP_S} s")
                    phase_start = time.monotonic()
                elif state["phase"] in ("finish", "aborted") and time.monotonic() - phase_start >= 4.0:
                    state["phase"] = "done" if state["phase"] == "finish" else "aborted-done"
                checkpoint()
                continue
            now = time.monotonic()
            sim = snapshot.sources["ips"]["sim_time"]
            x, y, yaw = snapshot.pose.x, snapshot.pose.y, snapshot.pose.yaw
            speed = (math.dist((x, y), previous[:2]) / (sim - previous[2])) if previous and sim > previous[2] else 0.0
            previous = (x, y, sim)
            ranges = snapshot.scan_ranges
            forward, left, right = sector_min(ranges, -15, 15), sector_min(ranges, 80, 100), sector_min(ranges, -100, -80)
            guard_state = read(args.results / "bridge-status.json").get("guard", {}).get("state")
            phase = state["phase"]
            frames_log.write(json.dumps({"t": time.monotonic_ns(), "telemetry_seq": snapshot.telemetry_seq,
                                         "ips_sim_time": sim, "pose": [x, y, yaw], "speed_mps": speed,
                                         "forward_m": forward, "left_m": left, "right_m": right,
                                         "guard": guard_state, "phase": phase}) + "\n")

            # Abort monitor (protocol §3) while anything may be moving.
            if phase in ("pulse", "rest", "ready") and state["abort"] is None and pulse is not None:
                dx, dy = x - pulse["start"][0], y - pulse["start"][1]
                heading = pulse["start"][2]
                lateral = abs(-math.sin(heading) * dx + math.cos(heading) * dy)
                yaw_change = abs(math.degrees(math.remainder(yaw - heading, math.tau)))
                reason = ("guard fault" if guard_state == "fault" else
                          "yaw change %.1f deg" % yaw_change if yaw_change > 10 else
                          "lateral deviation %.3f m" % lateral if lateral > 0.15 else
                          "forward clearance %.2f m" % forward if forward < 1.0 else
                          "side clearance %.2f m" % min(left, right) if min(left, right) < 0.25 else None)
                if reason:
                    state.update(phase="aborted", abort=reason)
                    phase_start = now
            phase = state["phase"]

            if phase == "wait-armed":
                send(snapshot, 0.0)
                if guard_state == "armed":
                    state["phase"], armed_at, phase_start = "settle", now, now
            elif phase == "settle":
                send(snapshot, 0.0)
                if now - phase_start >= M0_SETTLE_S:
                    check = {"spawn_offset_m": math.dist((x, y), M0_SPAWN_XY), "forward_min_m": forward,
                             "left_min_m": left, "right_min_m": right, "telemetry_seq": snapshot.telemetry_seq}
                    check["passed"] = check["spawn_offset_m"] <= 0.020 and forward >= 1.5 and min(left, right) >= 0.4
                    state["precheck"] = check
                    if check["passed"]:
                        state["phase"] = "ready"
                    else:
                        state.update(phase="aborted", abort="workspace precheck")
                        phase_start = now
            elif phase == "ready":
                travelled = sum(p["travel_m"] for p in state["pulses"])
                candidate = m1_next_pulse(state["pulses"])
                reason = ("sequence complete" if candidate is None else
                          "armed time" if now - armed_at + M1_REST_S > M1_ARMED_LIMIT_S else
                          "trial travel" if travelled + M1_TRAVEL_CAP_M > M1_TRIAL_TRAVEL_M else
                          "forward clearance before pulse" if forward < 1.5 else
                          "side clearance before pulse" if min(left, right) < 0.4 else None)
                if reason:
                    state.update(phase="finish", finish_reason=reason)
                    phase_start = now  # stop sending: the lease expires with zero output
                elif speed < M1_STOP_SPEED_MPS:
                    pulse = {"throttle": candidate, "start": (x, y, yaw), "start_sim": sim,
                             "start_telemetry_seq": snapshot.telemetry_seq, "peak_speed_mps": 0.0, "travel_m": 0.0,
                             "max_lateral_m": 0.0, "stopped_after_s": None, "started_at": now}
                    state["phase"] = "pulse"
                    send(snapshot, candidate)  # forwarded in this frame's reply only
                else:
                    send(snapshot, 0.0)
            elif phase == "pulse":
                send(snapshot, 0.0)  # next frame: back to zero (brakes)
                pulse["end_telemetry_seq"], pulse["end_sim"] = snapshot.telemetry_seq, sim
                state["phase"], stopped_at = "rest", None
            elif phase == "rest":
                send(snapshot, 0.0)
                dx, dy = x - pulse["start"][0], y - pulse["start"][1]
                heading = pulse["start"][2]
                pulse["travel_m"] = max(pulse["travel_m"], math.cos(heading) * dx + math.sin(heading) * dy)
                pulse["max_lateral_m"] = max(pulse["max_lateral_m"], abs(-math.sin(heading) * dx + math.cos(heading) * dy))
                pulse["peak_speed_mps"] = max(pulse["peak_speed_mps"], speed)
                if speed > M1_SPEED_CAP_MPS or pulse["travel_m"] > M1_TRAVEL_CAP_M:
                    pulse["final"] = [x, y, yaw]
                    state["pulses"].append({k: v for k, v in pulse.items() if k != "started_at"})
                    state.update(phase="aborted", abort="cap exceeded at throttle %s" % pulse["throttle"])
                    phase_start = now
                    checkpoint()
                    continue
                if speed < M1_STOP_SPEED_MPS and stopped_at is None:
                    stopped_at = sim
                    pulse["stopped_after_s"] = sim - pulse["end_sim"]
                elif speed >= M1_STOP_SPEED_MPS:
                    stopped_at = None
                if now - pulse["started_at"] >= M1_REST_S and stopped_at is not None:
                    pulse["final"] = [x, y, yaw]
                    state["pulses"].append({k: v for k, v in pulse.items() if k != "started_at"})
                    state["phase"] = "ready"
                    if pulse["peak_speed_mps"] > M1_SPEED_CAP_MPS or pulse["travel_m"] > M1_TRAVEL_CAP_M:
                        state.update(phase="aborted", abort="cap exceeded at throttle %s" % pulse["throttle"])
                        phase_start = now
            elif phase == "finish":
                if now - phase_start >= 4.0:
                    state["phase"] = "done"
            elif phase == "aborted":
                if now - phase_start < 1.0:
                    send(snapshot, 0.0)
                elif now - phase_start >= 5.0:
                    state["phase"] = "aborted-done"
            checkpoint()
    finally:
        bridge.close()
        sock.close()
        state["completed"] = True
        checkpoint()
        log.close()
        frames_log.close()


def endpoint_free():
    try:
        with socket.socket() as connection:
            connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            connection.bind(("127.0.0.1", 4567))
        return True
    except OSError:
        return False


def analyze(args):
    """Read retained trial evidence; never launch a process or decide stage acceptance."""
    import base64
    from io import BytesIO
    import numpy as np
    from PIL import Image

    output = args.analysis_output
    if output is None or output.exists() or not (args.results / "result.json").is_file():
        raise ValueError("Analyze requires completed attempt evidence and a fresh --analysis-output")
    if args.plot_directory is not None:
        args.plot_directory.mkdir(parents=True, exist_ok=False)

    def rows(path):
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]

    def intervals(times):
        if len(times) < 2:
            return {"count": len(times), "receipt_rate_hz": None}
        times = np.asarray(times, dtype=np.int64)
        delta = np.diff(times) / 1e6
        if (delta <= 0).any():
            raise ValueError("Non-increasing receipt times in retained evidence")
        span = (int(times[-1]) - int(times[0])) / 1e9
        return {"count": len(times), "receipt_span_seconds": span,
                "receipt_rate_hz": (len(times) - 1) / span,
                "interval_ms_p50_p95_p99_max": [float(x) for x in np.percentile(delta, [50, 95, 99, 100])]}

    attempt = read(args.results / "result.json")
    reports = []
    for directory in sorted(args.results.glob("run-*")):
        if not directory.is_dir():
            continue
        run = read(directory / "run.json")
        bridge_state = read(directory / "bridge-status.json")
        observer_state = read(directory / "observer-status.json")
        frames = rows(directory / "bridge-frames.jsonl")
        messages = rows(directory / "ros-messages.jsonl")
        resource_rows = rows(directory / "resources.jsonl")
        by_topic = {name: [row for row in messages if row["topic"] == name] for name in TOPICS}
        topic_metrics = {name: intervals([m["received_monotonic_ns"] for m in values])
                         for name, values in by_topic.items()}
        resources = {}
        for label in sorted({row["label"] for row in resource_rows}):
            samples = [row for row in resource_rows if row["label"] == label]
            first, last = samples[0], samples[-1]
            span = (last["monotonic_ns"] - first["monotonic_ns"]) / 1e9
            cpu = sum(last[k] - first[k] for k in ("user_cpu_seconds", "system_cpu_seconds"))
            resources[label] = {"samples": len(samples), "sampled_seconds": span,
                                "cpu_seconds_delta": cpu,
                                "mean_cpu_percent_one_core": 100 * cpu / span if span > 0 else None,
                                "max_sampled_rss_kib": max(int(r["VmRSS"].split()[0]) for r in samples),
                                "max_reported_hwm_kib": max(int(r["VmHWM"].split()[0]) for r in samples)}
        first_content = None
        raw_path = directory / "first-raw-frame.json"
        if raw_path.exists():
            raw = read(raw_path)
            scan = np.asarray([float(x) for x in raw["V1 LIDAR Range Array"].split()], dtype="<f4")
            scan_hash = hashlib.sha256(scan.tobytes()).hexdigest()
            with Image.open(BytesIO(base64.b64decode(raw["V1 Front Camera Image"]))) as camera:
                pixels = np.asarray(camera)
                pixel_hash = hashlib.sha256(pixels.tobytes()).hexdigest()
                first_content = {"scan_count": len(scan), "finite_ranges": int(np.isfinite(scan).sum()),
                    "scan_float32_sha256": scan_hash,
                    "matching_ros_scans": sum(m["range_sha256"] == scan_hash for m in by_topic["lidar"]),
                    "camera_size": list(camera.size), "camera_mode": camera.mode,
                    "camera_pixel_sha256": pixel_hash,
                    "matching_ros_images": sum(m["data_sha256"] == pixel_hash for m in by_topic["front_camera"])}
        start = run.get("observation_start_ns")
        coverage = {name: (observer_state.get("last_received_ns", {}).get(name, start) - start) / 1e9
                    for name in TOPICS} if start else None
        kinematics = None
        if run.get("kinematics_enabled"):
            from autodrive_kinematics import analyze_trace
            kinematics = analyze_trace(directory / "kinematics", start,
                run.get("diagnostic_deadline_ns", run.get("observation_end_ns")), frames,
                args.plot_directory / directory.name if args.plot_directory else None)
        contacts = None
        if run.get("contact_mode") and run.get("completed_diagnostic_window"):
            from autodrive_contacts import analyze_contacts
            contacts = analyze_contacts(directory / "kinematics", run, kinematics)
        pose = None
        if run.get("pose_trace_enabled"):
            from autodrive_pose import analyze_pose
            pose = analyze_pose(directory / "kinematics", run)
        provenance = None
        if run.get("provenance"):
            from autodrive_provenance import summarize
            provenance = summarize(frames, messages, run.get("freeze_test"))
        guard = None
        if run.get("guard") and (directory / "guard/guard-trace.jsonl").exists():
            from autodrive_guard import analyze_trace, cross_check, read_trace
            trace_path = directory / "guard/guard-trace.jsonl"
            scenario = bridge_state.get("guard", {})
            guard = {"trace": analyze_trace(trace_path), "driver": scenario,
                     "driver_events_missing_from_trace": cross_check(scenario.get("phases", []), read_trace(trace_path)[1]),
                     "actions": run.get("guard_actions"), "devkit_loss": run.get("devkit_loss"),
                     "frames_with_acknowledgements": sum("guard" in f for f in frames)}
        reports.append({"run": directory.name, "completed_observation": run.get("completed_observation", False),
            "provenance": provenance, "guard": guard,
            "profile": run.get("profile", profile_record("p0")),
            "completed_diagnostic_window": run.get("completed_diagnostic_window", False),
            "observation_start_ns": run.get("observation_start_ns"),
            "observation_end_ns": run.get("observation_end_ns"),
            "diagnostic_deadline_ns": run.get("diagnostic_deadline_ns"),
            "kinematics_enabled": run.get("kinematics_enabled", False),
            "kinematics_final": run.get("kinematics_final"),
            "kinematics_analysis": kinematics,
            "pose_trace_enabled": run.get("pose_trace_enabled", False), "pose_analysis": pose,
            "contact_mode": run.get("contact_mode"), "contact_target": run.get("contact_target", "proto-track"), "contact_analysis": contacts,
            "player_identity": run.get("player_identity"),
            "error": run.get("error"), "wall_seconds": run.get("wall_seconds"),
            "startup_to_observation_seconds": run.get("startup_to_observation_seconds"),
            "cleanup_seconds": run.get("cleanup_seconds"), "children": run.get("children"),
            "endpoint_released": run.get("endpoint_released"), "mode_review": run.get("manual_mode_review"),
            "bridge_status": bridge_state, "observer_status": observer_state,
            "bridge_receipts": intervals([f["received_monotonic_ns"] for f in frames]),
            "topic_receipts": topic_metrics, "topic_seconds_after_observation_start": coverage,
            "max_reported_displacement_m": max((f["position_displacement_m"] for f in frames), default=None),
            "movement_rejections": [f for f in frames if f.get("unexpected_movement_fields")],
            "reported_scan_rates": sorted({f["reported_scan_rate"] for f in frames}),
            "scan_lengths": sorted({f["range_count"] for f in frames}),
            "publisher_counts": sorted({f["publisher_count"] for f in frames if "publisher_count" in f}),
            "image_formats": [json.loads(s) for s in sorted({json.dumps({k:m[k] for k in
                ("width", "height", "step", "encoding", "byte_count")}, sort_keys=True)
                for m in by_topic["front_camera"]})],
            "first_content": first_content, "resources": resources,
            "recorded_message_counts": dict(Counter(m["topic"] for m in messages))})
    result = {"stage": "SIM0", "attempt": attempt, "runs": reports, "results_path": str(args.results),
              "analysis_tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "limits": ["Analysis only; stage acceptance still requires diagnostic, configuration, content and cleanup review",
                         "Receipt timing is not acquisition timing; stock protocol has no source acquisition identity",
                         "CPU/RSS samples cover the three owned process IDs, not GPU memory or the whole host",
                         "Reported displacement uses stock rounded telemetry and is not a stopping measurement"],
              "source_sha256": {str(p.relative_to(args.results)): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(args.results.rglob("*"))
                                if p.is_file() and p.suffix in {".json", ".jsonl", ".request"}}}
    save(output, result)
    if args.contact_gate_output:
        from autodrive_contacts import make_gate
        if args.contact_gate_output.exists():
            raise ValueError("Contact gate output must be fresh")
        save(args.contact_gate_output, make_gate(result, output))
    print(json.dumps({"runs_analyzed": len(reports), "completed_observations":
                      sum(r["completed_observation"] for r in reports),
                      "completed_diagnostic_windows": sum(r["completed_diagnostic_window"] for r in reports),
                      "output": str(output)}))


def trial(args, context, out):
    from Xlib import X, display
    from Xlib.ext import xtest
    from Xlib.protocol import event
    from PIL import Image
    from autodrive_build import process_sample

    out.mkdir()
    here = Path(context["scratch"])
    environment = dict(os.environ, **context["environment"], ROS_DOMAIN_ID="87", ROS_LOCALHOST_ONLY="1")
    bridge_environment = dict(environment,
        PYTHONPATH=str(here / "compat") + ":" + str(here / "install/lib/python3.10/site-packages") + ":" + environment.get("PYTHONPATH", ""),
        AMENT_PREFIX_PATH=str(here / "install") + ":" + environment.get("AMENT_PREFIX_PATH", ""))
    children, connection = [], None
    started = time.monotonic()
    record = {"started_utc": datetime.now(timezone.utc).isoformat(), "scope": "SIM0 stationary only",
              "profile": profile_record(args.profile), "completed_diagnostic_window": False,
              "kinematics_enabled": args.kinematics_probe,
              "pose_trace_enabled": args.pose_trace,
              "contact_mode": args.contact_mode, "contact_target": args.contact_target or "proto-track", "player_identity": args.player_identity,
              "requested_seconds_after_first_complete_observation": args.duration,
              "startup_timeout_seconds": args.startup_timeout, "children": [], "actions": [],
              "environment_overrides": dict(context["environment"], ROS_DOMAIN_ID="87", ROS_LOCALHOST_ONLY="1"),
              "source_acquisition_identity_available": args.provenance, "completed_observation": False,
              "provenance": args.provenance, "freeze_test": args.freeze_test,
              "freeze_window_seconds_after_first_frame": args.freeze_window if args.freeze_test else None,
              "guard": args.guard, "guard_actions": [], "plugin_observer": args.plugin_observer,
              "plugin_stack": args.plugin_stack}
    heartbeat = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    heartbeat.setblocking(False)
    heartbeat_seq = 0

    def checkpoint():
        save(out / "run.json", record)

    def spawn(label, argv, env):
        log = (out / (label + ".log")).open("w")
        process = subprocess.Popen(argv, cwd=here, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   stdin=subprocess.DEVNULL, start_new_session=True)
        entry = {"label": label, "argv": argv, "pid": process.pid, "started_ns": time.monotonic_ns()}
        children.append((process, log, entry))
        record["children"].append(entry)
        checkpoint()
        return process

    try:
        if not endpoint_free():
            raise RuntimeError("Endpoint 4567 is occupied; no existing listener was stopped")
        import configparser
        config = configparser.ConfigParser()
        config.read(here / "install/share/autodrive_f1tenth/api_config.ini")
        if any(config.getfloat("f1tenth_1", key) != 0 for key in ("throttle_command", "steering_command")):
            raise RuntimeError("Existing qualified Devkit command configuration is not zero")
        own_script = str(Path(__file__).resolve())
        sim1 = ["--provenance"] if args.provenance else []
        if args.freeze_test:
            sim1 += ["--freeze-test", args.freeze_test, "--freeze-window", ",".join(map(str, args.freeze_window))]
        if args.guard:
            sim1 += ["--guard", args.guard, "--duration", str(args.duration)]
        if args.motion_stage:
            sim1 += ["--motion-stage", args.motion_stage]
        bridge_process = spawn("bridge", [context["devkit_python"], "-B", own_script, "bridge", "--results", str(out),
                         "--reply-delay", str(args.reply_delay), "--profile", args.profile, *sim1], bridge_environment)
        supervisors = []

        supervisor_name = f"roboracer-supervisor-{os.getpid()}"
        plugin_environment = None
        if args.plugin_observer or args.plugin_stack or args.motion_stage:
            isolated = out / "plugin-avlite"
            plugin_environment = dict(environment, PYTHONNOUSERSITE="1", MPLCONFIGDIR=str(isolated / "mpl"),
                                      **{name: str(isolated / name.lower()) for name in (
                                          "AVLITE_CONFIG_DIR", "AVLITE_PLUGINS_DIR", "AVLITE_DATA_DIR",
                                          "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")})

        def spawn_supervisor():
            if args.plugin_stack or args.motion_stage:
                # S1: the real supervisor (its own process) owns the command path; the AVLite
                # stack or, in a confirmed motion stage, the calibration source (another process)
                # sends its requests there.
                stage = ["--stage", args.motion_stage, "--confirmation", str(MOTION_APPROVAL)] if args.motion_stage else []
                spawn("supervisor-1", [context["avlite_python"], "-B", "-m", "roboracer.runtime.supervisor_process",
                    "--name", supervisor_name, "--target", read(out / "bridge-status.json")["guard_socket"],
                    "--origin", "sup-1", "--status", str(out / "supervisor-1-status.json"),
                    "--trace", str(out / "supervisor-trace.jsonl"), *stage],
                    dict(plugin_environment, PYTHONPATH=str(PLUGIN_DIRECTORY.parent)))
                deadline = time.monotonic() + 30
                while not read(out / "supervisor-1-status.json").get("ready"):
                    if any(p.poll() is not None for p, _, _ in children) or time.monotonic() > deadline:
                        raise RuntimeError("Supervisor startup failed")
                    time.sleep(0.1)
                if args.motion_stage:
                    spawn("calibration", [context["avlite_python"], "-B", own_script, "calibrate",
                                          "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                          "--supervisor", supervisor_name, "--motion-stage", args.motion_stage],
                          plugin_environment)
                    status_name = "calibration-status.json"
                else:
                    spawn("plugin-stack", [context["avlite_python"], "-B", own_script, "plugin-observe",
                                           "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                           "--supervisor", supervisor_name], plugin_environment)
                    status_name = "plugin-observer-status.json"
                while not read(out / status_name).get("ready"):
                    if any(p.poll() is not None for p, _, _ in children) or time.monotonic() > deadline:
                        raise RuntimeError("Request source startup failed")
                    time.sleep(0.1)
                return
            # The request source is its own OS process, separate from the bridge and this runner.
            index = len(supervisors) + 1
            supervisors.append(spawn(f"supervisor-{index}", [sys.executable, "-B",
                str(Path(__file__).resolve().with_name("autodrive_guard.py")), "supervise",
                "--target", read(out / "bridge-status.json")["guard_socket"], "--origin", f"sup-{index}",
                "--status", str(out / f"supervisor-{index}-status.json")], environment))
        spawn("observer", [context["avlite_python"], "-B", own_script, "observe", "--results", str(out),
                           *(["--provenance"] if args.provenance else [])], environment)
        ready_files = ["bridge-status.json", "observer-status.json"]
        if args.plugin_observer:
            spawn("plugin-observer", [context["avlite_python"], "-B", own_script, "plugin-observe",
                                      "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY)], plugin_environment)
            ready_files.append("plugin-observer-status.json")
        deadline = time.monotonic() + 15
        while not all(read(out / name).get("ready") for name in ready_files):
            if any(p.poll() is not None for p, _, _ in children) or time.monotonic() > deadline:
                raise RuntimeError("Bridge/observer startup failed")
            time.sleep(0.1)
        if args.guard:
            spawn_supervisor()
        player_args = [str(args.player), "-screen-fullscreen", "0", "-screen-width", "1280",
                       "-screen-height", "720", "-logFile", str(out / "player-unity.log")]
        if args.kinematics_probe:
            (out / "kinematics").mkdir()
            player_args += ["-roboracerKinematics", str(out / "kinematics")]
        if args.contact_mode:
            player_args += ["-roboracerContacts", args.contact_mode, "-roboracerContactTarget", args.contact_target or "proto-track"]
        if args.pose_trace:
            player_args += ["-roboracerPoseTrace"]
        if args.freeze_test:
            player_args += ["-roboracerTestHooks"]
        if args.guard:
            # The interlock stays on unless a confirmed motion stage runs (M0 only, per the
            # approval record); only then is -roboracerMotionAuthorized passed.
            (out / "guard").mkdir()
            player_args += ["-roboracerGuard", "-roboracerGuardTrace", str(out / "guard")]
            if args.motion_stage:
                player_args += ["-roboracerMotionAuthorized"]
        player = spawn("player", player_args, environment)
        player_started = time.monotonic()
        connection = display.Display()
        root = connection.screen().root
        pid_atom = connection.intern_atom("_NET_WM_PID")

        def owned_window(window, depth=0):
            try:
                value = window.get_full_property(pid_atom, X.AnyPropertyType)
                if value is not None and len(value.value) and int(value.value[0]) == player.pid:
                    return window
                if depth < 3:
                    for child in window.query_tree().children:
                        found = owned_window(child, depth + 1)
                        if found is not None:
                            return found
            except Exception:
                return None
            return None

        def capture(window, label):
            geometry = window.get_geometry()
            if (geometry.width, geometry.height) != (1280, 720):
                raise RuntimeError("Unexpected owned-window geometry")
            pixels = window.get_image(0, 0, 1280, 720, X.ZPixmap, 0xffffffff)
            Image.frombytes("RGB", (1280, 720), pixels.data, "raw", "BGRX").save(out / (label + ".png"))

        def target_window(window, x, y):
            """Activate, raise and focus the owned window, then point at (x, y) inside it."""
            active_atom = connection.intern_atom("_NET_ACTIVE_WINDOW")
            root.send_event(event.ClientMessage(window=window.id, client_type=active_atom,
                data=(32, [2, X.CurrentTime, 0, 0, 0])),
                event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
            connection.sync()
            time.sleep(0.5)
            frame = window
            while frame.query_tree().parent.id != root.id:
                frame = frame.query_tree().parent
            frame.configure(stack_mode=X.Above)
            window.configure(stack_mode=X.Above)
            window.set_input_focus(X.RevertToParent, X.CurrentTime)
            window.warp_pointer(x, y)
            connection.sync()
            time.sleep(0.2)
            local = window.query_pointer()
            if connection.get_input_focus().focus != window or (local.win_x, local.win_y) != (x, y):
                raise RuntimeError("Guard input is not targeting the reviewed owned window")

        def guard_action(kind, window, approval):
            now = time.monotonic_ns()
            if kind == "kill-supervisor":
                process = supervisors[-1]
                entry = next(e for p, _, e in children if p is process)
                entry["expected_kill"] = True
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                return {"killed_pid": process.pid, "monotonic_ns": now}
            if kind == "spawn-supervisor":
                spawn_supervisor()
                return {"spawned_pid": supervisors[-1].pid, "monotonic_ns": now}
            if kind == "manual-input":
                # Keyboard drive input and a GUI mode-toggle click against the guarded player.
                from Xlib import XK
                if window is None:
                    raise RuntimeError("Owned player window unavailable for the manual-bypass probe")
                pointer, previous = root.query_pointer(), connection.get_input_focus().focus
                x, y = approval["mode_xy"]
                target_window(window, x, y)
                keycode = connection.keysym_to_keycode(XK.string_to_keysym("Up"))
                capture(window, "ui-before-manual")
                xtest.fake_input(connection, X.KeyPress, keycode)
                connection.sync()
                time.sleep(1.0)
                xtest.fake_input(connection, X.KeyRelease, keycode)
                connection.sync()
                time.sleep(0.2)
                # Synthetic clicks are occasionally lost by the player (see SIM0/SIM1-01 Connect retries).
                # Hover, click, and confirm the guard logged the block; at most three clicks.
                from autodrive_guard import read_trace
                clicks = []
                for _ in range(3):
                    window.warp_pointer(x + 3, y)
                    connection.sync()
                    time.sleep(0.1)
                    window.warp_pointer(x, y)
                    connection.sync()
                    time.sleep(0.3)
                    clicked = time.monotonic_ns()
                    xtest.fake_input(connection, X.ButtonPress, 1)
                    connection.sync()
                    time.sleep(0.1)
                    xtest.fake_input(connection, X.ButtonRelease, 1)
                    connection.sync()
                    time.sleep(0.5)
                    events = read_trace(out / "guard/guard-trace.jsonl", live=True)[1]
                    blocked = any(e["event"] == "blocked driving-mode" and e["mono"] >= clicked for e in events)
                    clicks.append({"monotonic_ns": clicked, "blocked_logged": blocked})
                    if blocked:
                        break
                capture(window, "ui-after-manual")
                root.warp_pointer(pointer.root_x, pointer.root_y)
                if hasattr(previous, "set_input_focus"):
                    previous.set_input_focus(X.RevertToParent, X.CurrentTime)
                connection.sync()
                return {"key": "Up", "key_seconds": 1.0, "click_xy": [x, y], "clicks": clicks, "monotonic_ns": now,
                        "completed_ns": time.monotonic_ns()}
            if kind == "kill-bridge":
                entry = next(e for p, _, e in children if p is bridge_process)
                entry["expected_kill"] = True
                os.killpg(bridge_process.pid, signal.SIGKILL)
                bridge_process.wait()
                record["devkit_loss"] = {"killed_ns": time.monotonic_ns()}
                return {"killed_pid": bridge_process.pid, "monotonic_ns": now}
            raise RuntimeError("Unknown guard action " + repr(kind))

        def check_devkit_loss():
            """After the bridge is killed, read the player's own trace: whichever of disconnect or lease
            expiry clears the lease first, then 2 s of steps with nothing applied."""
            from autodrive_guard import read_trace
            loss = record["devkit_loss"]
            _, events, steps, _ = read_trace(out / "guard/guard-trace.jsonl", live=True)
            after = [e for e in events if e["mono"] >= loss["killed_ns"]]
            for key, pattern in (("expired", "state stopped lease-expired"), ("disconnect", "state disarmed disconnect")):
                hit = next((e for e in after if e["event"].startswith(pattern)), None)
                if hit and key not in loss:
                    loss[key] = {"event": hit["event"], "n": hit["n"], "after_kill_ms": (hit["mono"] - loss["killed_ns"]) / 1e6}
            cleared = min((loss[k]["after_kill_ms"] for k in ("expired", "disconnect") if k in loss), default=None)
            loss["lease_cleared_after_kill_ms"] = cleared
            later = [s for s in steps if s["mono"] >= loss["killed_ns"]]
            loss["steps_after_kill"] = len(later)
            if cleared is not None:
                cleared_ns = loss["killed_ns"] + cleared * 1e6
                loss["applied_steps_after_clear"] = sum(s["applied"] >= 0 for s in later if s["mono"] > cleared_ns)
                loss["observed_after_clear_s"] = (later[-1]["mono"] - cleared_ns) / 1e9 if later else 0
            waited = (time.monotonic_ns() - loss["killed_ns"]) / 1e9
            loss["waited_seconds"] = waited
            return (cleared is not None and loss["observed_after_clear_s"] >= 2) or waited >= args.disconnect_wait

        reviewed, connected, observation_start = False, False, None
        approval = {}
        sample_at = 0
        with (out / "resources.jsonl").open("w", buffering=1) as metrics:
            while time.monotonic() - started < args.startup_timeout + max(args.duration, args.guard_timeout) + 15:
                if any(p.poll() is not None and not e.get("expected_kill") for p, _, e in children):
                    raise RuntimeError("An owned child exited during observation")
                bridge_state, observer_state = read(out / "bridge-status.json"), read(out / "observer-status.json")
                if bridge_state.get("errors"):
                    raise RuntimeError("Bridge rejected telemetry: " + repr(bridge_state["errors"]))
                probe_ready = not args.kinematics_probe
                if args.kinematics_probe:
                    probe = read(out / "kinematics/status.json")
                    if probe and probe.get("samples", 0) and probe.get("fixed_samples", 0) and probe.get("late_samples", 0):
                        check_kinematics_status(probe, player.pid, time.monotonic_ns())
                        if args.contact_mode:
                            from autodrive_contacts import check_status
                            check_status(probe, args.contact_mode, observation_start,
                                observation_start + int(args.duration * 1e9) if observation_start else None,
                                time.monotonic_ns(), target=args.contact_target or "proto-track")
                        if args.pose_trace:
                            from autodrive_pose import check_status as check_pose_status
                            check_pose_status(probe, observation_start,
                                observation_start + int(args.duration * 1e9) if observation_start else None)
                        if "kinematics_prefix" not in record:
                            record["kinematics_prefix"] = check_kinematics_prefix(out / "kinematics", player.pid)
                            record["kinematics_first_verified_ns"] = time.monotonic_ns()
                            checkpoint()
                        probe_ready = True
                    elif probe.get("state") == "failed" or time.monotonic() - player_started > 30:
                        raise RuntimeError("Kinematics probe did not become ready: " + str(probe.get("error")))
                window = owned_window(root)
                if probe_ready and window is not None and time.monotonic() - player_started >= 12:
                    if not reviewed:
                        capture(window, "ui-before-connect")
                        record["ui_review_required"] = {"pid": player.pid, "window_id": window.id,
                            "screenshot": str(out / "ui-before-connect.png"),
                            "review_file": str(out / "ui-review.json")}
                        checkpoint()
                        reviewed = True
                    approval = read(out / "ui-review.json")
                    if not connected and approval:
                        expected_mode = "Guarded" if args.guard else "Manual"
                        if approval.get("pid") != player.pid or approval.get("window_id") != window.id or approval.get("mode") != expected_mode:
                            raise RuntimeError(f"UI review does not match this owned {expected_mode}-mode window")
                        if args.guard == "scenario" and not (isinstance(approval.get("mode_xy"), list) and
                                all(0 <= v < limit for v, limit in zip(approval["mode_xy"], (1280, 720)))):
                            raise RuntimeError("Guard scenario review must locate the driving-mode button")
                        x, y = approval["connect_xy"]
                        if not (0 <= x < 1280 and 0 <= y < 720):
                            raise RuntimeError("Connect coordinates outside the owned window")
                        screenshot = out / "ui-before-connect.png"
                        if approval.get("screenshot_sha256") != hashlib.sha256(screenshot.read_bytes()).hexdigest():
                            raise RuntimeError("UI review screenshot hash does not match this trial")
                        pointer, focus = root.query_pointer(), connection.get_input_focus().focus
                        active_atom = connection.intern_atom("_NET_ACTIVE_WINDOW")
                        root.send_event(event.ClientMessage(window=window.id, client_type=active_atom,
                            data=(32, [2, X.CurrentTime, 0, 0, 0])),
                            event_mask=X.SubstructureRedirectMask | X.SubstructureNotifyMask)
                        connection.sync()
                        time.sleep(0.5)  # Give the WM time to activate its managed client.
                        # Raise the owned client's outer WM frame as well as its child.
                        # Raising only the client can leave an unrelated window above it.
                        frame = window
                        while frame.query_tree().parent.id != root.id:
                            frame = frame.query_tree().parent
                        frame.configure(stack_mode=X.Above)
                        window.configure(stack_mode=X.Above)
                        window.set_input_focus(X.RevertToParent, X.CurrentTime)
                        window.warp_pointer(x, y)
                        connection.sync()
                        time.sleep(0.2)  # Let the owned Unity window process focus/hover.
                        under_pointer, cursor = [], root
                        for _ in range(16):
                            under_pointer.append(cursor.id)
                            child = cursor.query_pointer().child
                            if not hasattr(child, "query_pointer"):
                                break
                            cursor = child
                        current_focus = connection.get_input_focus().focus
                        local_pointer = window.query_pointer()
                        record["ui_input_target"] = {
                            "window_id": window.id, "frame_id": frame.id,
                            "pointer_window_chain": under_pointer,
                            "focus_id": getattr(current_focus, "id", current_focus),
                            "client_xy": [local_pointer.win_x, local_pointer.win_y]}
                        active = root.get_full_property(active_atom, X.AnyPropertyType)
                        record["ui_input_target"]["active_window_id"] = int(active.value[0]) if active is not None and len(active.value) else None
                        checkpoint()
                        if window.id not in under_pointer or current_focus != window or (local_pointer.win_x, local_pointer.win_y) != (x, y):
                            raise RuntimeError("Connect input is not targeting the reviewed owned window")
                        capture(window, "ui-connect-hover")
                        xtest.fake_input(connection, X.ButtonPress, 1)
                        connection.sync()
                        time.sleep(0.1)  # Keep press and release on separate rendered frames.
                        xtest.fake_input(connection, X.ButtonRelease, 1)
                        connection.sync()
                        time.sleep(0.2)
                        capture(window, "ui-after-connect")
                        root.warp_pointer(pointer.root_x, pointer.root_y)
                        if hasattr(focus, "set_input_focus"):
                            focus.set_input_focus(X.RevertToParent, X.CurrentTime)
                        connection.sync()
                        connected = True
                        record["actions"].append({"action": "Connect only", "xy": [x, y], "monotonic_ns": time.monotonic_ns()})
                        record["manual_mode_review"] = approval
                        checkpoint()
                if observation_start is None and bridge_state.get("first_complete_frame_ns") and observer_state.get("first_complete_observation_ns"):
                    observation_start = max(bridge_state["first_complete_frame_ns"], observer_state["first_complete_observation_ns"])
                    record["observation_start_ns"] = observation_start
                    record["startup_to_observation_seconds"] = (observation_start - record["children"][-1]["started_ns"]) / 1e9
                    if args.contact_mode:
                        from autodrive_contacts import write_window_request
                        record["contact_window_request"] = write_window_request(out / "kinematics", player.pid,
                            args.contact_mode, observation_start, observation_start + int(args.duration * 1e9), target=args.contact_target or "proto-track")
                        record["contact_request_sent_ns"] = time.monotonic_ns()
                    checkpoint()
                if observation_start is None and time.monotonic() - started > args.startup_timeout:
                    raise TimeoutError("No complete stationary observation within startup bound")
                if args.guard:
                    action = bridge_state.get("action")
                    done = read(out / "actions-done.json")
                    if action and str(action["id"]) not in done and "devkit_loss" not in record:
                        result = guard_action(action["kind"], window, approval)
                        record["guard_actions"].append(dict(action, **result))
                        if action["kind"] != "kill-bridge":
                            save(out / "actions-done.json", dict(done, **{str(action["id"]): result}))
                        checkpoint()
                    if "devkit_loss" in record and check_devkit_loss():
                        record.update(completed_observation=True, observation_end_ns=time.monotonic_ns(),
                                      bridge_at_end=bridge_state, observer_at_end=observer_state)
                        if window is not None:
                            capture(window, "ui-completed")
                        break
                    # Observe and calibration trials end when the bridge-side driver completes
                    # (calibration: after its final checks and disarm; M0 attempt 2 waited for the timeout).
                    if args.guard in ("observe", "calibration") and bridge_state.get("guard", {}).get("complete"):
                        if window is not None:
                            capture(window, "ui-completed")
                        record.update(completed_observation=True, observation_end_ns=time.monotonic_ns(),
                                      bridge_at_end=bridge_state, observer_at_end=observer_state)
                        break
                    if time.monotonic() - started > args.startup_timeout + args.guard_timeout:
                        raise TimeoutError("Guard trial did not complete within its bound")
                target = observation_start + int(args.duration * 1e9) if observation_start else None
                if target and args.profile == "drift-diagnostic" and time.monotonic_ns() >= target:
                    record.update(completed_diagnostic_window=True, diagnostic_deadline_ns=target,
                                  observation_end_ns=time.monotonic_ns(),
                                  bridge_at_end=bridge_state, observer_at_end=observer_state)
                    if window is not None:
                        capture(window, "ui-completed")
                    break  # End by wall time, including stalled streams; analyze their coverage separately.
                if target and not args.guard and args.profile in ("p0", "p0-creep") and bridge_state.get("last_received_ns", 0) >= target and all(observer_state.get("last_received_ns", {}).get(t, 0) >= target for t in TOPICS):
                    if window is not None:
                        capture(window, "ui-completed")
                    record.update(completed_observation=True, observation_end_ns=time.monotonic_ns(),
                                  bridge_at_end=bridge_state, observer_at_end=observer_state)
                    break
                if time.monotonic() >= sample_at:
                    for process, _, entry in children:
                        sample = process_sample(process.pid)
                        if sample:
                            metrics.write(json.dumps(dict(label=entry["label"], **sample)) + "\n")
                    sample_at = time.monotonic() + 1
                if (args.plugin_stack or args.motion_stage) and connected:
                    # Runner liveness for the supervisor's lease, from this loop only (after the
                    # Connect sequence, whose ~1 s of input handling would otherwise trip it).
                    heartbeat_seq += 1
                    try:
                        heartbeat.sendto(json.dumps({"kind": "heartbeat", "seq": heartbeat_seq}).encode(),
                                         "\0" + supervisor_name)
                    except (BlockingIOError, ConnectionRefusedError, FileNotFoundError):
                        record["heartbeat_failures"] = record.get("heartbeat_failures", 0) + 1
                time.sleep(0.1)
        if not (record["completed_observation"] or record["completed_diagnostic_window"]):
            raise TimeoutError("Stationary observation did not complete in its execution bound")
    except BaseException as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        cleanup_started = time.monotonic()
        if connection is not None:
            connection.close()
        heartbeat.close()
        for process, log, entry in reversed(children):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                entry["termination"] = "SIGTERM owned process group"
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    entry["termination"] = "SIGKILL after bounded SIGTERM"
            entry.update(exit_code=process.returncode, reaped=True, completed_ns=time.monotonic_ns())
            log.close()
        record.update(cleanup_seconds=time.monotonic() - cleanup_started, wall_seconds=time.monotonic() - started,
                      endpoint_released=endpoint_free(), completed_utc=datetime.now(timezone.utc).isoformat())
        if args.kinematics_probe:
            record["kinematics_final"] = read(out / "kinematics/status.json")
        checkpoint()
    if not record["endpoint_released"] or any(e["exit_code"] != 0 and not e.get("expected_kill") for e in record["children"]):
        raise RuntimeError("Owned-process cleanup requires review")
    if args.kinematics_probe:
        check_kinematics_status(record["kinematics_final"], player.pid, time.monotonic_ns(), closed=True)
        if args.contact_mode:
            from autodrive_contacts import check_status
            check_status(record["kinematics_final"], args.contact_mode, record["observation_start_ns"],
                record["diagnostic_deadline_ns"], time.monotonic_ns(), closed=True, target=args.contact_target or "proto-track")
        if args.pose_trace:
            from autodrive_pose import check_status as check_pose_status
            check_pose_status(record["kinematics_final"],record["observation_start_ns"],record["diagnostic_deadline_ns"],closed=True)
            # Validate the binary before allowing the next fresh run in this invocation.
            from autodrive_pose import analyze_pose
            save(out / "pose-validation.json", analyze_pose(out / "kinematics", record))
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "bridge", "observe", "plugin-observe", "calibrate", "analyze"))
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--player", type=Path)
    parser.add_argument("--runs", type=int, default=2)
    parser.add_argument("--duration", type=float, default=60)
    parser.add_argument("--startup-timeout", type=float, default=180)
    parser.add_argument("--reply-delay", type=float, default=0.1)
    parser.add_argument("--profile", choices=PROFILES, default="p0",
                        help="p0 keeps the original any-position-change stop; drift-diagnostic is the approved 10 mm diagnostic only")
    parser.add_argument("--kinematics-probe", action="store_true",
                        help="Enable and supervise the approved source-player read-only diagnostic; requires drift-diagnostic")
    parser.add_argument("--pose-trace", action="store_true",
                        help="Approved statement-level tracing: Floor control, at most two 10-second windows")
    parser.add_argument("--contact-mode", choices=("control", "treatment"),
                        help="Explicit contact A/B diagnostic; requires kinematics, treatment also requires verified controls")
    parser.add_argument("--provenance", action="store_true",
                        help="SIM1: validate roboracer.sim1/1 provenance, restamp headers, publish provenance topic")
    parser.add_argument("--freeze-test", choices=("lidar", "ips"),
                        help="SIM1-01 P1a: launch with test hooks and freeze one source in --freeze-window")
    parser.add_argument("--freeze-window", default="10,15",
                        type=lambda text: tuple(float(v) for v in text.split(",")),
                        help="Freeze start,end seconds after the bridge's first frame")
    parser.add_argument("--guard", choices=("observe", "scenario", "calibration"),
                        help="SIM1-02: launch the guarded interlocked player with a supervisor stand-in; "
                             "observe forwards zero requests for --duration, scenario runs the disarmed P1a cases; "
                             "calibration forwards a confirmed motion stage's requests (requires --motion-stage)")
    parser.add_argument("--motion-stage", choices=sorted(MOTION_STAGES),
                        help="Confirmed motion-protocol stage (v0.1: m0 only, steering with throttle 0). Passes "
                             "-roboracerMotionAuthorized; requires the approval record and a SIM1-03 build record")
    parser.add_argument("--build-record", type=Path,
                        help="build-result.json of the player (motion stages: must include vendor-sim1-03)")
    parser.add_argument("--plugin-observer", action="store_true",
                        help="S1-02: also run the RoboRacer plugin's AutoDriveBridge as a read-only subscriber")
    parser.add_argument("--plugin-stack", action="store_true",
                        help="S1: run AVLite (HoldController) through the plugin bridge and the real supervisor "
                             "instead of the stand-in; exact-zero requests, interlocked guard")
    parser.add_argument("--plugin", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--supervisor", default=None, help=argparse.SUPPRESS)
    parser.add_argument("--guard-timeout", type=float, default=420,
                        help="Execution bound for a guard trial after startup")
    parser.add_argument("--disconnect-wait", type=float, default=30,
                        help="Seconds to wait for the player's disconnect after the Devkit-loss kill")
    parser.add_argument("--contact-target", choices=("proto-track", "floor"), help="Explicit collision surface and approved inertia policy")
    parser.add_argument("--control-evidence", type=Path, help="Verified control gate JSON, mandatory for treatment")
    parser.add_argument("--contact-gate-output", type=Path, help="Fresh contact gate JSON for analyze mode")
    parser.add_argument("--analysis-output", type=Path,
                        help="Fresh JSON output for read-only retained-trial analysis")
    parser.add_argument("--plot-directory", type=Path,
                        help="Fresh output directory for offline kinematics plots in analyze mode")
    args = parser.parse_args()
    args.results = args.results.resolve()
    if args.runs < 1 or not all(math.isfinite(v) and v > 0 for v in (args.duration, args.startup_timeout, args.reply_delay)):
        parser.error("Positive finite bounds are required")
    if args.profile == "drift-diagnostic" and (args.runs > 2 or args.duration > 60):
        parser.error("Approved diagnostic bounds are at most two runs per player and 60 seconds per window")
    if args.kinematics_probe and (args.profile != "drift-diagnostic" or args.mode != "run"):
        parser.error("Kinematics probe requires run mode and the diagnostic-only profile")
    if args.contact_mode and (not args.kinematics_probe or args.mode != "run"):
        parser.error("Contact mode requires explicit kinematics diagnostic run")
    if (args.provenance or args.freeze_test) and args.mode in ("run", "bridge") and (
            args.profile != "p0-creep" or args.kinematics_probe):
        parser.error("SIM1 provenance runs use the amended neutral p0-creep profile without diagnostic probes")
    if args.freeze_test and not args.provenance:
        parser.error("Freeze tests require --provenance")
    if args.guard and (not args.provenance or args.freeze_test or
                       not all(math.isfinite(v) and v > 0 for v in (args.guard_timeout, args.disconnect_wait))):
        parser.error("Guard trials require --provenance, no freeze test, and positive finite bounds")
    if args.freeze_test and not (len(args.freeze_window) == 2 and 0 < args.freeze_window[0] < args.freeze_window[1]
                                 and args.freeze_window[1] + 5 <= args.duration):
        parser.error("Freeze window must be ordered and end at least 5 s before the observation ends")
    if args.plugin_stack and (args.guard != "observe" or args.plugin_observer):
        parser.error("The plugin stack runs only with --guard observe and replaces --plugin-observer")
    if args.plugin_observer and not args.provenance:
        parser.error("The plugin observer needs the provenance topic (--provenance)")
    if (args.guard == "calibration") != bool(args.motion_stage) and args.mode == "run":
        parser.error("--guard calibration and --motion-stage go together")
    if args.motion_stage and args.mode == "run":
        if args.plugin_stack or args.plugin_observer or args.reply_delay > 0.05:
            parser.error("Motion stages run the calibration source alone with reply pacing <= 50 ms (D3)")
        approval = read(MOTION_APPROVAL)
        if approval.get("version") != "0.1" or args.motion_stage.upper() not in approval.get("stages", []):
            parser.error(f"Stage {args.motion_stage} is not confirmed in {MOTION_APPROVAL}")
        build = read(args.build_record) if args.build_record else {}
        argv = build.get("argv", [])
        built = argv[argv.index("-buildLinux64Player") + 1] if "-buildLinux64Player" in argv else None
        if build.get("exit_code") != 0 or build.get("sim1_patch", {}).get("through", "") < "03" or \
                not args.player or built != str(args.player.resolve()):
            parser.error("Motion stages need the player's own build record with vendor-sim1-03 (D1)")
        library = args.player.resolve().parent / "GameAssembly.so"
        if hashlib.sha256(library.read_bytes()).hexdigest() != build["output_files"].get("GameAssembly.so", {}).get("sha256"):
            parser.error("Player GameAssembly.so differs from its build record")
    if args.contact_target and not args.contact_mode:
        parser.error("Contact target requires contact mode")
    if args.pose_trace and (not args.kinematics_probe or args.mode!="run" or args.contact_mode!="control" or
                           args.contact_target!="floor" or args.duration>10 or args.runs>2 or args.startup_timeout>180):
        parser.error("Pose tracing requires Floor control and the approved two-run/10-second/180-second startup bounds")
    if (args.contact_mode == "treatment") != bool(args.control_evidence):
        parser.error("Control evidence is required only for contact treatment")
    if args.contact_gate_output and args.mode != "analyze":
        parser.error("Contact gate output requires analyze mode")
    os.umask(0o077)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    if args.mode == "analyze":
        return analyze(args)
    if args.mode == "bridge":
        return bridge(args)
    if args.mode == "observe":
        return observe(args)
    if args.mode == "plugin-observe":
        return plugin_observe(args)
    if args.mode == "calibrate":
        return calibrate(args)
    if not args.context or not args.player or not args.player.is_file() or args.results.exists():
        parser.error("Run mode needs an existing player/context and fresh results path")
    args.player = args.player.resolve()
    args.player_identity = None
    gate = None
    if args.contact_mode:
        from autodrive_contacts import player_identity, verify_gate
        args.player_identity = player_identity(args.player)
        if args.contact_mode == "treatment":
            gate = verify_gate(args.control_evidence, args.player, args.contact_target or "proto-track")
    args.results.mkdir(parents=True)
    context = json.loads(args.context.read_text())

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Signal {signum}; clean up owned children")

    signal.signal(signal.SIGTERM, interrupted)
    result = {"stage": "SIM1" if args.provenance else "SIM0", "runs_requested": args.runs, "duration_requested": args.duration,
              "profile": profile_record(args.profile),
              "kinematics_enabled": args.kinematics_probe,
              "pose_trace_enabled": args.pose_trace,
              "contact_mode": args.contact_mode, "contact_target": args.contact_target or "proto-track", "player_identity": args.player_identity,
              "control_gate": gate,
              "tool_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "context_sha256": hashlib.sha256(args.context.read_bytes()).hexdigest(), "completed_runs": []}
    try:
        for index in range(1, args.runs + 1):
            trial(args, context, args.results / f"run-{index:02d}")
            result["completed_runs"].append(index)
            save(args.results / "result.json", result)
    except BaseException as exc:
        result["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        result["acceptance"] = ("Diagnostic only; cannot pass P0 or SIM0 acceptance"
                                if args.profile == "drift-diagnostic" else
                                "Pending telemetry, diagnostic, source/config and cleanup review")
        save(args.results / "result.json", result)
    print(json.dumps(result))


if __name__ == "__main__":
    main()
