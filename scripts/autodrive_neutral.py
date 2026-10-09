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
                 "m1": {"throttle": (0.0, 0.002, 0.005, 0.01, 0.02), "steering": (0.0,)},
                 "m2": {"throttle": (0.0, 0.01), "steering": (0.0,)},
                 "m3": {"throttle": (0.0, 0.005, 0.01, 0.02), "steering": (0.0,)},
                 "m3b": {"throttle": (0.0, 0.03, 0.045, 0.06), "steering": (0.0,)}}
# S1-03 AVLite motion stages (proposal v0.2; mirrors supervisor_core.AVLITE_STAGES and
# SpeedLoopParams.u_max): continuous normalized ranges instead of discrete values.
AVLITE_MOTION_STAGES = {"m4": {"throttle_max": 0.07, "steering_max": 0.0, "steer_feedback_rad": 0.0,
                               "containment_m": 3.0},
                        "m5": {"throttle_max": 0.07, "steering_max": round(0.35 / 0.5235987755982988, 6),
                               "steer_feedback_rad": 0.3505, "containment_m": 7.0},
                        # S1-05 lap proposal v0.1 (D10, approved "approve D9, D10, D11; run M6"): M5 limits;
                        # a lap returns to the start, so containment is the qualified C0 wall extent + 0.3 m.
                        "m6": {"throttle_max": 0.07, "steering_max": round(0.35 / 0.5235987755982988, 6),
                               "steer_feedback_rad": 0.3505, "containment_box": (-4.23, 2.12, -9.04, 7.65)}}


# Recorded build/evidence paths stay as written. The working environments moved once, by rename on the
# same filesystem (2026-10-06, user request), so a recorded path is compared after this prefix mapping;
# player identity is still checked by content hashes against the build record.
PATH_RELOCATIONS = (("/tmp/roboracer-work/", str(Path.home() / "roboracer-work") + "/"),)


def relocated_path(path):
    for old, new in PATH_RELOCATIONS:
        if path and path.startswith(old):
            return new + path[len(old):]
    return path


def outside_containment(stage, reference, position):
    """Hard bridge containment for motion stages (fails closed): a radius from the first frame,
    or for M6 an axis-aligned box (x_min, x_max, y_min, y_max) in IPS coordinates."""
    limits = AVLITE_MOTION_STAGES.get(stage, {})
    if "containment_box" in limits:
        x_min, x_max, y_min, y_max = limits["containment_box"]
        return not (x_min <= position[0] <= x_max and y_min <= position[1] <= y_max)
    return math.dist(reference, position) >= limits.get("containment_m", M1_CONTAINMENT_M)
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
    if stage in AVLITE_MOTION_STAGES:
        limits = AVLITE_MOTION_STAGES[stage]
        if not (math.isfinite(throttle) and math.isfinite(steering) and 0 <= throttle <= limits["throttle_max"]
                and abs(steering) <= limits["steering_max"]):
            raise ValueError(f"Guard request outside confirmed stage {stage}: {throttle} {steering}")
        return
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
        if stage in AVLITE_MOTION_STAGES and math.isfinite(value):
            limits = AVLITE_MOTION_STAGES[stage]
            if key == "Throttle" and -0.0005 <= value <= limits["throttle_max"] + 0.0005:
                result["Throttle Feedback"] = value
                continue
            if key == "Steering" and abs(value) <= limits["steer_feedback_rad"]:
                result["Steering Feedback"] = value
                continue
        # M1/M2: throttle feedback (reported to 3 decimals) must be one of the stage's values.
        if key == "Throttle" and stage in ("m1", "m2", "m3", "m3b") and math.isfinite(value) and \
                any(abs(value - allowed) <= 0.0005 for allowed in MOTION_STAGES[stage]["throttle"]):
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
        # S2 batch (D20 A): the AVLite stage appends each finished episode to stage-episodes.json.
        episode_done = (lambda n: n <= len(read(out / "stage-episodes.json").get("episodes", []))) \
            if args.guard == "batch" and args.motion_stage else None
        driver = ScenarioDriver(inbox, lambda number: str(number) in read(out / "actions-done.json"),
                                mode=args.guard, duration_ns=int(args.duration * 1e9),
                                trigger=lambda: read(out / "guard-trigger.json"), case=args.f1_case or args.f2_case,
                                episodes=args.episodes, episode_done=episode_done, motion=bool(args.motion_stage))
        state.update(guard_mode=args.guard, guard_socket=socket_name(os.getpid()))

    def freeze_request():
        if args.freeze_test and args.freeze_trigger:
            # F1-1: freeze only inside the window the AVLite stage requested (monotonic ns).
            window = read(out / "freeze-request.json")
            now = time.monotonic_ns()
            inside = window and window["start_ns"] <= now < window["start_ns"] + int(window["duration_s"] * 1e9)
            return args.freeze_test if inside else ""
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
        # S2 batch 2: a lock-step stall left the player idle after the bridge had counted its reply. Record
        # when the reply was handed to Socket.IO and when that call returned, so the next stall shows
        # whether the last reply left this process.
        state["last_emit_started_ns"] = time.monotonic_ns()
        result = raw_emit(event, data=data, **kwargs)
        state["last_emit_returned_ns"] = time.monotonic_ns()
        checkpoint()
        return result

    @incoming.sio.on("connect")
    def connected(sid, environ):
        state["connections"] += 1
        allowed = {"reset": 2, "batch": args.episodes}.get(args.guard, 1)  # one Connect per scene load
        if state["connections"] > allowed:
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
            if args.motion_stage in ("m1", "m2", "m3", "m3b") or args.motion_stage in AVLITE_MOTION_STAGES:
                # Motion is intended: only the hard containment bound stops the bridge here.
                changed = ["Position"] if outside_containment(args.motion_stage, reference["Position"],
                                                              motion["Position"]) else []
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
    except Exception:
        # rclpy's SIGTERM handler can shut the context down between ok() and the next wait set
        # ("context is not valid"); that is the requested stop, not a failure (seen 2026-10-06).
        if rclpy.ok():
            raise
        state["shutdown_race"] = True
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
        controller_name = {"m4": "SpeedStepController", "m5": "GapFollowController",
                           "m6": "GapFollowController"}.get(args.stack_profile, "HoldController")
        executer = executor_factory(
            executer_type="SyncExecuter", bridge="AutoDriveBridge", perception_strategy_name="",
            localization_strategy_name="", mapping_strategy_name="", global_planner_strategy_name="",
            local_planner_strategy_name="", controller_strategy_name=controller_name, execution_task_names=[],
            default_global_trajectory_file="", map_file="", load_plugins=True)
        plugin = sys.modules["avlite.plugins.roboracer"]
        bridge = executer.world
        if args.stack_profile:
            # Proposal v0.2 §4: 0.3 m/s for M4/M5/M6, in this process only (the shipped default stays 0).
            plugin.PluginSettings.max_target_speed_mps = 0.3
        if args.stack_profile == "m6":
            # D9 (lap proposal v0.1): A-lap = GapFollowController with LAP_PARAMS.
            executer.controller.params = sys.modules[type(executer.controller).__module__].LAP_PARAMS
    else:
        import_plugin_modules(str(args.plugin), pkg_name="roboracer")
        plugin = sys.modules["avlite.plugins.roboracer"]
        bridge = plugin.AutoDriveBridge()
    trace = (args.results / "plugin-snapshots.jsonl").open("w", buffering=1)
    state = {"pid": os.getpid(), "plugin": str(args.plugin), "plugin_file": plugin.__file__,
             "stack_capabilities": sorted(c.name for c in bridge.stack_capabilities),
             "max_target_speed_mps": plugin.PluginSettings.max_target_speed_mps, "ready": False, "snapshots": 0,
             "stack": bool(executer), "supervisor": args.supervisor, "ticks": 0, "tick_overruns": 0,
             "stack_profile": args.stack_profile}
    params = getattr(executer.controller, "params", None) if executer else None
    if params is not None:
        state["controller_params"] = dict(params.__dict__)  # audit: A (M5) or A-lap (M6)
    stage = StackStage(args, executer, bridge, state) if args.stack_profile else None
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
    recorder = None
    if args.record_inputs:
        # S2-03: every raw message the bridge processes, for open-loop replay (roboracer_inputs.py).
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from roboracer_inputs import MAX_BYTES, InputRecorder
        recorder = InputRecorder(args.results / "plugin-inputs.jsonl", max_bytes=MAX_BYTES * max(1, args.episodes))
        bridge.message_listener = recorder
        state["input_recording"] = recorder.stats
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
            step = stage.before_tick() if stage else True
            if step:
                # Stage periods slightly below the tick so AVLite's float time sum never skips control.
                stage_dt = period * 0.99
                executer.step(sim_dt=period, control_dt=stage_dt, replan_dt=stage_dt, perception_dt=stage_dt,
                              localization_dt=stage_dt)
            tick = bridge._tick_snapshot
            row = {"start_ns": started, "end_ns": time.monotonic_ns(), "stepped": step,
                   "telemetry_seq": tick.telemetry_seq if tick else None, "request_seq": bridge._request_seq}
            if stage:
                row.update(stage.tick_record())
            ticks.write(json.dumps(row) + "\n")
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
        if recorder is not None:
            recorder.close()
        state["completed"] = True
        checkpoint()
        trace.close()
        if ticks is not None:
            ticks.close()


