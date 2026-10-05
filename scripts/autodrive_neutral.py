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
import time


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


SIM1_REPLY_FIELDS = {"RR Ping Mono", "RR Test Freeze"}


def check_zero_reply(event, data):
    controls = {"V1 Throttle", "V1 Steering"}
    if event != "Bridge" or not controls <= set(data) or not set(data) - controls <= SIM1_REPLY_FIELDS:
        raise ValueError("Unexpected outbound event or command fields")
    if any(float(data[key]) != 0.0 for key in controls):
        raise ValueError("Nonzero/nonfinite control blocked")
    if "RR Ping Mono" in data and not data["RR Ping Mono"].isdigit():
        raise ValueError("Malformed provenance ping")
    from autodrive_provenance import FREEZABLE
    if any(kind and kind not in FREEZABLE for kind in data.get("RR Test Freeze", "").split(",")):
        raise ValueError("Unsupported test-hook request")


def motion_fields(data):
    result = {}
    for key, count in (("Position", 3), ("Encoder Angles", 2), ("Encoder Ticks", 2),
                       ("Orientation Quaternion", 4), ("Orientation Euler Angles", 3),
                       ("Angular Velocity", 3), ("Linear Acceleration", 3)):
        values = [float(v) for v in data["V1 " + key].split()]
        if len(values) != count or not all(math.isfinite(v) for v in values):
            raise ValueError("Malformed/nonfinite " + key)
        result[key] = values
    for key in ("Throttle", "Steering"):
        if float(data["V1 " + key]) != 0.0:
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

    def guarded_emit(event, data=None, **kwargs):
        check_zero_reply(event, data)
        gevent.sleep(args.reply_delay)
        if tracker is not None:
            data = dict(data)
            request = freeze_request()
            if request is not None:
                data["RR Test Freeze"] = request
            data["RR Ping Mono"] = tracker.clock.ping(time.monotonic_ns())  # stamped at send time
            check_zero_reply(event, data)
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
            motion = motion_fields(data)
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
            raw_bridge(sid, data)  # Official conversion/publishing; guarded zero-only reply.
            if tracker is not None:
                from std_msgs.msg import String
                if provenance_publisher is None:
                    provenance_publisher = incoming.autodrive_incoming_bridge.create_publisher(
                        String, "/autodrive/f1tenth_1/provenance", 10)
                message = String()
                message.data = json.dumps({"session": tracker.session, **provenance,
                                           "stamp_basis": row["stamp_basis"]})
                provenance_publisher.publish(message)
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
        reports.append({"run": directory.name, "completed_observation": run.get("completed_observation", False),
            "provenance": provenance,
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
              "freeze_window_seconds_after_first_frame": args.freeze_window if args.freeze_test else None}

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
        spawn("bridge", [context["devkit_python"], "-B", own_script, "bridge", "--results", str(out),
                         "--reply-delay", str(args.reply_delay), "--profile", args.profile, *sim1], bridge_environment)
        spawn("observer", [context["avlite_python"], "-B", own_script, "observe", "--results", str(out),
                           *(["--provenance"] if args.provenance else [])], environment)
        deadline = time.monotonic() + 15
        while not (read(out / "bridge-status.json").get("ready") and read(out / "observer-status.json").get("ready")):
            if any(p.poll() is not None for p, _, _ in children) or time.monotonic() > deadline:
                raise RuntimeError("Bridge/observer startup failed")
            time.sleep(0.1)
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

        reviewed, connected, observation_start = False, False, None
        sample_at = 0
        with (out / "resources.jsonl").open("w", buffering=1) as metrics:
            while time.monotonic() - started < args.startup_timeout + args.duration + 15:
                if any(p.poll() is not None for p, _, _ in children):
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
                        if approval.get("pid") != player.pid or approval.get("window_id") != window.id or approval.get("mode") != "Manual":
                            raise RuntimeError("UI review does not match this owned Manual-mode window")
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
                target = observation_start + int(args.duration * 1e9) if observation_start else None
                if target and args.profile == "drift-diagnostic" and time.monotonic_ns() >= target:
                    record.update(completed_diagnostic_window=True, diagnostic_deadline_ns=target,
                                  observation_end_ns=time.monotonic_ns(),
                                  bridge_at_end=bridge_state, observer_at_end=observer_state)
                    if window is not None:
                        capture(window, "ui-completed")
                    break  # End by wall time, including stalled streams; analyze their coverage separately.
                if target and args.profile in ("p0", "p0-creep") and bridge_state.get("last_received_ns", 0) >= target and all(observer_state.get("last_received_ns", {}).get(t, 0) >= target for t in TOPICS):
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
    if not record["endpoint_released"] or any(e["exit_code"] != 0 for e in record["children"]):
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
    parser.add_argument("mode", choices=("run", "bridge", "observe", "analyze"))
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
                        help="SIM1-01: validate roboracer.sim1/1 provenance, restamp headers, publish provenance topic")
    parser.add_argument("--freeze-test", choices=("lidar", "ips"),
                        help="SIM1-01 P1a: launch with test hooks and freeze one source in --freeze-window")
    parser.add_argument("--freeze-window", default="10,15",
                        type=lambda text: tuple(float(v) for v in text.split(",")),
                        help="Freeze start,end seconds after the bridge's first frame")
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
    if args.freeze_test and not (len(args.freeze_window) == 2 and 0 < args.freeze_window[0] < args.freeze_window[1]
                                 and args.freeze_window[1] + 5 <= args.duration):
        parser.error("Freeze window must be ordered and end at least 5 s before the observation ends")
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
