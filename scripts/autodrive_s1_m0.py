#!/usr/bin/env python3
"""Motion protocol v0.1 stage M0 (steering only, throttle 0): analysis of one retained trial.

Reads the guard's per-step trace (1 ms fixed steps: applied command, output, wheel motor/brake
torques and both front wheel steer angles), the guard events, the bridge frame trace and the
calibration/supervisor logs. Pass criteria (s1-motion-protocol.md §4, M0):
  - sign: positive normalized steering turns left (negative Unity steerAngle on both front wheels);
  - steady angle within 0.5 deg of the vendor Ackermann split of 30 deg x command
    (serialized Wheelbase 324, TrackWidth 236);
  - outward slew 183 +/- 10 deg/s (internal angle reconstructed from the front-left wheel);
  - return to 0 after each step; expiry case: angles back to 0 within 0.2 s of the lease expiry;
  - IPS displacement <= 5 mm, encoders unchanged, motor torque exactly 0 on every step;
  - no guard fault or rejection; every supervisor decision forwarded.
Writes a fresh JSON report; nonzero exit when any criterion fails.
"""

import argparse
import json
import math
from pathlib import Path

WHEELBASE, TRACK, LIMIT_DEG, RATE_DEG_S = 324.0, 236.0, 30.0, 183.346
FIXED_STEP_S = 0.001  # pinned fixed timestep (SIM1-02); the guard traces every step


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def expected_wheels(command):
    """Vendor Steer(): SteeringAngle = -command * 30; Ackermann split per front wheel (deg)."""
    delta = math.radians(-command * LIMIT_DEG)
    t = math.tan(delta)
    left = math.degrees(math.atan(2 * WHEELBASE * t / (2 * WHEELBASE + TRACK * t)))
    right = math.degrees(math.atan(2 * WHEELBASE * t / (2 * WHEELBASE - TRACK * t)))
    return left, right


def internal_from_left(angle_deg):
    tan_left = math.tan(math.radians(angle_deg))
    return math.degrees(math.atan(2 * WHEELBASE * tan_left / (2 * WHEELBASE - TRACK * tan_left)))


def segments(steps):
    """Runs of constant output steering: [(value, first index, last index)]."""
    out, start = [], 0
    for i in range(1, len(steps) + 1):
        if i == len(steps) or steps[i]["out"][1] != steps[start]["out"][1]:
            out.append((steps[start]["out"][1], start, i - 1))
            start = i
    return out