M0_SPAWN_XY = (0.741, 3.158)  # recorded spawn IPS (S1-02)
RESET_XY = (52, 606)  # GUI "Reset" button in the 1280x720 player window (SceneReset reloads the scene)
# SIM1-05: simulator-hang containment. Telemetry gaps are ~0.25 s at most (0.65 s under GPU starvation, M4);
# no frame for this long while the player process exists is treated as a hung simulator.
SIM_HANG_S = 2.0


def simulator_hung(last_received_ns, now_ns, threshold_s=SIM_HANG_S):
    """True when the last telemetry frame is older than the hang threshold."""
    return bool(last_received_ns) and now_ns - last_received_ns > threshold_s * 1e9
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
    if args.motion_stage == "m2":
        return calibrate_m2(args)
    if args.motion_stage in ("m3", "m3b"):
        return calibrate_m3(args)
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


M2_THROTTLE = 0.01
M2_INSIST_S = 3.0     # case b: keep requesting while the supervisor must inhibit itself
M2_OBSERVE_S = 6.0    # after the last request: watch the stop


def calibrate_m2(args):
    """M2 stop cases under motion (0.01, steering 0). Case a, algorithm hang: one request on a
    frame, then silence; the guard lease must expire with throttle applied. Case b, runner loss:
    the runner stops heartbeating while 0.01 is requested every frame; the supervisor must
    inhibit itself and the guard lease must then expire. The source never sends a zero to stop
    the vehicle: stopping is the mechanism under test. It only falls silent early on an abort."""
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
    state = {"pid": os.getpid(), "stage": "m2", "case": args.m2_case, "phase": "wait-armed", "ready": False,
             "seq": 0, "sent": 0, "send_failures": 0, "abort": None, "precheck": None, "pulse": None}
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

    bridge.snapshot_listener = arrivals.put
    bridge.connect()
    state["ready"] = True
    checkpoint()
    previous = start = None
    phase_start = None
    try:
        while not stop:
            try:
                snapshot = arrivals.get(timeout=M1_FRAME_GAP_S)
            except queue.Empty:
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
            if phase in ("done", "aborted-done"):
                continue
            if start is not None and state["abort"] is None:
                dx, dy = x - start[0], y - start[1]
                lateral = abs(-math.sin(start[2]) * dx + math.cos(start[2]) * dy)
                travel = math.cos(start[2]) * dx + math.sin(start[2]) * dy
                yaw_change = abs(math.degrees(math.remainder(yaw - start[2], math.tau)))
                reason = ("speed %.3f m/s" % speed if speed > M1_SPEED_CAP_MPS else
                          "travel %.3f m" % travel if travel > M1_TRAVEL_CAP_M else
                          "yaw change %.1f deg" % yaw_change if yaw_change > 10 else
                          "lateral deviation %.3f m" % lateral if lateral > 0.15 else
                          "forward clearance %.2f m" % forward if forward < 1.0 else
                          "side clearance %.2f m" % min(left, right) if min(left, right) < 0.25 else
                          "guard fault" if guard_state == "fault" else None)
                if reason:  # silence is the only stop action the source has; it is the mechanism under test
                    state["abort"] = reason
                    if state["phase"] == "insist":
                        state["phase"], phase_start = "observe", now
            phase = state["phase"]
            if phase == "wait-armed":
                send(snapshot, 0.0)
                if guard_state == "armed":
                    state["phase"], phase_start = "settle", now
            elif phase == "settle":
                send(snapshot, 0.0)
                if now - phase_start >= M0_SETTLE_S:
                    check = {"spawn_offset_m": math.dist((x, y), M0_SPAWN_XY), "forward_min_m": forward,
                             "left_min_m": left, "right_min_m": right, "telemetry_seq": snapshot.telemetry_seq}
                    check["passed"] = check["spawn_offset_m"] <= 0.020 and forward >= 1.5 and min(left, right) >= 0.4 \
                        and speed < M1_STOP_SPEED_MPS
                    state["precheck"] = check
                    if not check["passed"]:
                        state.update(phase="aborted-done", abort="workspace precheck")  # silent: lease expires at rest
                    else:
                        start = (x, y, yaw)
                        state["pulse"] = {"start": [x, y, yaw], "start_sim": sim,
                                          "start_telemetry_seq": snapshot.telemetry_seq}
                        if args.m2_case == "b":
                            save(args.results / "runner-heartbeat-pause.json", {"requested_ns": time.monotonic_ns()})
                            state["phase"] = "insist"
                        else:
                            state["phase"] = "hang"
                        phase_start = now
                        send(snapshot, M2_THROTTLE)
                        if args.m2_case == "a":
                            state["pulse"]["last_request_seq"] = state["seq"]
            elif phase == "insist":
                if now - phase_start < M2_INSIST_S:
                    send(snapshot, M2_THROTTLE)
                    state["pulse"]["last_request_seq"] = state["seq"]
                else:
                    state["phase"], phase_start = "observe", now
            elif phase in ("hang", "observe"):
                if now - phase_start >= M2_OBSERVE_S:
                    state["phase"] = "done"
            checkpoint()
    finally:
        bridge.close()
        sock.close()
        state["completed"] = True
        checkpoint()
        log.close()
        frames_log.close()


M3_HOLDS = (0.005, 0.01, 0.02)
M3_SPEED_END_MPS = 0.3      # hold ends at this encoder speed ...
M3_HOLD_MAX_S = 2.0         # ... or after this long ...
M3_HOLD_TRAVEL_M = 0.4      # ... or at this encoder travel (keeps travel incl. braking under 0.5 m)
# M3b (proposal v0.2): up to ~0.3 m/s. A frame then covers ~6 cm and braking ~6 cm, so the
# travel end is 0.35 m to keep each hold under the 0.5 m cap.
M3B_HOLDS = (0.03, 0.045, 0.06)
M3B_HOLD_TRAVEL_M = 0.35
M3_REST_MIN_S = 1.5         # after the hold ends, before the next may start (stop window)
WHEEL_RADIUS_M = 0.059      # WheelCollider radius; encoder angle (rad) x radius = distance (M1)


