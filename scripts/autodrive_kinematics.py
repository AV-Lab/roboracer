"""Offline full-precision trace analysis, called by autodrive_neutral.py analyze."""
import hashlib
import json
from pathlib import Path


def analyze_trace(directory, start_ns, end_ns, frames, plot=None):
    import numpy as np

    path = directory / "samples.jsonl"
    if not path.exists() or start_ns is None or end_ns is None:
        return {"available": False, "reason": "No trace or complete observation interval"}

    def invalid(value):
        raise ValueError("Nonfinite trace constant: " + value)

    with path.open() as stream:
        rows = [json.loads(line, parse_constant=invalid) for line in stream]
    header, samples = rows[0], rows[1:]
    if header.get("kind") != "binding" or header.get("clock") != "Linux CLOCK_MONOTONIC":
        raise ValueError("Unexpected trace binding or clock")
    if any(r.get("kind") != "sample" or r.get("index") != i for i, r in enumerate(samples)):
        raise ValueError("Trace sequence is incomplete or reordered")
    if any(b["monotonic_ns"] <= a["monotonic_ns"] for a, b in zip(samples, samples[1:])):
        raise ValueError("Non-increasing trace clock")
    unknown = {r["phase"] for r in samples} - {"FixedUpdate", "LateUpdate"}
    if unknown:
        raise ValueError("Unexpected trace phase")
    selected = [r for r in samples if start_ns <= r["monotonic_ns"] <= end_ns]
    if len(selected) < 2:
        raise ValueError("Insufficient in-window diagnostic records")

    def values(records, section, field):
        result = np.asarray([r[section][field] for r in records], dtype=np.float64)
        if not np.isfinite(result).all():
            raise ValueError("Nonfinite numeric trace")
        return result

    def motion(records, section, field="position"):
        points = values(records, section, field)
        dt = np.asarray([(r["monotonic_ns"] - records[0]["monotonic_ns"]) / 1e9 for r in records])
        delta = points - points[0]
        return {"first": points[0].tolist(), "last": points[-1].tolist(),
                "delta_xyz_m": delta[-1].tolist(),
                "axis_span_m": np.ptp(points, axis=0).tolist(),
                "max_displacement_m": float(np.linalg.norm(delta, axis=1).max()),
                "linear_fit_xyz_m_per_s": np.polyfit(dt, points, 1)[0].tolist()}

    def bounds(array):
        array = np.asarray(array, dtype=np.float64)
        if not np.isfinite(array).all():
            raise ValueError("Nonfinite numeric diagnostic value")
        return {"min": np.min(array, axis=0).tolist(), "median": np.median(array, axis=0).tolist(),
                "max": np.max(array, axis=0).tolist()}

    phases = {}
    for phase in ("FixedUpdate", "LateUpdate"):
        r = [s for s in selected if s["phase"] == phase]
        if len(r) < 2:
            raise ValueError("Missing diagnostic phase: " + phase)
        body = values(r, "body", "position")
        axle = values(r, "axle", "position")
        root = values(r, "root", "position")
        ips = np.asarray([s["ips"] for s in r], dtype=np.float64)
        mapped_axle = axle[:, [2, 0, 1]] * [1, -1, 1]
        wheels = []
        for i in range(4):
            wheel = [s["wheels"][i] for s in r]
            contact = [w for w in wheel if w["grounded"]]
            entry = {"name": header["wheel_order"][i], "grounded_fraction": len(contact)/len(wheel)}
            for key in ("rpm", "motor_torque", "brake_torque", "steer_angle"):
                entry[key] = bounds([w[key] for w in wheel])
            for key in ("force", "forward_slip", "sideways_slip"):
                entry[key] = bounds([w[key] for w in contact]) if contact else None
            wheels.append(entry)
        elapsed = (r[-1]["monotonic_ns"] - r[0]["monotonic_ns"]) / 1e9
        phases[phase] = {
            "samples": len(r), "span_seconds": elapsed, "callback_rate_hz": (len(r)-1)/elapsed,
            "body_position": motion(r, "body"), "root_position": motion(r, "root"),
            "axle_position": motion(r, "axle"), "axle_local_position": motion(r, "axle", "local_position"),
            "body_velocity_xyz_m_per_s": bounds(values(r, "body", "velocity")),
            "body_speed_m_per_s": bounds(np.linalg.norm(values(r, "body", "velocity"), axis=1)),
            "body_angular_velocity_rad_per_s": bounds(values(r, "body", "angular_velocity")),
            "body_rotation_xyzw": bounds(values(r, "body", "rotation")),
            "root_minus_body_xyz_m": bounds(root - body),
            "ips_minus_current_axle_m": bounds(ips - mapped_axle),
            "body_sleeping_fraction": sum(s["body"]["sleeping"] for s in r)/len(r),
            "throttle": bounds([s["throttle"] for s in r]), "steering": bounds([s["steering"] for s in r]),
            "wheels": wheels}
        if "contact_state" in r[0]:
            states = [s["contact_state"] for s in r]
            mode = states[0]["mode"]
            if mode not in ("control", "treatment") or any(s["mode"] != mode for s in states):
                raise ValueError("Inconsistent contact mode")
            for s in states:
                if s["ignored"] != [mode == "treatment" and s["activation_ns"] > 0]*4:
                    raise ValueError("Unexpected contact-pair state")
            prop = {key: bounds([s["properties"][key] for s in states]) for key in
                    ("mass", "center_of_mass", "inertia_tensor", "inertia_rotation")}
            phases[phase]["contact_state"] = {"mode": mode, "properties_bounds": prop,
                "properties_constant": all(v["min"] == v["max"] for v in prop.values()),
                "mass_com_constant": all(prop[k]["min"] == prop[k]["max"] for k in ("mass", "center_of_mass")),
                "first_properties": states[0]["properties"],
                "activation_values_ns": sorted({s["activation_ns"] for s in states})}
            for i, entry in enumerate(wheels):
                entry["ground_collider_ids"] = sorted({s["wheels"][i]["collider_id"] for s in r if s["wheels"][i]["grounded"]})

    raw_window = [f for f in frames if start_ns <= f["received_monotonic_ns"] <= end_ns]
    fixed = [r for r in selected if r["phase"] == "FixedUpdate"]
    # This is a content/receipt-neighborhood comparison, never an acquisition identity.
    trace_times = np.asarray([r["monotonic_ns"] for r in fixed], dtype=np.int64)
    formatted = [tuple(float(format(v, ".3f")) for v in r["ips"]) for r in fixed]
    matches = 0
    for frame in raw_window:
        lo = int(np.searchsorted(trace_times, frame["received_monotonic_ns"] - 500_000_000))
        hi = int(np.searchsorted(trace_times, frame["received_monotonic_ns"] + 500_000_000, side="right"))
        matches += tuple(frame["motion"]["Position"]) in formatted[lo:hi]
    status = json.loads((directory / "status.json").read_text())
    if status["samples"] != len(samples) or status["trace_bytes"] != path.stat().st_size:
        raise ValueError("Final probe counters disagree with the trace file")
    metrics = {"available": True, "binding": header, "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
               "window_start_ns": start_ns, "window_end_ns": end_ns, "trace_samples": len(samples),
               "window_samples": len(selected), "phases": phases,
               "raw_position_rounding_neighborhood": {"raw_frames": len(raw_window), "matches": matches,
                   "neighborhood_seconds": 0.5, "identity_claim": False},
               "costs": {"sample_mean_ms": status["total_sample_ns"] / len(samples) / 1e6,
                   "sample_max_ms": status["max_sample_ns"] / 1e6,
                   "flush_mean_ms": status["total_flush_ns"] / status["flush_count"] / 1e6,
                   "flush_max_ms": status["max_flush_ns"] / 1e6,
                   "scope": "Capture, serialization and buffered write; flush measured separately. Excludes bootstrap/status-file writes and effects on engine scheduling."},
               "limits": ["Unity xyz; stock IPS maps z,-x,y", "Callback labels do not establish sensor acquisition identity",
                          "FixedUpdate records follow vendor scripts but precede the subsequent physics step; LateUpdate is a separate view",
                          "Observed body drift does not by itself identify the physical solver/contact cause"]}
    if plot is not None:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        plot = Path(plot)
        plot.parent.mkdir(parents=True, exist_ok=True)
        t = [(r["monotonic_ns"] - start_ns)/1e9 for r in fixed]
        fig, axes = plt.subplots(2, 1, figsize=(9, 6), sharex=True, constrained_layout=True)
        for section, label in (("body", "Rigidbody Z"), ("axle", "Rear-axle Transform Z")):
            z = values(fixed, section, "position")[:, 2]
            axes[0].plot(t, (z-z[0])*1000, label=label, linewidth=1.5)
        if raw_window:
            rt = [(r["received_monotonic_ns"]-start_ns)/1e9 for r in raw_window]
            x = np.asarray([r["motion"]["Position"][0] for r in raw_window])
            axes[0].step(rt, (x-x[0])*1000, where="post", label="Stock reported X", alpha=.7)
        axes[0].set_ylabel("Change from first in-window sample (mm)")
        axes[0].legend(); axes[0].grid(alpha=.2)
        velocity = values(fixed, "body", "velocity")
        axes[1].plot(t, velocity[:,2]*1000, color="#b2182b", label="Rigidbody Z velocity")
        axes[1].set(xlabel="Time since complete observation (s)", ylabel="Velocity (mm/s)", xlim=(0,(end_ns-start_ns)/1e9))
        axes[1].grid(alpha=.2); axes[1].legend()
        fig.suptitle("Read-only kinematics diagnostic — " + directory.parent.name + "\nIndependent sample references; receipt alignment is not acquisition alignment")
        fig.savefig(plot.with_suffix(".png"), dpi=160); fig.savefig(plot.with_suffix(".svg")); plt.close(fig)
        metrics["plot"] = str(plot.with_suffix(".png"))
    return metrics
