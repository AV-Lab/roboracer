#!/usr/bin/env python3
"""Bounded input recording and open-loop replay for the AutoDRIVE plugin stack (S2-03).

Recording. ``InputRecorder`` is installed as ``AutoDriveBridge.message_listener``. It writes
every raw Devkit message, in the order the bridge processed it and with the bridge's arrival
time, to ``plugin-inputs.jsonl`` (schema ``roboracer.inputs/1``). Scan ranges are stored as
base64 float32, exactly as published. The other fields are JSON floats and ints, which round-trip
exactly. The file is bounded: past ``max_bytes`` nothing more is written and the recording is
marked truncated.

Replay. This is **open-loop**: recorded inputs drive the code, and the code's outputs never feed
back into the simulator. It is never a lap and never counts as one.
- ``snapshots``: feed the recorded messages into a fresh ``SnapshotAssembler`` (the plugin's own
  code) and compare every committed snapshot with the live ``plugin-snapshots.jsonl``.
- ``controller``: for every live tick, rebuild the sensor frame from the snapshot that tick used,
  through ``AutoDriveBridge.get_sensor_frame``, and run the same controller class with the same
  parameters. Compare target speed and steer with the live tick.

Tolerance (D24, proposed): exact equality on this host and environment.

Usage:
  roboracer_inputs.py replay   --run RUN_DIR --plugin PLUGIN_DIR --output FRESH.json
  roboracer_inputs.py fixtures --plugin PLUGIN_DIR --output FRESH.json
Both import the plugin through AVLite's plugin loader, so run them with the AVLite interpreter.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import sys
import threading
from pathlib import Path
from types import SimpleNamespace as NS

SCHEMA = "roboracer.inputs/1"
MAX_BYTES = 64 * 1024 * 1024  # proposed per-episode bound; a lap is about 6 MB


# -- encoding (no NumPy or ROS needed to record) -----------------------------------------------
def _header(message) -> dict:
    return {"sec": int(message.header.stamp.sec), "nanosec": int(message.header.stamp.nanosec),
            "frame_id": str(message.header.frame_id)}


def _xyz(v) -> list:
    return [float(v.x), float(v.y), float(v.z)]


def encode(topic: str, message, now_ns: int) -> dict:
    """One raw message as a JSON-ready record."""
    record = {"t": int(now_ns), "topic": topic}
    if topic == "provenance":
        record["data"] = str(message.data)
    elif topic == "lidar":
        import array
        ranges = message.ranges
        if isinstance(ranges, array.array) and ranges.typecode == "f":
            raw = ranges.tobytes()
        else:
            raw = array.array("f", [float(r) for r in ranges]).tobytes()
        if sys.byteorder != "little":
            raise RuntimeError("recording assumes a little-endian host")
        record.update(header=_header(message), angle_min=float(message.angle_min),
                      angle_increment=float(message.angle_increment),
                      ranges_f32=base64.b64encode(raw).decode("ascii"))
    elif topic == "imu":
        o = message.orientation
        record.update(header=_header(message), orientation=[float(o.x), float(o.y), float(o.z), float(o.w)],
                      angular_velocity=_xyz(message.angular_velocity),
                      linear_acceleration=_xyz(message.linear_acceleration))
    elif topic in ("left_encoder", "right_encoder"):
        record.update(header=_header(message), position=[float(p) for p in message.position])
    elif topic == "ips":
        record["xyz"] = _xyz(message)
    else:
        raise ValueError(f"unknown topic {topic!r}")
    return record


def decode(record: dict):
    """(topic, duck-typed message, arrival ns): the fields SnapshotAssembler reads, nothing more."""
    import numpy as np
    topic = record["topic"]

    def header(h):
        return NS(stamp=NS(sec=h["sec"], nanosec=h["nanosec"]), frame_id=h["frame_id"])

    if topic == "provenance":
        message = NS(data=record["data"])
    elif topic == "lidar":
        ranges = np.frombuffer(base64.b64decode(record["ranges_f32"]), dtype="<f4")
        message = NS(header=header(record["header"]), angle_min=record["angle_min"],
                     angle_increment=record["angle_increment"], ranges=ranges)
    elif topic == "imu":
        message = NS(header=header(record["header"]), orientation=NS(**dict(zip("xyzw", record["orientation"]))),
                     angular_velocity=NS(**dict(zip("xyz", record["angular_velocity"]))),
                     linear_acceleration=NS(**dict(zip("xyz", record["linear_acceleration"]))))
    elif topic in ("left_encoder", "right_encoder"):
        message = NS(header=header(record["header"]), position=list(record["position"]))
    elif topic == "ips":
        message = NS(**dict(zip("xyz", record["xyz"])))
    else:
        raise ValueError(f"unknown topic {topic!r}")
    return topic, message, record["t"]


class InputRecorder:
    """Bridge ``message_listener``: writes each message as one JSON line, up to ``max_bytes``.

    Called on the bridge's transport thread under the bridge lock, so it only encodes and writes.
    """

    def __init__(self, path: Path, max_bytes: int = MAX_BYTES):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self._file = self.path.open("x", buffering=1 << 20)
        self._lock = threading.Lock()
        self.stats = {"schema": SCHEMA, "path": str(self.path), "max_bytes": max_bytes, "messages": 0,
                      "bytes": 0, "truncated": False, "by_topic": {}, "errors": 0}
        self._write({"schema": SCHEMA, "kind": "header"})

    def _write(self, record: dict) -> bool:
        line = json.dumps(record, separators=(",", ":")) + "\n"
        if self.stats["bytes"] + len(line) > self.max_bytes:
            self.stats["truncated"] = True
            return False
        self._file.write(line)
        self.stats["bytes"] += len(line)
        return True

    def __call__(self, topic: str, message, now_ns: int) -> None:
        with self._lock:
            if self._file.closed or self.stats["truncated"]:
                return
            try:
                record = encode(topic, message, now_ns)
            except Exception:  # never disturb the bridge; count it instead
                self.stats["errors"] += 1
                return
            if self._write(record):
                self.stats["messages"] += 1
                self.stats["by_topic"][topic] = self.stats["by_topic"].get(topic, 0) + 1

    def close(self) -> None:
        with self._lock:
            if not self._file.closed:
                self._file.flush()
                self._file.close()


def read_recording(path: Path) -> tuple[dict, list[dict]]:
    lines = Path(path).read_text().splitlines()
    head = json.loads(lines[0])
    if head.get("schema") != SCHEMA or head.get("kind") != "header":
        raise ValueError(f"{path} is not a {SCHEMA} recording")
    return head, [json.loads(line) for line in lines[1:] if line.strip()]


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


# -- replay ------------------------------------------------------------------------------------
def load_plugin(plugin_dir: Path):
    """The plugin package as AVLite loads it (``avlite.plugins.roboracer``)."""
    from avlite.c60_apps.c63_plugins import import_plugin_modules
    if "avlite.plugins.roboracer" not in sys.modules:
        import_plugin_modules(str(plugin_dir), pkg_name="roboracer")
    return sys.modules["avlite.plugins.roboracer"]


def scan_sha256(snapshot) -> str:
    import numpy as np
    return hashlib.sha256(np.ascontiguousarray(snapshot.scan_ranges).tobytes()).hexdigest()


def replay_snapshots(records: list[dict], plugin) -> tuple[list, dict]:
    """Recorded messages, in recorded order and arrival time, through a fresh assembler."""
    observation = sys.modules[plugin.__name__ + ".integration.autodrive_observation"]
    assembler = observation.SnapshotAssembler()
    snapshots = []
    for record in records:
        topic, message, now_ns = decode(record)
        if topic == "provenance":
            snapshots += assembler.offer_provenance(message.data, now_ns)
        else:
            snapshots += assembler.offer(topic, message, now_ns)
    return snapshots, {"committed": assembler.committed, "rejections": dict(assembler.rejections),
                       "dropped": assembler.dropped}


SNAPSHOT_FIELDS = ("telemetry_seq", "session", "episode", "committed_monotonic_ns", "scan_sha256", "points",
                   "pose", "encoders", "clock_bound_s", "scan_pose_skew_s", "lidar_stamp_s", "imu_stamp_s")


def snapshot_row(snapshot) -> dict:
    """The live ``plugin-snapshots.jsonl`` fields, computed the same way."""
    return {"telemetry_seq": snapshot.telemetry_seq, "session": snapshot.session, "episode": snapshot.episode,
            "committed_monotonic_ns": snapshot.committed_monotonic_ns, "scan_sha256": scan_sha256(snapshot),
            "points": len(snapshot.lidar.points),
            "pose": [snapshot.pose.x, snapshot.pose.y, snapshot.pose.z, snapshot.pose.yaw],
            "encoders": list(snapshot.encoder_angles_rad), "clock_bound_s": snapshot.clock_bound_s,
            "scan_pose_skew_s": snapshot.scan_pose_skew_s, "lidar_stamp_s": snapshot.lidar.stamp,
            "imu_stamp_s": snapshot.imu.stamp}


def compare_snapshots(snapshots: list, live: list[dict]) -> dict:
    replayed = [snapshot_row(s) for s in snapshots]
    mismatches = []
    for i, (a, b) in enumerate(zip(replayed, live)):
        diff = [k for k in SNAPSHOT_FIELDS if k in b and a[k] != b[k]]
        if diff:
            mismatches.append({"index": i, "telemetry_seq": b.get("telemetry_seq"), "fields": diff})
    return {"replayed": len(replayed), "live": len(live), "count_equal": len(replayed) == len(live),
            "mismatched": len(mismatches), "first_mismatches": mismatches[:5],
            "exact": len(replayed) == len(live) and not mismatches}


def make_controller(plugin, name: str, params: dict | None):
    module = sys.modules[plugin.__name__ + ".control." + {"GapFollowController": "gap_follow",
                                                            "HoldController": "hold",
                                                            "SpeedStepController": "speed_step"}[name]]
    controller = getattr(module, name)()
    if params is not None:
        controller.params = module.GapFollowParams(**params)
    return controller


def replay_controller(snapshots: list, ticks: list[dict], plugin, controller_name: str,
                      params: dict | None) -> dict:
    """Each live tick's command recomputed from the snapshot it used, through the bridge's
    sensor-frame path and the same controller class and parameters."""
    by_seq = {s.telemetry_seq: s for s in snapshots}
    bridge = plugin.AutoDriveBridge()
    controller = make_controller(plugin, controller_name, params)
    compared, mismatches, skipped = 0, [], {"no_snapshot": 0, "disabled_or_absent": 0}
    for i, tick in enumerate(ticks):
        live = tick.get("controller")
        if not isinstance(live, dict) or "reason" in live:
            skipped["disabled_or_absent"] += 1
            continue
        snapshot = by_seq.get(tick.get("telemetry_seq"))
        if snapshot is None:
            skipped["no_snapshot"] += 1
            continue
        bridge._snapshot = snapshot  # what the transport thread would have committed
        frame = bridge.get_sensor_frame()
        command = controller.control(bridge.get_ego_state(), sensors=frame)
        compared += 1
        got = (command.target_speed, command.steer)
        want = (live["target_speed"], live["steer"])
        if got != want:
            mismatches.append({"tick": i, "telemetry_seq": tick.get("telemetry_seq"), "replayed": got, "live": want,
                               "abs_diff": [abs(g - w) for g, w in zip(got, want)]})
    worst = max((max(m["abs_diff"]) for m in mismatches), default=0.0)
    return {"controller": controller_name, "params": params, "ticks": len(ticks), "compared": compared,
            "skipped": skipped, "mismatched": len(mismatches), "worst_abs_diff": worst,
            "first_mismatches": mismatches[:5], "exact": compared > 0 and not mismatches}


def replay_run(run: Path, plugin_dir: Path) -> dict:
    plugin = load_plugin(plugin_dir)
    head, records = read_recording(run / "plugin-inputs.jsonl")
    status = json.loads((run / "plugin-observer-status.json").read_text())
    snapshots, assembly = replay_snapshots(records, plugin)
    result = {"mode": "open-loop replay (not a live lap)", "run": str(run), "recording": head,
              "recording_status": status.get("input_recording"), "messages": len(records),
              "assembly": assembly, "snapshots": compare_snapshots(snapshots, rows(run / "plugin-snapshots.jsonl"))}
    ticks_path = run / "plugin-ticks.jsonl"
    ticks = rows(ticks_path) if ticks_path.exists() else []
    if not any(isinstance(t.get("controller"), dict) for t in ticks):
        # Stationary stack runs (no stage) do not record controller outputs: nothing to compare.
        result["controller"] = {"applicable": False, "ticks": len(ticks)}
    else:
        profile = status.get("stack_profile")
        name = {"m4": "SpeedStepController", "m5": "GapFollowController",
                "m6": "GapFollowController"}.get(profile, "HoldController")
        result["controller"] = replay_controller(snapshots, ticks, plugin, name, status.get("controller_params"))
    result["exact"] = result["snapshots"]["exact"] and result.get("controller", {}).get("exact", True)
    return result


# -- analytical fixtures -----------------------------------------------------------------------
def corridor_ranges(half_width: float, beams: int = 1081):
    """A straight, infinitely long corridor centred on the sensor: r = w / |sin(theta)|,
    beyond 10 m reported as inf (no return)."""
    out = []
    for i in range(beams):
        theta = math.radians(-135.0) + math.radians(0.25) * i
        s = abs(math.sin(theta))
        r = half_width / s if s > 1e-12 else math.inf
        out.append(r if r <= 10.0 else math.inf)
    return out


def opening_ranges(radius: float, lo_deg: float, hi_deg: float, beams: int = 1081):
    """A ring of ``radius`` with no return (inf) for beams in [lo_deg, hi_deg]."""
    out = []
    for i in range(beams):
        deg = -135.0 + 0.25 * i
        out.append(math.inf if lo_deg - 1e-9 <= deg <= hi_deg + 1e-9 else radius)
    return out


def _opening_expected():
    """Ring 1.0 m with a no-return opening at +20..+80 deg (A parameters).

    Beams with no return are exactly 10 m in the controller, so the deepest set is an exact tie.
    Disparity extension at the +20 deg edge (near = 1.0 m) covers ceil(atan2(0.25, 1.0) / 0.25 deg)
    = 57 beams, i.e. +20.00..+34.00 deg; the straightest remaining 10 m beam is +34.25 deg.
    steer = atan2(2 L sin(alpha), l_d) with L = 0.324 m, l_d = 1 m; front (+-10 deg) = 1.0 m, so
    speed = min(0.3, 0.3 (1 - |steer| / 0.6), 0.25 (1.0 - 0.5)).
    """
    alpha = math.radians(20.0 + 0.25 * math.ceil(math.degrees(math.atan2(0.25, 1.0)) / 0.25))
    steer = math.atan2(2 * 0.324 * math.sin(alpha), 1.0)
    return min(0.3, 0.3 * (1 - abs(steer) / 0.6), 0.25 * (1.0 - 0.5)), steer


# Points are float32 (the plugin's LiDAR frame), so finite ranges carry ~1e-7 relative rounding;
# the analytical tolerance follows that representation. Live replay is held to exact equality.
FIXTURE_TOL = 1e-6
FIXTURES = {
    # name: (ranges, expected (target speed, steer or None if not determined), derivation)
    "symmetric corridor 1.0 m": (lambda: corridor_ranges(1.0), (0.3, 0.0),
                                 "mirror-symmetric; beams beyond 10 m have no return, so the deepest set is an "
                                 "exact tie around 0 deg and the straightest wins (alpha 0); front 5.76 m, so the "
                                 "speed is the 0.3 m/s cap"),
    "opening +20..+80 deg in a 1.0 m ring": (lambda: opening_ranges(1.0, 20.0, 80.0), _opening_expected(),
                                             _opening_expected.__doc__.strip()),
    "dead end 0.45 m ring": (lambda: [0.45] * 1081, (0.0, None),
                             "front 0.45 m < 0.5 m: speed floored at 0. Steer is not determined: equal finite "
                             "ranges tie only up to float32 rounding, so it is not checked"),
}


def fixture_records(ranges, frames: int = 3) -> list[dict]:
    """A synthetic recording: ``frames`` telemetry frames with the given scan, recorded through
    ``encode`` exactly as the live recorder would."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "roboracer" / "tests"))
    import s1_02_fixtures as fx
    out, now = [], 1_000_000_000
    for seq in range(1, frames + 1):
        messages, provenance = fx.frame(seq, ranges=ranges)
        for name, message in messages.items():
            out.append(encode(name, message, now))
            now += 1000
        out.append(encode("provenance", NS(data=provenance), now))
        now += 1000
    return out