def calibrate_m3(args):
    """S1-03 M3 identification (proposal v0.1, D8): open-loop throttle holds, steering 0.
    Frame-locked like M1; encoder speed (mean of both wheels, acquisition sim time) ends each
    hold; zero throttle (hard brake) follows. Never exceeds the stage profile. Stage m3b
    (proposal v0.2) uses holds 0.03/0.045/0.06 and a 0.35 m travel end."""
    import queue
    from avlite.c60_apps.c63_plugins import import_plugin_modules

    holds, hold_travel_end = ((M3B_HOLDS, M3B_HOLD_TRAVEL_M) if args.motion_stage == "m3b"
                              else (M3_HOLDS, M3_HOLD_TRAVEL_M))
    assert all(h in MOTION_STAGES[args.motion_stage]["throttle"] for h in holds)

    import_plugin_modules(str(args.plugin), pkg_name="roboracer")
    plugin = sys.modules["avlite.plugins.roboracer"]
    bridge = plugin.AutoDriveBridge()
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)
    log = (args.results / "calibration-requests.jsonl").open("w", buffering=1)
    frames_log = (args.results / "calibration-frames.jsonl").open("w", buffering=1)
    arrivals = queue.Queue()
    state = {"pid": os.getpid(), "stage": args.motion_stage, "holds_planned": list(holds), "phase": "wait-armed", "ready": False, "seq": 0, "sent": 0,
             "send_failures": 0, "holds": [], "abort": None, "precheck": None, "finish_reason": None}
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

    bridge.snapshot_listener = arrivals.put
    bridge.connect()
    state["ready"] = True
    checkpoint()
    previous = None  # (mean encoder angle, encoder sim time)
    armed_at = phase_start = hold = start_pose = None
    still_frames = 0
    try:
        while not stop:
            try:
                snapshot = arrivals.get(timeout=M1_FRAME_GAP_S)
                if state["phase"] in ("done", "aborted-done"):
                    continue
            except queue.Empty:
                if state["phase"] in ("done", "aborted-done"):
                    continue
                if state["phase"] in ("hold", "brake", "ready") and state["abort"] is None:
                    state.update(phase="aborted", abort=f"no new observation for {M1_FRAME_GAP_S} s")
                    phase_start = time.monotonic()
                elif state["phase"] in ("finish", "aborted") and time.monotonic() - phase_start >= 4.0:
                    state["phase"] = "done" if state["phase"] == "finish" else "aborted-done"
                checkpoint()
                continue
            now = time.monotonic()
            angle = sum(snapshot.encoder_angles_rad) / 2
            encoder_sim = snapshot.sources["left_encoder"]["sim_time"]
            speed = ((angle - previous[0]) * WHEEL_RADIUS_M / (encoder_sim - previous[1])
                     if previous and encoder_sim > previous[1] else 0.0)
            previous = (angle, encoder_sim)
            x, y, yaw = snapshot.pose.x, snapshot.pose.y, snapshot.pose.yaw
            ranges = snapshot.scan_ranges
            forward, left, right = sector_min(ranges, -15, 15), sector_min(ranges, 80, 100), sector_min(ranges, -100, -80)
            guard_state = read(args.results / "bridge-status.json").get("guard", {}).get("state")
            phase = state["phase"]
            frames_log.write(json.dumps({"t": time.monotonic_ns(), "telemetry_seq": snapshot.telemetry_seq,
                                         "encoder_sim_time": encoder_sim, "ips_sim_time": snapshot.sources["ips"]["sim_time"],
                                         "encoder_angle_rad": angle, "encoder_speed_mps": speed,
                                         "pose": [x, y, yaw], "forward_m": forward, "left_m": left, "right_m": right,
                                         "guard": guard_state, "phase": phase}) + "\n")
            still_frames = still_frames + 1 if abs(speed) < M1_STOP_SPEED_MPS else 0

            # Protocol §3 abort monitor while anything may be moving.
            if phase in ("hold", "brake", "ready") and start_pose is not None and state["abort"] is None:
                dx, dy = x - start_pose[0], y - start_pose[1]
                heading = start_pose[2]
                lateral = abs(-math.sin(heading) * dx + math.cos(heading) * dy)
                yaw_change = abs(math.degrees(math.remainder(yaw - heading, math.tau)))
                hold_travel = (angle - hold["start_angle"]) * WHEEL_RADIUS_M if hold else 0.0
                reason = ("guard fault" if guard_state == "fault" else
                          "speed %.3f m/s" % speed if speed > M1_SPEED_CAP_MPS else
                          "hold travel %.3f m" % hold_travel if hold_travel > M1_TRAVEL_CAP_M else
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
                    start_pose = (x, y, yaw)
                    if check["passed"]:
                        state["phase"] = "ready"
                    else:
                        state.update(phase="aborted", abort="workspace precheck")
                        phase_start = now
            elif phase == "ready":
                done = state["holds"]
                travelled = sum(h["travel_m"] for h in done)
                reason = ("sequence complete" if len(done) >= len(holds) else
                          "armed time" if now - armed_at + M3_HOLD_MAX_S + M3_REST_MIN_S + 1.0 > M1_ARMED_LIMIT_S else
                          "trial travel" if travelled + M1_TRAVEL_CAP_M > M1_TRIAL_TRAVEL_M else
                          "forward clearance before hold" if forward < 1.5 else
                          "side clearance before hold" if min(left, right) < 0.4 else None)
                if reason:
                    state.update(phase="finish", finish_reason=reason)
                    phase_start = now  # silent: the lease expires with zero output
                elif still_frames >= 2:
                    throttle = holds[len(done)]
                    hold = {"throttle": throttle, "start_angle": angle, "start_encoder_sim": encoder_sim,
                            "start_pose": [x, y, yaw], "start_telemetry_seq": snapshot.telemetry_seq,
                            "max_speed_mps": 0.0, "end_reason": None, "started_at": now}
                    state["phase"] = "hold"
                    send(snapshot, throttle)
                else:
                    send(snapshot, 0.0)
            elif phase == "hold":
                hold["max_speed_mps"] = max(hold["max_speed_mps"], speed)
                travel = (angle - hold["start_angle"]) * WHEEL_RADIUS_M
                hold_s = encoder_sim - hold["start_encoder_sim"]
                end = ("speed" if speed >= M3_SPEED_END_MPS else "time" if hold_s >= M3_HOLD_MAX_S else
                       "travel" if travel >= hold_travel_end else None)
                if end:
                    hold.update(end_reason=end, end_speed_mps=speed, end_encoder_sim=encoder_sim,
                                end_travel_m=travel, end_telemetry_seq=snapshot.telemetry_seq)
                    state["phase"], phase_start = "brake", now
                    send(snapshot, 0.0)  # zero throttle = hard brake
                else:
                    send(snapshot, hold["throttle"])
            elif phase == "brake":
                send(snapshot, 0.0)
                if still_frames >= 2 and now - phase_start >= M3_REST_MIN_S:
                    hold.update(travel_m=(angle - hold["start_angle"]) * WHEEL_RADIUS_M, stop_encoder_sim=encoder_sim,
                                final_pose=[x, y, yaw])
                    state["holds"].append({k: v for k, v in hold.items() if k != "started_at"})
                    state["phase"] = "ready"
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


# S1-03 proposal v0.2, D8: M4 closed-loop speed (straight, steering 0) and M5 reactive A.
M4_SCHEDULE = ((0.0, 3.0, 0.1), (3.0, 6.0, 0.2), (6.0, 9.0, 0.3), (9.0, 11.0, 0.0), (11.0, 13.0, 0.2))
M4_BLACKOUT_AT_S = 12.0     # stale-feedback case: inside the last 0.2 m/s step
M4_TRAVEL_ABORT_M = 2.5
M5_DISTANCE_M, M5_TIME_S = 6.0, 40.0
M6_DISTANCE_M, M6_TIME_S = 33.0, 200.0  # D10: one lap plus the opening straight, or 200 s
# S1-06 M1 protocol v0.1 (D14): F1 injection at 6.0 s of run time; the case ends 8 s later.
F1_CASES = ("f1-1", "f1-2", "f1-3", "f1-4", "f1-5", "f1-6", "f1-7", "f1-8", "f1-9")
F1_INJECT_S, F1_END_S, F1_FAULT_S, F1_REARM_S = 6.0, 8.0, 5.0, 3.0
STOP_HOLD_S = 1.5           # zero requests before going silent (lease then expires at zero)
# S2 F2 catalog (proposal v0.1 section 5, D23): injected in the batch's first episode at 6.0 s of run time.
F2_CASES = tuple(f"f2-{n}" for n in range(1, 11))
F2_INJECT_S = 6.0
F2_FAULT_S = 1.0            # F2-2/F2-3: duplicated / reordered observations for this long (about 5 frames)
F2_CLOCK_JUMP_NS = 1_000_000_000
F2_END_S = 8.0              # process-loss cases: observe this long after the injection, then end the session


class StackStage:
    """Runs a confirmed AVLite motion stage inside the stack child: waits for arming, settles,
    checks the workspace, drives the test controller and applies the stage's abort rules.
    Aborting or finishing requests zero, then stops stepping, so the guard lease expires with
    zero output. GT pose is used only for these labelled monitors, never by the controller."""

    def __init__(self, args, executer, bridge, state):
        self.args, self.executer, self.bridge, self.state = args, executer, bridge, state
        self.profile = args.stack_profile
        self.controller = executer.controller
        self.phase, self.phase_start = "wait-armed", time.monotonic()
        self.start_pose = self.last_pose = None
        self.path_m = 0.0
        self.last_seq, self.last_new = None, time.monotonic()
        self.blackout_written = False
        self.info = {}
        self.f1 = getattr(args, "f1_case", None)
        self.injected_at = None
        self.scan_fault_until_ns = 0
        # S2 batch (D20 A): episode `number` of `episodes`, in simulator episode `episode` (scene load count).
        self.episodes, self.number, self.episode, self.reported = getattr(args, "episodes", 1) or 1, 1, None, False
        self.saw_unarmed = False
        self.f2, self.f2_injected = getattr(args, "f2_case", None), None
        state.update(stage_phase=self.phase, abort=None, finish_reason=None, precheck=None, f1_case=self.f1,
                     f2_case=self.f2, stage_episodes=[])
        self._request(0.0)

    def _report_episode(self):
        """Append the finished episode for the bridge-side batch driver and the scorer."""
        entry = {"number": self.number, "episode": self.episode, "finish_reason": self.state.get("finish_reason"),
                 "abort": self.state.get("abort"), "precheck": self.state.get("precheck"), "path_m": self.path_m,
                 "finished_ns": time.monotonic_ns()}
        self.state["stage_episodes"].append(entry)
        save(self.args.results / "stage-episodes.json", {"episodes": self.state["stage_episodes"]})
        self.reported = True

    def _next_episode(self, snap):
        """Back to wait-armed for the next episode after the scene load (GUI Reset) arrived."""
        self.number, self.episode, self.reported, self.saw_unarmed = self.number + 1, snap.episode, False, False
        self.start_pose = self.last_pose = None
        self.path_m, self.last_seq, self.last_new = 0.0, None, time.monotonic()
        self.state.update(abort=None, finish_reason=None, precheck=None, stage_number=self.number)
        self._request(0.0)
        self._set("wait-armed")

    def _request(self, speed):
        if self.profile == "m4":
            self.controller.target_speed = speed
        else:
            self.controller.enabled = speed != 0.0  # GapFollow chooses its own speed when enabled

    def _set(self, phase, **extra):
        self.phase, self.phase_start = phase, time.monotonic()
        self.state.update(stage_phase=phase, **extra)

    def before_tick(self):
        now = time.monotonic()
        snap = self.bridge.latest()
        guard_state = read(self.args.results / "bridge-status.json").get("guard", {}).get("state")
        if snap is not None and snap.telemetry_seq != self.last_seq:
            self.last_seq, self.last_new = snap.telemetry_seq, now
            pose = (snap.pose.x, snap.pose.y)
            if self.last_pose is not None and self.phase in ("run", "stopping"):
                self.path_m += math.dist(pose, self.last_pose)
            self.last_pose = pose
        speed = self.bridge._encoder_speed.get(snap.telemetry_seq) if snap is not None else None
        ranges = snap.scan_ranges if snap is not None else None
        self.info = {"phase": self.phase, "guard": guard_state, "encoder_speed": speed, "path_m": self.path_m}
        if snap is not None:
            self.info.update(front10=sector_min(ranges, -10, 10), front15=sector_min(ranges, -15, 15),
                             left=sector_min(ranges, 80, 100), right=sector_min(ranges, -100, -80),
                             pose=[snap.pose.x, snap.pose.y, snap.pose.yaw])
        elapsed = now - self.phase_start
        if self.phase in ("settle", "run", "stopping") and snap is not None and self.episode is not None \
                and snap.episode > self.episode:
            # The scene reloaded during the episode (F2-1 reset during motion): the episode is over.
            self._request(0.0)
            self._set("finished", finish_reason="scene reload")
        if self.phase == "finished":
            if not self.reported:
                self._report_episode()
            if self.number < self.episodes and snap is not None and self.episode is not None \
                    and snap.episode > self.episode:
                self._next_episode(snap)
            else:
                return False  # no requests: the guard lease expires; the runner resets the scene
        if self.phase == "wait-armed":
            if snap is not None and self.episode is None:
                self.episode = snap.episode
            if guard_state != "armed":
                self.saw_unarmed = True
            # From the second episode on, an "armed" left over from the previous episode never counts:
            # the guard must have been seen not armed since this episode began (scene load disarms it).
            if guard_state == "armed" and snap is not None and snap.episode == self.episode and \
                    (self.number == 1 or self.saw_unarmed):
                self._set("settle")
            return True
        if self.phase == "settle":
            if elapsed >= M0_SETTLE_S and snap is not None:
                check = {"spawn_offset_m": math.dist((snap.pose.x, snap.pose.y), M0_SPAWN_XY),
                         "forward_min_m": self.info["front15"], "left_min_m": self.info["left"],
                         "right_min_m": self.info["right"]}
                check["passed"] = (check["spawn_offset_m"] <= 0.020 and check["forward_min_m"] >= 1.5
                                   and min(check["left_min_m"], check["right_min_m"]) >= 0.4)
                self.state["precheck"] = check
                if check["passed"]:
                    self.start_pose = (snap.pose.x, snap.pose.y, snap.pose.yaw)
                    self._set("run")
                else:
                    self._set("stopping", abort="workspace precheck")
            return True
        if self.phase == "hang":
            # F1-3: the process stays alive but AVLite is not stepped, so no request is generated.
            if now - self.injected_at >= F1_END_S:
                self._set("finished", finish_reason="f1 case end")
            return False
        if self.phase == "run" and self.f1:
            if self.injected_at is None and elapsed >= F1_INJECT_S:
                self._inject(now, snap, speed)
                if self.phase == "hang":
                    return False
            elif self.injected_at is not None and now - self.injected_at >= F1_END_S:
                if self.f1 == "f1-5":  # re-armed and driving again: the normal zero-request stop
                    self._request(0.0)
                    self._set("stopping", finish_reason="f1 case end")
                    return True
                self._set("finished", finish_reason="f1 case end")  # guard already stopped: no requests
                return False
        if self.phase == "run" and self.f2 and self.number == 1 and self.f2_injected is None \
                and elapsed >= F2_INJECT_S:
            self._inject_f2(now, snap, speed)
        if self.phase == "run":
            reason = self._abort_reason(now, snap, speed, guard_state)
            if reason:
                self._request(0.0)
                self._set("stopping", abort=reason)
                return True
            if self.profile == "m4":
                current = [v for start, end, v in M4_SCHEDULE if start <= elapsed < end]
                if not current:
                    self._request(0.0)
                    self._set("stopping", finish_reason="schedule complete")
                    return True
                self._request(current[0])
                if elapsed >= M4_BLACKOUT_AT_S and not self.blackout_written:
                    save(self.args.results / "supervisor-feedback-blackout.json", {"requested_ns": time.monotonic_ns()})
                    self.blackout_written = True
                    self.state["blackout_written_ns"] = time.monotonic_ns()
            else:
                distance, limit = (M6_DISTANCE_M, M6_TIME_S) if self.profile == "m6" else (M5_DISTANCE_M, M5_TIME_S)
                if self.path_m >= distance or elapsed >= limit:
                    self._request(0.0)
                    self._set("stopping", finish_reason="distance" if self.path_m >= distance else "time")
                    return True
                self._request(1.0)
            return True
        if self.phase == "stopping":
            self._request(0.0)
            if elapsed >= STOP_HOLD_S:
                self._set("finished")
                return False
            return True
        return False  # finished: no further requests; the guard lease expires

    def _inject(self, now, snap, speed):
        """S1-06 F1 injection (M1 protocol v0.1, D14). Test-only; selected on the command line."""
        results = self.args.results
        self.injected_at = now
        record = {"case": self.f1, "injected_ns": time.monotonic_ns(), "run_elapsed_s": now - self.phase_start,
                  "encoder_speed": speed, "path_m": self.path_m,
                  "pose": [snap.pose.x, snap.pose.y, snap.pose.yaw] if snap is not None else None}
        if self.f1 == "f1-1":
            save(results / "freeze-request.json", {"kind": "lidar", "start_ns": record["injected_ns"],
                                                   "duration_s": F1_FAULT_S})
        elif self.f1 == "f1-2":
            self._install_scan_fault(record["injected_ns"] + int(F1_FAULT_S * 1e9))
        elif self.f1 == "f1-3":
            self._set("hang")
        elif self.f1 == "f1-4":
            record["direct_nan"] = self._install_nonfinite()
        elif self.f1 == "f1-5":
            save(results / "guard-trigger.json", {"disarm": True, "rearm_after_s": F1_REARM_S, "source": "f1-5"})
        elif self.f1 == "f1-6":
            save(results / "kill-stack-request.json", {"requested_ns": record["injected_ns"]})
        elif self.f1 == "f1-7":
            save(results / "runner-heartbeat-pause.json", {"requested_ns": record["injected_ns"]})
        elif self.f1 == "f1-8":
            save(results / "kill-runner-request.json", {"requested_ns": record["injected_ns"]})
        elif self.f1 == "f1-9":
            save(results / "runner-error-request.json", {"requested_ns": record["injected_ns"]})
        save(results / "fault-inject.json", record)
        self.state["f1_injected_ns"] = record["injected_ns"]

    def _inject_f2(self, now, snap, speed):
        """S2 F2 injection (proposal v0.1 section 5, D23). Test-only; selected on the command line.
        Stack-side cases act here; process and scene cases are carried out by the runner (f2-inject.json),
        the clock jump by the bridge-side guard driver (guard-trigger.json)."""
        results = self.args.results
        self.f2_injected = now
        record = {"case": self.f2, "injected_ns": time.monotonic_ns(), "run_elapsed_s": now - self.phase_start,
                  "episode": self.episode, "encoder_speed": speed, "path_m": self.path_m,
                  "pose": [snap.pose.x, snap.pose.y, snap.pose.yaw] if snap is not None else None}
        until = record["injected_ns"] + int(F2_FAULT_S * 1e9)
        if self.f2 == "f2-2":
            self._install_duplicates(until)
        elif self.f2 == "f2-3":
            self._install_reorder(until)
        elif self.f2 == "f2-4":
            save(results / "guard-trigger.json", {"clock_jump_ns": F2_CLOCK_JUMP_NS, "source": "f2-4"})
        elif self.f2 == "f2-5":
            save(results / "supervisor-feedback-blackout.json", {"requested_ns": record["injected_ns"], "source": "f2-5"})
        save(results / "f2-inject.json", record)
        self.state["f2_injected_ns"] = record["injected_ns"]

    def _install_duplicates(self, until_ns):
        """F2-2: every incoming message (sensors and provenance) is delivered twice until `until_ns`."""
        bridge, original = self.bridge, self.bridge._offer

        def offer(topic, message):
            original(topic, message)
            if time.monotonic_ns() < until_ns:
                self.state["f2_duplicated"] = self.state.get("f2_duplicated", 0) + 1
                original(topic, message)

        bridge._offer = offer

    def _install_reorder(self, until_ns):
        """F2-3: provenance records arrive out of order until `until_ns`: each is held back and delivered
        after the next one (an older telemetry sequence after a newer one)."""
        bridge, original = self.bridge, self.bridge._offer
        held = []

        def offer(topic, message):
            if topic != "provenance":
                return original(topic, message)
            if time.monotonic_ns() < until_ns or held:
                if not held and time.monotonic_ns() < until_ns:
                    held.append(message)
                    return
                original(topic, message)
                if held:
                    self.state["f2_reordered"] = self.state.get("f2_reordered", 0) + 1
                    original(topic, held.pop())
                return
            original(topic, message)

        bridge._offer = offer

    def _install_scan_fault(self, until_ns):
        """F1-2: incoming LiDAR messages carry NaN ranges until `until_ns` (wraps this bridge
        instance's intake; the plugin source is unchanged)."""
        import copy
        bridge, original = self.bridge, self.bridge._offer

        def offer(topic, message):
            if topic == "lidar" and time.monotonic_ns() < until_ns:
                message = copy.copy(message)
                message.ranges = [math.nan] * len(message.ranges)
                self.state["f1_corrupted_scans"] = self.state.get("f1_corrupted_scans", 0) + 1
                self.state.setdefault("f1_first_corrupted_ns", time.monotonic_ns())  # D17: F1-2 onset
            return original(topic, message)

        bridge._offer = offer

    def _install_nonfinite(self):
        """F1-4: (a) the controller's output becomes a NaN target speed (the plugin must refuse it);
        (b) one NaN request goes straight to the supervisor socket (the supervisor must reject it)."""
        controller, original = self.controller, self.controller.control

        def control(*positional, **keywords):
            command = original(*positional, **keywords)
            return type(command)(target_speed=math.nan, steer=command.steer)

        controller.control = control
        bridge = self.bridge
        snapshot = bridge.latest()
        bridge._request_seq += 1
        message = {"kind": "request", "origin": "avlite", "seq": bridge._request_seq, "gen_ns": time.monotonic_ns(),
                   "target_speed": math.nan, "steer": 0.0,
                   "observation": {"telemetry_seq": snapshot.telemetry_seq, "session": snapshot.session,
                                   "episode": snapshot.episode, "stamp_ns": int(round(snapshot.pose.stamp * 1e9)),
                                   "lidar_stamp_ns": int(round(snapshot.lidar.stamp * 1e9))}}
        sock, name = bridge._supervisor
        sock.sendto(json.dumps(message).encode(), "\0" + name)  # json writes NaN as the bare token NaN
        return {"seq": message["seq"], "gen_ns": message["gen_ns"]}

    def _abort_reason(self, now, snap, speed, guard_state):
        if guard_state == "fault":
            return "guard fault"
        gap = 0.6 if self.profile == "m4" else 0.5
        if now - self.last_new > gap:
            return "no new observation for %.2f s" % (now - self.last_new)
        if speed is not None and speed > 0.5:
            return "speed %.3f m/s" % speed
        if self.requested_steer() > 0.35:
            return "requested steer %.3f rad" % self.requested_steer()
        if snap is None or self.start_pose is None:
            return None
        dx, dy = snap.pose.x - self.start_pose[0], snap.pose.y - self.start_pose[1]
        heading = self.start_pose[2]
        if self.profile == "m4":
            lateral = abs(-math.sin(heading) * dx + math.cos(heading) * dy)
            yaw = abs(math.degrees(math.remainder(snap.pose.yaw - heading, math.tau)))
            if self.path_m > M4_TRAVEL_ABORT_M:
                return "travel %.2f m" % self.path_m
            if yaw > 10:
                return "yaw change %.1f deg" % yaw
            if lateral > 0.15:
                return "lateral deviation %.3f m" % lateral
            if self.info["front15"] < 1.0:
                return "forward clearance %.2f m" % self.info["front15"]
            if min(self.info["left"], self.info["right"]) < 0.25:
                return "side clearance %.2f m" % min(self.info["left"], self.info["right"])
        else:
            if min(self.info["left"], self.info["right"]) < 0.15:
                return "side clearance %.2f m" % min(self.info["left"], self.info["right"])
            if self.info["front10"] < 0.5:
                return "forward clearance %.2f m" % self.info["front10"]
        return None

    def requested_steer(self):
        last = getattr(self.controller, "last", None) or {}
        return abs(last.get("steer", 0.0))

    def tick_record(self):
        record = dict(self.info)
        if self.profile == "m4":
            record["target_speed"] = self.controller.target_speed
        else:
            record["controller"] = getattr(self.controller, "last", None)
        return record


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


def sample_gpu(path, stop, period_s=1.0):
    """S1-06: device-level GPU utilization/memory once per second, from a thread so a slow
    nvidia-smi never delays the runner's heartbeats. Not attributable per process (the player
    renders through OpenGL, which compute-app queries do not list)."""
    query = ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"]
    with open(path, "w", buffering=1) as f:
        while not stop.is_set():
            before = time.monotonic_ns()
            try:
                done = subprocess.run(query, capture_output=True, text=True, timeout=5)
                row = {"monotonic_ns": before, "query_ms": (time.monotonic_ns() - before) / 1e6}
                if done.returncode == 0 and done.stdout.strip():
                    util, used, total, temp = (float(v) for v in done.stdout.strip().splitlines()[0].split(","))
                    row.update(utilization_pct=util, memory_used_mib=used, memory_total_mib=total, temperature_c=temp)
                else:
                    row["error"] = done.stderr.strip()[:200] or f"exit {done.returncode}"
            except (OSError, subprocess.TimeoutExpired, ValueError) as exc:
                row = {"monotonic_ns": before, "error": type(exc).__name__}
            f.write(json.dumps(row) + "\n")
            stop.wait(period_s)


def thread_snapshot(pid):
    """Per-thread name, scheduler state and kernel wait channel of a live process (same user, no ptrace)."""
    base = Path(f"/proc/{pid}")
    snapshot = {"pid": pid, "monotonic_ns": time.monotonic_ns(), "threads": []}
    try:
        snapshot["status"] = {k: v.strip() for k, v in (line.split(":", 1) for line in
                              (base / "status").read_text().splitlines() if ":" in line)
                              if k in ("State", "Threads", "VmRSS", "voluntary_ctxt_switches")}
        for task in sorted(base.glob("task/*"), key=lambda p: int(p.name)):
            row = {"tid": int(task.name)}
            for name in ("comm", "wchan"):
                try:
                    row[name] = (task / name).read_text().strip()
                except OSError as exc:
                    row[name] = f"<{type(exc).__name__}>"
            try:
                row["state"] = (task / "stat").read_text().rsplit(")", 1)[1].split()[0]
            except (OSError, IndexError):
                row["state"] = "?"
            snapshot["threads"].append(row)
    except OSError as exc:
        snapshot["error"] = f"{type(exc).__name__}: {exc}"
    return snapshot


def runner_error_stop(out, wait_s=2.0):
    """D16 (M1 protocol v0.1): before any owned process is terminated after a runner error, ask the
    bridge's guard driver to disarm, then wait up to `wait_s` for the guard to report it and for the
    wheels to stop (encoder angles unchanged across the last two frames). Result is recorded."""
    started = time.monotonic_ns()
    save(out / "guard-trigger.json", {"disarm": True, "rearm_after_s": None, "source": "runner-error"})
    result = {"requested_ns": started, "disarmed": False, "stopped": False}
    while time.monotonic_ns() - started < wait_s * 1e9:
        frames = []
        try:
            lines = (out / "bridge-frames.jsonl").read_text().splitlines()[-3:]
            frames = [json.loads(line) for line in lines if line.strip()]
        except (OSError, ValueError):
            pass
        guard = [f.get("guard", {}).get("state") for f in frames]
        angles = [tuple(f["motion"]["Encoder Angles"]) for f in frames if "motion" in f]
        result["disarmed"] = bool(guard) and guard[-1] == "disarmed"
        result["stopped"] = len(angles) >= 2 and max(abs(a - b) for a, b in zip(angles[-1], angles[-2])) < 1e-3
        if result["disarmed"] and result["stopped"]:
            break
        time.sleep(0.05)
    result["waited_s"] = (time.monotonic_ns() - started) / 1e9
    return result


def trial(args, context, out):
    import threading
    from Xlib import X, display
    from Xlib.ext import xtest
    from Xlib.protocol import event
    from PIL import Image
    from autodrive_build import process_sample

    out.mkdir()
    gpu_stop = threading.Event()
    threading.Thread(target=sample_gpu, args=(out / "gpu.jsonl", gpu_stop), daemon=True).start()
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
              "plugin_stack": args.plugin_stack, "f1_case": args.f1_case, "f2_case": args.f2_case}
    heartbeat = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    heartbeat.setblocking(False)
    heartbeat_seq = 0

    def checkpoint():
        save(out / "run.json", record)

    def beat():
        """Runner heartbeat for the supervisor lease, also from GUI actions (SIM1-03 reset). Only while a
        supervisor runs, after Connect, and not while heartbeats are deliberately paused (M2 b, F1-7)."""
        nonlocal heartbeat_seq
        if not ((args.plugin_stack or args.motion_stage) and connected and "heartbeat_paused_ns" not in record):
            return
        heartbeat_seq += 1
        try:
            heartbeat.sendto(json.dumps({"kind": "heartbeat", "seq": heartbeat_seq}).encode(), "\0" + supervisor_name)
        except (BlockingIOError, ConnectionRefusedError, FileNotFoundError):
            record["heartbeat_failures"] = record.get("heartbeat_failures", 0) + 1

    def pause_beating(seconds):
        """Sleep in 0.1 s steps with heartbeats, so GUI input handling never outlives the runner lease."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            beat()
            time.sleep(min(0.1, max(0.0, end - time.monotonic())))

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
            if args.freeze_trigger:
                sim1 += ["--freeze-trigger"]
        if args.f1_case:
            sim1 += ["--f1-case", args.f1_case]
        if args.f2_case:
            sim1 += ["--f2-case", args.f2_case]
        if args.guard:
            sim1 += ["--guard", args.guard, "--duration", str(args.duration)]
            if args.guard == "batch":
                sim1 += ["--episodes", str(args.episodes)]
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
                if args.motion_stage in AVLITE_MOTION_STAGES:
                    # D4 A: the supervisor reads encoder speed itself; M4 also gets the stale-feedback hook.
                    stage += ["--feedback"]
                    if args.motion_stage == "m4" or args.f2_case == "f2-5":
                        stage += ["--blackout-file", str(out / "supervisor-feedback-blackout.json")]
                spawn("supervisor-1", [context["avlite_python"], "-B", "-m", "roboracer.runtime.supervisor_process",
                    "--name", supervisor_name, "--target", read(out / "bridge-status.json")["guard_socket"],
                    "--origin", "sup-1", "--status", str(out / "supervisor-1-status.json"),
                    "--trace", str(out / "supervisor-trace.jsonl"), *stage],
                    # Keep the sourced ROS paths: the M4/M5 supervisor subscribes to ROS itself (D4 A).
                    dict(plugin_environment, PYTHONPATH=":".join(
                        p for p in (str(PLUGIN_DIRECTORY.parent), plugin_environment.get("PYTHONPATH", "")) if p)))
                deadline = time.monotonic() + 30
                while not read(out / "supervisor-1-status.json").get("ready"):
                    if any(p.poll() is not None for p, _, _ in children) or time.monotonic() > deadline:
                        raise RuntimeError("Supervisor startup failed")
                    time.sleep(0.1)
                if args.motion_stage in AVLITE_MOTION_STAGES:
                    spawn("plugin-stack", [context["avlite_python"], "-B", own_script, "plugin-observe",
                                           "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                           "--supervisor", supervisor_name, "--stack-profile", args.motion_stage,
                                           *(["--f1-case", args.f1_case] if args.f1_case else []),
                                           *(["--f2-case", args.f2_case] if args.f2_case else []),
                                           *(["--record-inputs"] if args.record_inputs else []),
                                           "--episodes", str(args.episodes)],
                          plugin_environment)
                    status_name = "plugin-observer-status.json"
                elif args.motion_stage:
                    spawn("calibration", [context["avlite_python"], "-B", own_script, "calibrate",
                                          "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                          "--supervisor", supervisor_name, "--motion-stage", args.motion_stage,
                                          *(["--m2-case", args.m2_case] if args.m2_case else [])],
                          plugin_environment)
                    status_name = "calibration-status.json"
                else:
                    spawn("plugin-stack", [context["avlite_python"], "-B", own_script, "plugin-observe",
                                           "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                           "--supervisor", supervisor_name,
                                           *(["--record-inputs"] if args.record_inputs else [])], plugin_environment)
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
                                      "--results", str(out), "--plugin", str(PLUGIN_DIRECTORY),
                                      *(["--record-inputs"] if args.record_inputs else [])], plugin_environment)
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
            pause_beating(0.5)
            frame = window
            while frame.query_tree().parent.id != root.id:
                frame = frame.query_tree().parent
            frame.configure(stack_mode=X.Above)
            window.configure(stack_mode=X.Above)
            window.set_input_focus(X.RevertToParent, X.CurrentTime)
            window.warp_pointer(x, y)
            connection.sync()
            pause_beating(0.2)
            local = window.query_pointer()
            if connection.get_input_focus().focus != window or (local.win_x, local.win_y) != (x, y):
                raise RuntimeError("Guard input is not targeting the reviewed owned window")

        def click(window, x, y):
            target_window(window, x, y)
            xtest.fake_input(connection, X.ButtonPress, 1)
            connection.sync()
            time.sleep(0.1)  # press and release on separate rendered frames
            xtest.fake_input(connection, X.ButtonRelease, 1)
            connection.sync()
            return time.monotonic_ns()

        def wait_beating(seconds, until=None):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                beat()
                if until is not None and until():
                    return True
                time.sleep(0.1)
            return until() if until is not None else True

        def gui_reset(window, approval):
            """SIM1-03: click GUI Reset (scene reload), confirm the guard's scene-load disarm, then require a
            second visual review of the reloaded scene before reconnecting with the Connect button. Heartbeats
            continue throughout so the supervisor lease reflects runner liveness, not this wait."""
            if window is None:
                raise RuntimeError("Owned player window unavailable for the reset action")
            trace_path = out / "guard/guard-trace.jsonl"
            offset = trace_path.stat().st_size

            def scene_load_seen():
                with open(trace_path, "rb") as f:
                    f.seek(offset)
                    return b"state disarmed scene-load" in f.read()

            def bridge_errors():
                return read(out / "bridge-status.json").get("errors")

            result = {"clicks": [], "reset": False}
            number = len([a for a in record["guard_actions"] if a.get("kind") == "gui-reset"]) + 1
            suffix = f"-{number}" if args.guard == "batch" else ""
            pointer, focus = root.query_pointer(), connection.get_input_focus().focus
            capture(window, "ui-before-reset" + suffix)
            for _ in range(3):
                result["clicks"].append(click(window, *RESET_XY))
                if wait_beating(5, scene_load_seen):
                    result["reset"] = True
                    break
            root.warp_pointer(pointer.root_x, pointer.root_y)
            if hasattr(focus, "set_input_focus"):
                focus.set_input_focus(X.RevertToParent, X.CurrentTime)
            connection.sync()
            if not result["reset"]:
                return result
            wait_beating(4)
            capture(window, "ui-after-reset" + suffix)
            review_name = f"ui-review-reset{suffix}.json"
            record["ui_reset_review_required"] = {"pid": player.pid, "window_id": window.id,
                                                  "screenshot": str(out / f"ui-after-reset{suffix}.png"),
                                                  "review_file": str(out / review_name)}
            checkpoint()
            if args.ui_reference:
                automated_review(window, "ui-after-reset" + suffix, review_name)
            if not wait_beating(900, lambda: (out / review_name).exists()):
                raise TimeoutError("No review of the reloaded scene")
            review = read(out / review_name)
            if review.get("pid") != player.pid or review.get("window_id") != window.id or \
                    review.get("screenshot_sha256") != hashlib.sha256((out / f"ui-after-reset{suffix}.png").read_bytes()).hexdigest():
                raise RuntimeError("Reset review does not match this window or screenshot")
            result["review"] = review
            before = read(out / "bridge-status.json").get("connections", 0)
            pointer, focus = root.query_pointer(), connection.get_input_focus().focus
            for _ in range(3):
                result.setdefault("connect_clicks", []).append(click(window, *approval["connect_xy"]))
                if wait_beating(8, lambda: read(out / "bridge-status.json").get("connections", 0) > before or bridge_errors()):
                    break
            root.warp_pointer(pointer.root_x, pointer.root_y)
            if hasattr(focus, "set_input_focus"):
                focus.set_input_focus(X.RevertToParent, X.CurrentTime)
            connection.sync()
            result["reconnected"] = read(out / "bridge-status.json").get("connections", 0) > before
            processed = read(out / "bridge-status.json").get("processed", 0)
            result["frames_resumed"] = wait_beating(10, lambda: read(out / "bridge-status.json").get("processed", 0)
                                                    >= processed + 3 or bridge_errors())
            result["bridge_errors"] = bridge_errors()
            # Verified single C0 start: the first frames of the new episode are at the spawn and at rest.
            try:
                rows = [json.loads(line) for line in (out / "bridge-frames.jsonl").read_text().splitlines()[-40:]]
                rows = [r for r in rows if "motion" in r and "provenance" in r]
                newest = max((r["provenance"]["episode"] for r in rows), default=None)
                new = [r for r in rows if r["provenance"]["episode"] == newest]
                xy = new[-1]["motion"]["Position"][:2] if new else None
                result["c0_start"] = {
                    "episode": newest, "frames_in_episode": len(new), "position": xy,
                    "offset_m": math.dist(xy, M0_SPAWN_XY) if xy else None,
                    "encoders_still": len(new) >= 2 and new[-1]["motion"]["Encoder Angles"] == new[-2]["motion"]["Encoder Angles"]}
            except (OSError, ValueError, KeyError) as exc:
                result["c0_start"] = {"error": f"{type(exc).__name__}: {exc}"}
            if args.guard == "batch":
                result["readiness"] = readiness(result["c0_start"], read(out / "first-raw-frame.json") and
                                                motion_fields(read(out / "first-raw-frame.json"), args.motion_stage))
                record["guard_actions"].append({"kind": "readiness", **result["readiness"]})  # visible at once
                checkpoint()
                if not (result["reconnected"] and result["frames_resumed"] and result["readiness"]["passed"]):
                    raise RuntimeError("Initialization failed after GUI Reset: " + json.dumps(
                        {"reconnected": result["reconnected"], "frames_resumed": result["frames_resumed"],
                         **result["readiness"]["checks"]}))
            return result

        def automated_review(window, label, review_name):
            """D21 A: the reviewed-reference text-region check replaces the human review; written in the
            same review format, so the Connect path applies all its usual window and hash checks."""
            from roboracer_uicheck import check, load_reference
            result = check(out / (label + ".png"), load_reference(args.ui_reference))
            record.setdefault("ui_checks", []).append(dict(result, label=label))
            checkpoint()
            if not result["passed"]:
                raise RuntimeError(f"Automated pre-Connect check failed ({label}): {result['mismatch_px']}")
            save(out / review_name, {"pid": player.pid, "window_id": window.id, "mode": "Guarded",
                                     "connect_xy": [52, 273], "screenshot_sha256": result["image_sha256"],
                                     "note": "automated D21 text-region check against the reviewed reference",
                                     "automated": result})

        def readiness(c0_start, first):
            """D21 A telemetry readiness after a scene load, before any arm (proposal section 2)."""
            guard = read(out / "bridge-status.json").get("guard", {})
            yaw = None
            try:
                rows = [json.loads(line) for line in (out / "bridge-frames.jsonl").read_text().splitlines()[-40:]]
                new = [r for r in rows if "motion" in r and r.get("provenance", {}).get("episode") == c0_start.get("episode")]
                if new and first:
                    yaw = abs(math.degrees(math.remainder(new[-1]["motion"]["Orientation Euler Angles"][2]
                                                          - first["Orientation Euler Angles"][2], math.tau)))
            except (OSError, ValueError, KeyError):
                pass
            checks = {"spawn offset <= 0.010 m": (c0_start.get("offset_m") or 1e9) <= 0.010,
                      "yaw within 1 deg of the first spawn": yaw is not None and yaw <= 1.0,
                      "wheels still": bool(c0_start.get("encoders_still")),
                      "guard not armed and no fault": guard.get("state") not in ("armed", "fault")}
            return {"checks": checks, "yaw_offset_deg": yaw, "passed": all(checks.values())}

        def guard_action(kind, window, approval):
            now = time.monotonic_ns()
            if kind == "gui-reset":
                return dict(gui_reset(window, approval), monotonic_ns=now)
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

        def f2_action(case, window, approval):
            """S2 F2 cases the runner carries out (proposal v0.1 section 5): scene reset, Devkit loss,
            supervisor exit/hang, simulator exit/hang. Every termination is recorded as expected."""
            now = time.monotonic_ns()
            if case == "f2-1":
                result = gui_reset(window, approval)
                record["guard_actions"].append(dict(result, kind="gui-reset", source="f2-1"))
                return {"case": case, "monotonic_ns": now, "reset": result.get("reset"),
                        "readiness": result.get("readiness")}
            if case == "f2-6":
                return dict(guard_action("kill-bridge", window, approval), case=case)
            if case in ("f2-7", "f2-8"):
                process, _, entry = next(c for c in children if c[2]["label"] == "supervisor-1")
                entry["expected_kill"] = True
                if case == "f2-7":
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    entry["termination"] = "SIGKILL (F2-7 supervisor exit)"
                else:
                    os.killpg(process.pid, signal.SIGSTOP)
                    entry["termination_note"] = "SIGSTOP (F2-8 supervisor hang)"
                return {"case": case, "monotonic_ns": now, "pid": process.pid}
            if case == "f2-9":
                entry = next(e for p, _, e in children if p is player)
                entry["expected_kill"] = True
                os.killpg(player.pid, signal.SIGKILL)
                player.wait()
                entry["termination"] = "SIGKILL (F2-9 simulator exit; containment, not a stop)"
                return {"case": case, "monotonic_ns": now, "pid": player.pid}
            if case == "f2-10":
                os.kill(player.pid, signal.SIGSTOP)  # the hang watchdog contains it
                record["sim_hang_injected_ns"] = now
                return {"case": case, "monotonic_ns": now, "pid": player.pid}
            return {"case": case, "monotonic_ns": now, "runner_action": None}  # stack- or driver-side case

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
        connect_retries = 0
        approval = {}
        sample_at = 0
        with (out / "resources.jsonl").open("w", buffering=1) as metrics:
            while time.monotonic() - started < args.startup_timeout + max(args.duration, args.guard_timeout) + 15:
                if any(p.poll() is not None and not e.get("expected_kill") for p, _, e in children):
                    raise RuntimeError("An owned child exited during observation")
                bridge_state, observer_state = read(out / "bridge-status.json"), read(out / "observer-status.json")
                if bridge_state.get("errors"):
                    raise RuntimeError("Bridge rejected telemetry: " + repr(bridge_state["errors"]))
                if observation_start and connected and "devkit_loss" not in record and player.poll() is None:
                    now_ns = time.monotonic_ns()
                    if args.sim_hang_test and "sim_hang_injected_ns" not in record and \
                            now_ns >= observation_start + int(args.sim_hang_test * 1e9):
                        os.kill(player.pid, signal.SIGSTOP)  # test only: freeze the whole simulator process
                        record["sim_hang_injected_ns"] = now_ns
                        checkpoint()
                    if simulator_hung(bridge_state.get("last_received_ns"), now_ns):
                        # SIM1-05: containment, not a stop. A hung player also freezes its physics; the only
                        # remedy is to end the process. Recorded separately from every stop qualification.
                        entry = next(e for p, _, e in children if p is player)
                        hang = {"detected_ns": now_ns,
                                "frame_age_s": (now_ns - bridge_state["last_received_ns"]) / 1e9,
                                "threshold_s": SIM_HANG_S, "player_threads": thread_snapshot(player.pid),
                                # Did the last reply leave the bridge? (lock-step stall diagnosis, S2 batch 2)
                                "bridge": {k: bridge_state.get(k) for k in (
                                    "processed", "emissions", "last_received_ns", "last_emit_started_ns",
                                    "last_emit_returned_ns", "connections")},
                                "bridge_threads": thread_snapshot(bridge_process.pid),
                                "classification": "containment (process termination), not a stop"}
                        entry["expected_kill"] = True
                        os.killpg(player.pid, signal.SIGKILL)
                        player.wait()
                        entry["termination"] = "SIGKILL (simulator-hang containment)"
                        hang["contained_ns"] = time.monotonic_ns()
                        record["simulator_hang"] = hang
                        checkpoint()
                        raise RuntimeError("Simulator hang: no telemetry for %.2f s; player killed (containment)"
                                           % hang["frame_age_s"])
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
                        if args.ui_reference:
                            automated_review(window, "ui-before-connect", "ui-review.json")
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
                        if args.record_video and "video" not in record:
                            # Only the reviewed AutoDRIVE window (x11grab -window_id), not the screen.
                            # Optional evidence: its exit never aborts the run; spawned last, so cleanup
                            # stops it (SIGTERM, which finalizes the file) before the player.
                            spawn("recorder", ["ffmpeg", "-hide_banner", "-loglevel", "warning", "-nostdin",
                                               "-f", "x11grab", "-framerate", "15", "-draw_mouse", "0",
                                               "-window_id", str(window.id), "-i", os.environ.get("DISPLAY", ":1"),
                                               "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
                                               "-pix_fmt", "yuv420p", str(out / "player-window.mp4")], dict(os.environ))
                            record["children"][-1]["expected_kill"] = True  # same entry object as in `children`
                            record["video"] = {"path": str(out / "player-window.mp4"), "window_id": window.id,
                                               "fps": 15, "started_ns": time.monotonic_ns()}
                            checkpoint()
                    elif connected and not bridge_state.get("transport_requests") and connect_retries < 2 and \
                            time.monotonic_ns() - record["actions"][-1]["monotonic_ns"] > 8_000_000_000:
                        # Unity intermittently drops the synthetic click (no handshake at all). Click the
                        # same reviewed window again through the same checks; at most twice.
                        connect_retries += 1
                        record["connect_retries"] = connect_retries
                        connected = False
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
                    if args.guard in ("observe", "calibration", "reset", "batch") and bridge_state.get("guard", {}).get("complete"):
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
                if args.f1_case == "f1-6" and "f1_stack_killed_ns" not in record and \
                        (out / "kill-stack-request.json").exists():
                    # F1-6 algorithm exit: SIGKILL the AVLite stack; expected, so observation continues.
                    for process, _, entry in children:
                        if entry["label"] == "plugin-stack" and process.poll() is None:
                            entry["expected_kill"] = True
                            os.killpg(process.pid, signal.SIGKILL)
                            entry["termination"] = "SIGKILL (F1-6 algorithm exit)"
                    record["f1_stack_killed_ns"] = time.monotonic_ns()
                    checkpoint()
                if args.f2_case and connected and "f2_action" not in record and (out / "f2-inject.json").exists():
                    record["f2_action"] = f2_action(args.f2_case, window, approval)
                    checkpoint()
                if args.f2_case in ("f2-5", "f2-7", "f2-8", "f2-9") and "f2_action" in record and \
                        time.monotonic_ns() - read(out / "f2-inject.json")["injected_ns"] >= F2_END_S * 1e9:
                    record["f2_case_end_ns"] = time.monotonic_ns()
                    checkpoint()
                    raise RuntimeError(f"{args.f2_case.upper()} case end (expected): observation window over")
                if args.f1_case == "f1-9" and (out / "runner-error-request.json").exists():
                    record["f1_error_raised_ns"] = time.monotonic_ns()
                    raise RuntimeError("F1-9 injected runner error")
                if (args.motion_stage == "m2" or args.f1_case == "f1-7") and "heartbeat_paused_ns" not in record \
                        and (out / "runner-heartbeat-pause.json").exists():
                    # M2 case b: the calibration source asks the runner to stop heartbeating; the
                    # supervisor must inhibit itself within its runner lease. Never resumed.
                    record["heartbeat_paused_ns"] = time.monotonic_ns()
                    checkpoint()
                if (args.plugin_stack or args.motion_stage) and connected and "heartbeat_paused_ns" not in record:
                    # Runner liveness for the supervisor's lease, from this loop only (after the
                    # Connect sequence, whose ~1 s of input handling would otherwise trip it).
                    beat()
                time.sleep(0.1)
        if not (record["completed_observation"] or record["completed_diagnostic_window"]):
            raise TimeoutError("Stationary observation did not complete in its execution bound")
    except BaseException as exc:
        record["error"] = type(exc).__name__ + ": " + str(exc)
        raise
    finally:
        gpu_stop.set()
        cleanup_started = time.monotonic()
        heartbeat.close()  # D16: no further runner heartbeats from here on
        if record.get("error") and args.guard in ("calibration", "batch") and args.motion_stage:
            record["d16"] = runner_error_stop(out)
            checkpoint()
        if connection is not None:
            connection.close()
        for process, log, entry in reversed(children):
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                entry["termination"] = "SIGTERM owned process group"
                try:
                    # The player can hang at shutdown (4/27 M1 v0.2 runs, after stop and disarm). If it is
                    # still alive after 10 s, record its threads (name, state, kernel wait channel) before
                    # the remaining wait and SIGKILL; ptrace_scope 1 rules out an attached debugger.
                    if entry["label"] == "player":
                        try:
                            process.wait(timeout=10)
                        except subprocess.TimeoutExpired:
                            entry["hang_diagnostics"] = str(out / "player-hang-diagnostics.json")
                            save(out / "player-hang-diagnostics.json", thread_snapshot(process.pid))
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
    parser.add_argument("--guard", choices=("observe", "scenario", "calibration", "reset", "batch"),
                        help="SIM1-02: launch the guarded interlocked player with a supervisor stand-in; "
                             "observe forwards zero requests for --duration, scenario runs the disarmed P1a cases; "
                             "calibration forwards a confirmed motion stage's requests (requires --motion-stage)")
    parser.add_argument("--stack-profile", choices=sorted(AVLITE_MOTION_STAGES), default=None, help=argparse.SUPPRESS)
    parser.add_argument("--f1-case", choices=F1_CASES, default=None,
                        help="S1-06 F1 fault case (M1 protocol v0.1); motion stage m6 only")
    parser.add_argument("--f2-case", choices=F2_CASES, default=None,
                        help="S2 F2 fault case (proposal v0.1 section 5, D23); --guard batch with stage m6 only")
    parser.add_argument("--freeze-trigger", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--episodes", type=int, default=1,
                        help="S2 batch (--guard batch): episodes in this player, GUI Reset between them (D20 A)")
    parser.add_argument("--ui-reference", type=Path, default=None,
                        help="S2 (D21 A): reviewed roboracer.ui-reference/1 record; replaces the per-Connect review")
    parser.add_argument("--record-inputs", action="store_true",
                        help="S2-03: record every raw message the plugin bridge processes (plugin-inputs.jsonl)")
    parser.add_argument("--sim-hang-test", type=float, default=None,
                        help="Test only (no motion stage): SIGSTOP the player this many seconds after observation start")
    parser.add_argument("--record-video", action="store_true",
                        help="Record only the AutoDRIVE window (ffmpeg x11grab) from Connect to cleanup")
    parser.add_argument("--motion-stage", choices=sorted(MOTION_STAGES) + sorted(AVLITE_MOTION_STAGES),
                        help="Confirmed motion-protocol stage (v0.1: m0 only, steering with throttle 0). Passes "
                             "-roboracerMotionAuthorized; requires the approval record and a SIM1-03 build record")
    parser.add_argument("--m2-case", choices=("a", "b"),
                        help="M2 stop case: a = algorithm hang (source silent after one 0.01 request), "
                             "b = runner loss (heartbeats stop while 0.01 is requested)")
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
    if args.record_inputs and args.mode in ("run", "plugin-observe") and \
            not (args.plugin_stack or args.plugin_observer or args.motion_stage in AVLITE_MOTION_STAGES
                 or args.mode == "plugin-observe"):
        parser.error("--record-inputs needs the plugin bridge (--plugin-stack, --plugin-observer or an AVLite stage)")
    if args.f2_case and args.mode == "run" and not (args.guard == "batch" and args.motion_stage == "m6"):
        parser.error("--f2-case runs only in an S2 batch on stage m6 (D22, D23)")
    if args.f2_case and args.f1_case:
        parser.error("one fault case per run")
    if args.sim_hang_test is not None and (args.motion_stage or args.mode != "run" or args.sim_hang_test <= 0):
        parser.error("--sim-hang-test is a stationary (no motion stage) run-mode test with a positive delay")
    if args.f1_case:
        # S1-06 M1 protocol v0.1 (D14): F1 cases run only in the approved M6 envelope.
        if args.mode == "run" and args.motion_stage != "m6":
            parser.error("--f1-case requires --motion-stage m6")
        if args.f1_case == "f1-1" and args.mode == "run":
            # Stage-triggered LiDAR freeze; the runner passes the explicit flags on to its bridge child.
            args.freeze_test, args.freeze_trigger = "lidar", True
    elif args.freeze_trigger:
        parser.error("--freeze-trigger is only for F1-1")
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
    if args.guard and (not args.provenance or (args.freeze_test and not args.freeze_trigger) or
                       not all(math.isfinite(v) and v > 0 for v in (args.guard_timeout, args.disconnect_wait))):
        parser.error("Guard trials require --provenance, no freeze test, and positive finite bounds")
    if args.freeze_test and not (len(args.freeze_window) == 2 and 0 < args.freeze_window[0] < args.freeze_window[1]
                                 and args.freeze_window[1] + 5 <= args.duration):
        parser.error("Freeze window must be ordered and end at least 5 s before the observation ends")
    if args.guard == "batch" and args.mode == "run" and not (
            args.episodes >= 1 and args.ui_reference and (args.motion_stage == "m6" or args.plugin_stack)):
        parser.error("--guard batch needs --episodes >= 1, --ui-reference and either --motion-stage m6 or --plugin-stack")
    if args.episodes != 1 and args.guard != "batch" and args.mode in ("run", "bridge"):
        parser.error("--episodes is for --guard batch")
    if args.plugin_stack and (args.guard not in ("observe", "reset", "batch") or args.plugin_observer):
        parser.error("The plugin stack runs only with --guard observe and replaces --plugin-observer")
    if args.plugin_observer and not args.provenance:
        parser.error("The plugin observer needs the provenance topic (--provenance)")
    if (args.motion_stage == "m2") != bool(args.m2_case) and args.mode in ("run", "calibrate"):
        parser.error("--m2-case is required for, and only for, stage m2")
    if args.mode == "run" and (bool(args.motion_stage) != (args.guard in ("calibration", "batch")) and
                               not (args.guard == "batch" and args.plugin_stack and not args.motion_stage)):
        parser.error("--motion-stage needs --guard calibration or batch (batch also runs stationary with --plugin-stack)")
    if args.guard == "batch" and args.motion_stage and args.motion_stage != "m6":
        parser.error("S2 batches run only the M6 envelope (D22)")
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
                not args.player or relocated_path(built) != str(args.player.resolve()):
            parser.error("Motion stages need the player's own build record with vendor-sim1-03 (D1)")
        for name, path in (("GameAssembly.so", args.player.resolve().parent / "GameAssembly.so"),
                           ("AutoDRIVE.x86_64", args.player.resolve())):
            # Identity by content; this also covers a relocated player (see relocated_path).
            if hashlib.sha256(path.read_bytes()).hexdigest() != build["output_files"].get(name, {}).get("sha256"):
                parser.error(f"Player {name} differs from its build record")
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
