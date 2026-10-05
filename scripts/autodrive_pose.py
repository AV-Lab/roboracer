"""Explicit statement-level diagnostic preparation and retained-trace analysis."""
import hashlib
import json
import math
import struct

CONTROLLER_SHA256 = "3f0ba69aca6449c351442c25ec84694a5becb05197b66928948f378ae2ea4322"
MARKER = " // RoboRacer pose observation"
LAYOUT = "<qqiiiqdd37fiiff"
STAGES = [(i, -1) for i in range(7)] + [(i, w) for w in range(4) for i in range(10, 18)] + [(7, -1), (8, -1)]


def patch_controller(original):
    """Add marker lines only to the reviewed exact vendor file; never replace a statement."""
    if hashlib.sha256(original).hexdigest() != CONTROLLER_SHA256:
        raise ValueError("Controller differs from the pinned reviewed source")
    lines = original.decode("utf-8").splitlines(keepends=True)
    before = {259: (10, True), 261: (11, True), 262: (13, True), 263: (15, True),
              268: (0, False), 271: (2, False), 272: (4, False), 275: (6, False)}
    after = {261: [(12, True)], 262: [(14, True)], 263: [(16, True), (17, True)],
             268: [(1, False)], 271: [(3, False)], 272: [(5, False)], 275: [(7, False), (8, False)]}
    def marker(stage, wheel):
        return "        RoboRacer.Qualification.PoseTrace.Mark(this, " + str(stage) + (", _collider, _transform" if wheel else "") + ");" + MARKER + "\n"
    result=[]
    for n,line in enumerate(lines,1):
        if n in before: result.append(marker(*before[n]))
        result.append(line)
        for item in after.get(n,[]):result.append(marker(*item))
    patched="".join(result).encode("utf-8")
    if b"".join(l for l in patched.splitlines(keepends=True) if not l.rstrip().endswith(MARKER.encode())) != original:
        raise ValueError("Pose instrumentation changed an original statement")
    return patched


def check_status(state, start=None, end=None, closed=False):
    keys = ("pose_bytes", "pose_records", "pose_steps", "pose_pending_stage", "pose_first_ns", "pose_last_ns",
            "pose_total_capture_ns", "pose_max_capture_ns")
    if (state.get("pose_schema"), state.get("pose_record_bytes"), state.get("pose_stages_per_step")) != (1, 216, 41):
        raise RuntimeError("Missing or incompatible pose trace status")
    if any(type(state.get(k)) is not int or state[k] < 0 for k in keys):
        raise RuntimeError("Malformed pose counters")
    if state["trace_bytes"] + state["contact_bytes"] + state["pose_bytes"] > 1024**3:
        raise RuntimeError("Combined pose trace exceeded 1 GiB")
    if state["pose_records"] != state["pose_steps"] * 41 + state["pose_pending_stage"] or state["pose_pending_stage"] >= 41:
        raise RuntimeError("Pose record and step counters disagree")
    if start is None:
        if state["pose_records"]:
            raise RuntimeError("Pose records exist before the observation request")
    elif end is None or not 0 < end-start <= 10_000_000_000:
        raise RuntimeError("Invalid pose window bounds")
    elif state["pose_records"] and not start <= state["pose_first_ns"] <= state["pose_last_ns"]:
        raise RuntimeError("Pose samples precede the requested window")
    if closed and (not state.get("pose_window_complete") or not state["pose_steps"] or state["pose_pending_stage"]):
        raise RuntimeError("Incomplete pose tracing window")


def record_dtype():
    import numpy as np
    fields = [("index", "<i8"), ("step", "<i8"), ("stage", "<i4"), ("wheel", "<i4"), ("frame", "<i4"),
              ("monotonic_ns", "<i8"), ("fixed_time", "<f8"), ("time", "<f8")]
    for name, size in [("body_position", 3), ("body_position_repeat", 3), ("body_rotation", 4), ("root_position", 3),
                       ("root_rotation", 4), ("velocity", 3), ("angular_velocity", 3), ("center_of_mass", 3),
                       ("inertia_tensor", 3), ("inertia_rotation", 4), ("mass", 1), ("body_position_after_reads", 3)]:
        fields.append((name, "<f4", (size,)))
    fields += [("recorder_flags", "<i4"), ("driving_mode", "<i4"), ("throttle", "<f4"), ("steering", "<f4")]
    dtype = np.dtype(fields)
    assert dtype.itemsize == struct.calcsize(LAYOUT) == 216
    return dtype