def analyze(directory: Path) -> dict:
    trace = rows(directory / "guard/guard-trace.jsonl")
    steps = [r for r in trace if r.get("k") == "step"]
    events = [r for r in trace if r.get("k") == "event"]
    frames = [r for r in rows(directory / "bridge-frames.jsonl") if "motion" in r]
    supervisor = [r for r in rows(directory / "supervisor-trace.jsonl") if r["event"] == "request"]
    calibration = json.loads((directory / "calibration-status.json").read_text())
    failures = []

    texts = [e["text"].split(" ", 1)[1] for e in events]
    faults = [t for t in texts if t.startswith("state fault")]
    rejects = [t for t in texts if t.startswith("reject ")]
    stops = [(e, e["text"].split(" ", 1)[1]) for e in events if e["text"].split(" ", 1)[1].startswith("state stopped")]
    if faults or rejects:
        failures.append(f"guard faults {faults} / rejections {rejects}")
    if any(r["decision"] != "forwarded" for r in supervisor):
        failures.append("supervisor rejected a calibration request")
    if any(any(m != 0 for m in s["motor"]) for s in steps):
        failures.append("nonzero motor torque")
    if any(s["out"][0] != 0 or s["cmd"][0] != 0 for s in steps):
        failures.append("nonzero throttle command or output")
    if calibration.get("abort"):
        failures.append("calibration aborted: " + calibration["abort"])

    results = []
    segs = segments(steps)
    for index, (value, first, last) in enumerate(segs):
        seg = steps[first:last + 1]
        duration_s = (seg[-1]["mono"] - seg[0]["mono"]) / 1e9
        row = {"command": value, "steps": len(seg), "duration_s": duration_s}
        if value != 0:
            left_exp, right_exp = expected_wheels(value)
            left, right = seg[-1]["steer"]
            row.update(expected_deg=[left_exp, right_exp], final_deg=[left, right],
                       error_deg=[left - left_exp, right - right_exp],
                       turns="left" if left < 0 and right < 0 else "right" if left > 0 and right > 0 else "mixed",
                       # Convention-free cross-check: the inner front wheel steers more (Ackermann).
                       inner_wheel="left" if abs(left) > abs(right) else "right")
            target = abs(value) * LIMIT_DEG
            # Simulation time (fixed step index x 1 ms): Unity runs several physics steps back to
            # back per rendered frame, so the wall-clock stamps in the trace are bunched.
            internal = [(s["step"], abs(internal_from_left(s["steer"][0]))) for s in seg]
            t10 = next((t for t, a in internal if a >= 0.1 * target), None)
            t90 = next((t for t, a in internal if a >= 0.9 * target), None)
            row["slew_deg_s"] = 0.8 * target / ((t90 - t10) * FIXED_STEP_S) if t10 and t90 and t90 > t10 else None
            settled = duration_s >= 0.5
            row["settled"] = settled
            if settled:
                side = "left" if value > 0 else "right"
                ok_sign = row["turns"] == side and row["inner_wheel"] == side
                ok_angle = max(abs(e) for e in row["error_deg"]) <= 0.5
                ok_slew = row["slew_deg_s"] is not None and abs(row["slew_deg_s"] - RATE_DEG_S) <= 10
                row["passed"] = ok_sign and ok_angle and ok_slew
                if not row["passed"]:
                    failures.append(f"segment {index} command {value}: sign {ok_sign} angle {ok_angle} slew {ok_slew}")
        else:
            zero_at = next((s["mono"] for s in seg if s["steer"] == [0, 0]), None)
            row["return_to_zero_s"] = (zero_at - seg[0]["mono"]) / 1e9 if zero_at is not None else None
            if index > 0 and row["return_to_zero_s"] is None:
                failures.append(f"segment {index}: steering did not return to 0")
        results.append(row)

    commanded = sorted({v for v, _, _ in segs if v != 0})
    settled_commands = sorted({r["command"] for r in results if r.get("settled")})
    if settled_commands != sorted({0.1, -0.1, 0.5, -0.5, 1.0, -1.0}):
        failures.append(f"settled commands {settled_commands} differ from the M0 profile")

    expiry = None
    if len(stops) != 1 or not stops[0][1].startswith("state stopped lease-expired"):
        failures.append(f"expected exactly one lease-expired stop, got {[s[1] for s in stops]}")
    else:
        event = stops[0][0]
        after = [s for s in steps if s["step"] >= event["step"]]
        zero = next((s for s in after if s["steer"] == [0, 0] and s["out"][1] == 0), None)
        before = [s for s in steps if s["step"] < event["step"]]
        expiry = {"event": stops[0][1], "step": event["step"],
                  "command_before": before[-1]["out"][1] if before else None,
                  "zero_after_s": (zero["mono"] - event["mono"]) / 1e9 if zero else None}
        if expiry["command_before"] != 0.5 or expiry["zero_after_s"] is None or expiry["zero_after_s"] > 0.2:
            failures.append(f"expiry case: {expiry}")

    # Translation over the M0 window: from the first profile request until the expiry wait ended
    # (last request + 4 s). Passive creep (SIM0: ~3-4 mm/min) outside it is reported separately.
    requests = rows(directory / "calibration-requests.jsonl")
    profile = [r["gen_ns"] for r in requests if r["phase"] == "profile"]
    window = (min(profile), max(r["gen_ns"] for r in requests) + 4_000_000_000) if profile else None
    reference = frames[0]["motion"]

    def millimetres(frame):  # IPS is reported in whole millimetres; avoid float artefacts
        return round(math.dist(reference["Position"], frame["motion"]["Position"]) * 1000, 3)

    inside = [f for f in frames if window and window[0] <= f["received_monotonic_ns"] <= window[1]]
    start = [f for f in frames if window and f["received_monotonic_ns"] < window[0]]
    base = millimetres(start[-1]) if start else 0.0
    displacement = max((abs(millimetres(f) - base) for f in inside), default=None)
    whole_run = max(millimetres(f) for f in frames)
    encoders_changed = any(f["motion"]["Encoder Ticks"] != reference["Encoder Ticks"] for f in frames)
    if displacement is None or displacement > 5.0 or encoders_changed:
        failures.append(f"translation in the M0 window: {displacement} mm, encoders changed {encoders_changed}")
    feedback = [f["motion"].get("Steering Feedback") for f in frames if "Steering Feedback" in f["motion"]]
    return {"run": str(directory), "guard_steps": len(steps), "segments": results, "commanded": commanded,
            "expiry": expiry, "m0_window_displacement_mm": displacement, "whole_run_displacement_mm": whole_run,
            "m0_window_s": (window[1] - window[0]) / 1e9 if window else None,
            "whole_run_s": (frames[-1]["received_monotonic_ns"] - frames[0]["received_monotonic_ns"]) / 1e9,
            "encoders_changed": encoders_changed,
            "steering_feedback_rad_min_max": [min(feedback), max(feedback)] if feedback else None,
            "calibration": {k: calibration.get(k) for k in ("phase", "sent", "send_failures", "precheck", "abort")},
            "supervisor_decisions": len(supervisor), "guard_faults": faults, "guard_rejections": rejects,
            "failures": failures, "passes": not failures}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output must be fresh")
    report = analyze(args.run)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("commanded", "m0_window_displacement_mm", "whole_run_displacement_mm", "expiry", "failures", "passes")}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