def run_fixtures(plugin_dir: Path) -> dict:
    plugin = load_plugin(plugin_dir)
    results = {}
    for name, (make, expected, why) in FIXTURES.items():
        records = json.loads(json.dumps(fixture_records(make())))  # through the JSON file format
        snapshots, assembly = replay_snapshots(records, plugin)
        bridge = plugin.AutoDriveBridge()
        controller = make_controller(plugin, "GapFollowController", None)  # baseline A
        outputs = []
        for snapshot in snapshots:
            bridge._snapshot = snapshot
            command = controller.control(bridge.get_ego_state(), sensors=bridge.get_sensor_frame())
            outputs.append((command.target_speed, command.steer))
        ok = len(snapshots) == 3 and all(
            math.isclose(s, expected[0], abs_tol=FIXTURE_TOL) and
            (expected[1] is None or math.isclose(a, expected[1], abs_tol=FIXTURE_TOL)) for s, a in outputs)
        results[name] = {"why": why, "expected": expected, "outputs": outputs, "snapshots": len(snapshots),
                         "assembly": assembly, "pass": ok}
    return {"mode": "analytical fixtures (open-loop)", "fixtures": results,
            "pass": all(r["pass"] for r in results.values())}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    rp = sub.add_parser("replay")
    rp.add_argument("--run", type=Path, required=True, help="run-01 directory with plugin-inputs.jsonl")
    fx = sub.add_parser("fixtures")
    for p in (rp, fx):
        p.add_argument("--plugin", type=Path, required=True, help="the roboracer plugin directory")
        p.add_argument("--output", type=Path, required=True, help="fresh JSON report")
    args = parser.parse_args(argv)
    result = replay_run(args.run, args.plugin) if args.command == "replay" else run_fixtures(args.plugin)
    with args.output.open("x") as f:
        json.dump(result, f, indent=1, default=float)
    ok = result["exact"] if args.command == "replay" else result["pass"]
    print(json.dumps({"output": str(args.output), "pass": ok}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