def summarize_records(data):
    """Validate all stages and exactly account for the observed pose changes."""
    import numpy as np
    if not len(data) or len(data) % len(STAGES):
        raise ValueError("Partial or absent pose step")
    n = len(data) // len(STAGES)
    matrix = data.reshape(n, len(STAGES))
    for field, expected in [("index", np.arange(len(data))), ("step", np.repeat(np.arange(n), 41)),
                            ("stage", np.tile([s for s, _ in STAGES], n)), ("wheel", np.tile([w for _, w in STAGES], n))]:
        if not np.array_equal(data[field], expected):
            raise ValueError("Missing, reordered or inconsistent pose " + field)
    for name in data.dtype.names:
        if not np.isfinite(data[name]).all():
            raise ValueError("Nonfinite pose field " + name)
    if np.any(np.diff(data["monotonic_ns"]) <= 0):
        raise ValueError("Non-increasing pose timestamps")
    if any(np.any(data[k] != 0) for k in ("recorder_flags", "driving_mode", "throttle", "steering")):
        raise ValueError("Pose recorder or control guard violated")
    if not np.all(matrix["fixed_time"] == matrix["fixed_time"][:, :1]) or not np.all(matrix["frame"] == matrix["frame"][:, :1]):
        raise ValueError("Pose stages crossed a physics step or frame")
    if n > 1 and not np.allclose(np.diff(matrix["fixed_time"][:, 0]), .0010000000474974513, rtol=0, atol=1e-9):
        raise ValueError("Missing or duplicate fixed pose sample")
    p = data["body_position"].astype(np.float64)
    after = data["body_position_after_reads"].astype(np.float64)
    read_delta = after-p
    gaps = p[1:]-after[:-1]
    within = data["step"][1:] == data["step"][:-1]
    endpoint = after[-1]-p[0]
    decomposition = read_delta.sum(axis=0) + gaps[within].sum(axis=0) + gaps[~within].sum(axis=0)
    if not np.array_equal(endpoint, decomposition):
        raise ValueError("Pose transition accounting does not close")
    def describe(values):
        values = np.asarray(values, dtype=np.float64)
        return {"count": len(values), "sum_xyz_m": values.sum(axis=0).tolist(),
                "min_xyz_m": values.min(axis=0).tolist() if len(values) else None,
                "max_xyz_m": values.max(axis=0).tolist() if len(values) else None,
                "nonzero_Z_count": int(np.count_nonzero(values[:, 2])) if len(values) else 0}
    intervals = {}
    for j in range(40):
        before_stage, wheel = STAGES[j]
        after_stage, after_wheel = STAGES[j+1]
        idx = np.arange(j, len(data)-1, 41)
        key = f"{before_stage}:{wheel} -> {after_stage}:{after_wheel}"
        intervals[key] = {"gap_excluding_prior_read_effect": describe(gaps[idx]),
                          "gross_start_to_start": describe(p[idx+1]-p[idx])}
    return {"records": len(data), "steps": n, "all_stages_valid": True, "endpoint_accounting_exact": True,
            "window_first_last_monotonic_ns": [int(data["monotonic_ns"][0]), int(data["monotonic_ns"][-1])],
            "first_last_fixed_time": [float(matrix["fixed_time"][0, 0]), float(matrix["fixed_time"][-1, 0])],
            "body_endpoint_delta_xyz_m": endpoint.tolist(),
            "checkpoint_read_effect": describe(read_delta),
            "immediate_repeat_read_effect": describe(data["body_position_repeat"].astype(np.float64)-p),
            "within_step_gaps": describe(gaps[within]), "between_step_gaps": describe(gaps[~within]),
            "intervals": intervals, "all_recorder_and_control_fields_zero": True,
            "mass_range_kg": [float(data["mass"].min()), float(data["mass"].max())],
            "COM_range_m": [data["center_of_mass"].min(axis=0).tolist(), data["center_of_mass"].max(axis=0).tolist()]}


def analyze_pose(directory, run):
    import numpy as np
    from pathlib import Path
    directory = Path(directory)
    if not run.get("completed_diagnostic_window"):
        return {"available": False, "reason": "Retained incomplete live attempt; no complete pose-window claim"}
    binding = json.loads((directory / "pose-binding.json").read_text())
    status = json.loads((directory / "status.json").read_text())
    check_status(status, run["observation_start_ns"], run["diagnostic_deadline_ns"], closed=True)
    if (binding.get("schema"), binding.get("record_bytes"), binding.get("stages_per_step"), binding.get("layout"),
            binding.get("clock"), binding.get("pid")) != (1, 216, 41, LAYOUT, "Linux CLOCK_MONOTONIC", status["pid"]):
        raise ValueError("Pose binding does not match the trial")
    expected_paths = ["F1TENTH/Vehicle/"+name+" Wheel" for name in ("FL", "FR", "RL", "RR")]
    if [b["path"] for b in binding["wheel_bindings"]] != expected_paths:
        raise ValueError("Unexpected pose transform bindings")
    binary = directory / "pose.bin"
    if binary.stat().st_size != status["pose_records"]*216 or binary.stat().st_size+(directory/"pose-binding.json").stat().st_size != status["pose_bytes"]:
        raise ValueError("Truncated or mismatched pose bytes")
    data = np.memmap(binary, dtype=record_dtype(), mode="r")
    result = summarize_records(data)
    if result["steps"] != status["pose_steps"]:
        raise ValueError("Pose step count differs from status")
    steps = data.reshape(-1, 41)
    if np.any(steps["monotonic_ns"][:, 0] >= run["diagnostic_deadline_ns"]):
        raise ValueError("Pose step started after the deadline")
    result.update({"available": True, "binding": binding, "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "trace_bytes": status["pose_bytes"], "total_capture_ns": status["pose_total_capture_ns"],
        "max_capture_ns": status["pose_max_capture_ns"],
        "activation_delay_ms": (status["pose_first_ns"]-run["observation_start_ns"])/1e6,
        "last_record_offset_from_deadline_ms": (status["pose_last_ns"]-run["diagnostic_deadline_ns"])/1e6,
        "limits": ["Brackets localize observed changes; getters and instrumentation can affect native synchronization.",
                   "Between-controller intervals include physics and other callbacks; native solver internals are not traced.",
                   "A final in-flight callback is recorded completely even if it ends just beyond the wall deadline."]})
    return result
