#!/usr/bin/env python3
"""S1 supervisor-skeleton live check: trace every command from AVLite to the guard.

Joins, for one ``autodrive_neutral.py run --plugin-stack`` run directory:
  plugin-ticks.jsonl   AVLite SyncExecuter ticks (snapshot used, request sequence)
  supervisor-trace.jsonl  every supervisor decision and forwarded request
  guard/guard-trace.jsonl the simulator guard's events and per-step actuation record

Checks: every guard acceptance traces back to one forwarded supervisor request and one
AVLite request, with exact-zero values, the request's original generation time and
``deadline = generation + request life``; every AVLite request names the snapshot of the
tick that produced it; no supervisor rejection other than before the runner's first
heartbeat, except ``inhibited`` after the runner lease expired once the observation had ended
(the runner stops heartbeating at cleanup); no step with nonzero output. Writes a fresh JSON report; nonzero exit on failure.
"""

import argparse
import json
import math
from pathlib import Path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def percentiles(values, points=(50, 95, 100)):
    if not values:
        return None
    ordered = sorted(values)
    return [ordered[min(len(ordered) - 1, math.ceil(p / 100 * len(ordered)) - 1)] for p in points]


def analyze(directory: Path) -> dict:
    ticks = rows(directory / "plugin-ticks.jsonl")
    supervisor = rows(directory / "supervisor-trace.jsonl")
    guard = rows(directory / "guard/guard-trace.jsonl")
    status = json.loads((directory / "supervisor-1-status.json").read_text())
    run = json.loads((directory / "run.json").read_text())
    stack = json.loads((directory / "plugin-observer-status.json").read_text())
    failures = []

    requests = [r for r in supervisor if r["event"] == "request"]
    decisions = {}
    for r in requests:
        decisions[r["decision"]] = decisions.get(r["decision"], 0) + 1
    first_heartbeat = next((r["t"] for r in supervisor if r["event"] == "heartbeat"), None)
    states = [r for r in supervisor if r["event"] == "state"]
    end = run.get("observation_end_ns")
    inhibited_at = states[0]["t"] if states and states[0]["reason"] == "runner-lease-expired" else None
    if any(r["t"] < end for r in states) if end else states:
        failures.append("supervisor changed state during the observation")
    late_rejections = [r for r in requests if r["decision"] != "forwarded" and
                       (first_heartbeat is None or r["t"] >= first_heartbeat)]
    post_run = [r for r in late_rejections if r["decision"] == "inhibited" and inhibited_at and end
                and inhibited_at >= end and r["t"] >= inhibited_at]
    if len(late_rejections) != len(post_run):
        failures.append(f"{len(late_rejections) - len(post_run)} supervisor rejections during the observation")
    forwarded = {r["forwarded"]["seq"]: r for r in requests if r["decision"] == "forwarded"}
    life = status["limits"]["request_life_ns"]
    for r in forwarded.values():
        f = r["forwarded"]
        if f["gen_ns"] != r["gen_ns"] or f["deadline_ns"] != r["gen_ns"] + life or (f["throttle"], f["steering"]) != ("0", "0") \
                or f["inputs"] != f"avlite.{r['seq']}.t{r['observation']['telemetry_seq']}":
            failures.append(f"forwarded request {f['seq']} differs from its source")
    if [r["seq"] for r in requests] != sorted({r["seq"] for r in requests}):
        failures.append("AVLite request sequence not strictly increasing")

    # Each AVLite request names the snapshot used by the tick that produced it.
    tick_of_request, previous = {}, 0
    for t in ticks:
        for seq in range(previous + 1, t["request_seq"] + 1):
            tick_of_request[seq] = t
        previous = t["request_seq"]
    mismatched = [r["seq"] for r in requests
                  if tick_of_request.get(r["seq"], {}).get("telemetry_seq") != r["observation"]["telemetry_seq"]]
    if mismatched:
        failures.append(f"{len(mismatched)} requests name a snapshot other than their tick's")

    accepts, remaining = [], []
    for e in (g for g in guard if g.get("k") == "event"):
        parts = e["text"].split()
        if len(parts) >= 7 and parts[1] == "accept":
            seq, expiry, throttle, steering, inputs = int(parts[2]), int(parts[3]), parts[4], parts[5], parts[6]
            accepts.append(seq)
            remaining.append(expiry / 1e6)
            source = forwarded.get(seq)
            if source is None or source["forwarded"]["inputs"] != inputs or (throttle, steering) != ("0", "0"):
                failures.append(f"guard acceptance {seq} does not trace to a forwarded zero request")
    if not accepts:
        failures.append("no guard acceptance")
    steps = [g for g in guard if g.get("k") == "step"]
    nonzero = sum(1 for g in steps if any(g["out"]) or any(g["motor"]) or any(g["steer"]))
    if nonzero:
        failures.append(f"{nonzero} steps with nonzero output")

    after = [r for r in requests if r["decision"] == "forwarded"]
    request_age = [(r["t"] - r["gen_ns"]) / 1e6 for r in after]
    observation_age = [(r["t"] - r["observation"]["stamp_ns"]) / 1e6 for r in after]
    durations = [(t["end_ns"] - t["start_ns"]) / 1e6 for t in ticks]
    starts = [t["start_ns"] for t in ticks]
    periods = [(b - a) / 1e6 for a, b in zip(starts, starts[1:])]
    heartbeats = [r for r in supervisor if r["event"] == "heartbeat"]
    return {"run": str(directory), "avlite_ticks": len(ticks), "tick_overruns": stack.get("tick_overruns"),
            "tick_ms_p50_p95_max": percentiles(durations), "tick_period_ms_p50_p95_max": percentiles(periods),
            "bridge_requests": stack["statistics"]["requests"], "supervisor_decisions": decisions,
            "supervisor_state": status["state"], "supervisor_io": status["io"],
            "heartbeat_rejections_or_state_changes": len(heartbeats) - 1 if heartbeats else None,
            "rejections_before_first_heartbeat": sum(1 for r in requests if r["decision"] != "forwarded") - len(late_rejections),
            "inhibited_after_observation_end": len(post_run),
            "inhibition_after_observation_end_ms": (inhibited_at - end) / 1e6 if inhibited_at and end else None,
            "guard_acceptances": len(accepts), "forwarded": len(forwarded),
            "forwarded_superseded_at_bridge": len(forwarded) - len(set(accepts)),
            "forwarded_request_age_at_supervisor_ms_p50_p95_max": percentiles(request_age),
            "forwarded_observation_age_at_supervisor_ms_p50_p95_max": percentiles(observation_age),
            "guard_lease_remaining_at_accept_ms_p50_p5_min": None if not remaining else
                [percentiles(remaining, (50,))[0], percentiles(remaining, (5,))[0], min(remaining)],
            "guard_steps": len(steps), "nonzero_output_steps": nonzero,
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
    print(json.dumps({k: report[k] for k in ("guard_acceptances", "forwarded", "failures", "passes")}))
    return 0 if report["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
