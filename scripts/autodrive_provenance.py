"""SIM1-01 provenance validation for the roboracer.sim1/1 AutoDRIVE telemetry fields.

Pure functions and small state holders only: import-safe, no ROS/Unity/network
access. The bridge child applies them to every received telemetry frame; the
analysis mode and tests reuse them on recorded frames.

Clock model: the simulator and bridge each report their own monotonic clocks.
No shared epoch is assumed. Each zero reply carries the bridge send time as
"RR Ping Mono"; the simulator echoes it with its receipt and emit times, giving
an NTP-style offset estimate whose error is bounded by half the round-trip delay
not spent inside the simulator.
"""

import math

SCHEMA = "roboracer.sim1/1"
SOURCES = {"lidar": "V1 RR LIDAR Stamp", "ips": "V1 RR IPS Stamp", "imu": "V1 RR IMU Stamp",
           "left_encoder": "V1 RR Left Encoder Stamp", "right_encoder": "V1 RR Right Encoder Stamp",
           "front_camera": "V1 RR Front Camera Stamp"}
FREEZABLE = ("lidar", "ips")
REQUIRED = ("RR Schema", "RR Session", "RR Episode", "RR Telemetry Seq", "RR Capabilities", "RR Clock",
            "RR Ping Echo", "RR Ping Receipt Mono", "RR Test Frozen", "RR Test Hook Rejections", "RR Emit Mono")


class ProvenanceError(ValueError):
    """A frame violates the provenance contract; the consumer must reject it."""


def _integer(text, name, minimum=0):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise ProvenanceError(f"{name} is not an integer: {text!r}") from None
    if value < minimum:
        raise ProvenanceError(f"{name} below {minimum}: {value}")
    return value


def parse_stamp(text):
    """Parse "seq episode step simTime monoNs monoEndNs"."""
    parts = (text or "").split()
    if len(parts) != 6:
        raise ProvenanceError(f"Malformed stamp: {text!r}")
    sim_time = float(parts[3])
    if not math.isfinite(sim_time) or sim_time < 0:
        raise ProvenanceError(f"Invalid simulation time: {parts[3]!r}")
    stamp = {"seq": _integer(parts[0], "seq"), "episode": _integer(parts[1], "episode"),
             "step": _integer(parts[2], "step"), "sim_time": sim_time,
             "mono_ns": _integer(parts[4], "mono_ns"), "mono_end_ns": _integer(parts[5], "mono_end_ns")}
    if stamp["seq"] and stamp["mono_end_ns"] < stamp["mono_ns"]:
        raise ProvenanceError("Acquisition interval ends before it starts")
    return stamp


class ClockEstimator:
    """Offset = simulator_mono - bridge_mono, estimated from echoed pings."""

    def __init__(self, keep=64):
        self.sent = {}
        self.keep = keep
        self.samples = []

    def ping(self, bridge_send_ns):
        value = str(bridge_send_ns)
        self.sent[value] = bridge_send_ns
        if len(self.sent) > self.keep:
            self.sent.pop(next(iter(self.sent)))
        return value

    def observe(self, echo, sim_receipt_ns, sim_emit_ns, bridge_receive_ns):
        """Return a new sample for a fresh echo, or None for absent/repeated/unknown echoes."""
        sent = self.sent.pop(echo, None) if echo else None
        if sent is None:
            return None
        if sim_emit_ns < sim_receipt_ns or bridge_receive_ns < sent:
            raise ProvenanceError("Clock exchange is not causal")
        delay = (bridge_receive_ns - sent) - (sim_emit_ns - sim_receipt_ns)
        if delay < 0:
            raise ProvenanceError("Clock exchange has negative network delay")
        sample = {"offset_ns": ((sim_receipt_ns - sent) + (sim_emit_ns - bridge_receive_ns)) / 2,
                  "bound_ns": delay / 2, "round_trip_ns": bridge_receive_ns - sent,
                  "bridge_receive_ns": bridge_receive_ns}
        self.samples.append(sample)
        return sample

    def current(self, window=16):
        """Tightest-bound sample among the most recent `window` exchanges."""
        recent = self.samples[-window:]
        return min(recent, key=lambda s: s["bound_ns"]) if recent else None


class ProvenanceTracker:
    """Validate successive frames of one simulator session and classify each source sample."""

    def __init__(self, expect_test_hooks):
        self.expect_test_hooks = expect_test_hooks
        self.session = None
        self.episode = None
        self.telemetry_seq = None
        self.last = {}
        self.clock = ClockEstimator()

    def check(self, frame, bridge_receive_ns):
        missing = [key for key in REQUIRED + tuple(SOURCES.values()) if key not in frame]
        if missing:
            raise ProvenanceError("Missing provenance fields: " + ", ".join(missing))
        if frame["RR Schema"] != SCHEMA:
            raise ProvenanceError(f"Unsupported schema {frame['RR Schema']!r}")
        capabilities = set(frame["RR Capabilities"].split())
        if not {"provenance", "clock-echo"} <= capabilities:
            raise ProvenanceError("Required capabilities not advertised")
        if ("test-hooks" in capabilities) != self.expect_test_hooks:
            raise ProvenanceError("Test-hook capability does not match this trial")
        session = frame["RR Session"]
        if self.session is None:
            self.session = session
        elif session != self.session:
            raise ProvenanceError("Simulator session changed within one bridge connection")
        seq = _integer(frame["RR Telemetry Seq"], "telemetry seq", 1)
        if self.telemetry_seq is not None and seq <= self.telemetry_seq:
            raise ProvenanceError(f"Duplicate or out-of-order telemetry seq {seq} after {self.telemetry_seq}")
        episode = _integer(frame["RR Episode"], "episode", 1)
        episode_changed = self.episode is not None and episode != self.episode
        if self.episode is not None and episode < self.episode:
            raise ProvenanceError("Episode moved backwards")
        if episode_changed:
            self.last = {}
        self.telemetry_seq, self.episode = seq, episode
        emit = _integer(frame["RR Emit Mono"], "emit mono")
        sample = self.clock.observe(frame["RR Ping Echo"], _integer(frame["RR Ping Receipt Mono"], "ping receipt"),
                                    emit, bridge_receive_ns)
        clock = self.clock.current()
        record = {"telemetry_seq": seq, "episode": episode, "episode_changed": episode_changed,
                  "frozen": [k for k in frame["RR Test Frozen"].split(",") if k],
                  "hook_rejections": _integer(frame["RR Test Hook Rejections"], "hook rejections"),
                  "clock_sample": sample, "clock": clock, "sources": {}}
        for name, key in SOURCES.items():
            stamp = parse_stamp(frame[key])
            if stamp["episode"] != episode:
                raise ProvenanceError(f"{name} stamp from episode {stamp['episode']} in episode {episode}")
            if stamp["seq"] and stamp["mono_end_ns"] > emit:
                raise ProvenanceError(f"{name} acquired after telemetry emission")
            previous = self.last.get(name)
            if previous and stamp["seq"] < previous["seq"]:
                raise ProvenanceError(f"{name} sequence moved backwards")
            if previous and stamp["seq"] == previous["seq"] and stamp != previous:
                raise ProvenanceError(f"{name} sample identity reused with different content stamp")
            entry = dict(stamp, acquired=stamp["seq"] > 0,
                         reused=bool(previous) and stamp["seq"] == previous["seq"],
                         emit_minus_acquisition_ns=emit - stamp["mono_end_ns"] if stamp["seq"] else None)
            if clock and stamp["seq"]:
                # Age at bridge receipt, in bridge clock, with the exchange's error bound.
                entry["age_ns"] = bridge_receive_ns - (stamp["mono_end_ns"] - clock["offset_ns"])
                entry["age_bound_ns"] = clock["bound_ns"]
            record["sources"][name] = entry
            self.last[name] = stamp
        return record


def _percentiles(values, points=(50, 95, 100)):
    if not values:
        return None
    ordered = sorted(values)
    return [ordered[min(len(ordered) - 1, max(0, math.ceil(p / 100 * len(ordered)) - 1))] for p in points]


def summarize(frames, messages, freeze_test=None):
    """Describe recorded bridge provenance rows (and observer messages); never decides acceptance."""
    rows = [f for f in frames if "provenance" in f]
    summary = {"frames": len(rows), "stamp_basis": {}, "sources": {}, "clock": None,
               "final_hook_rejections": rows[-1]["provenance"]["hook_rejections"] if rows else None,
               "frozen_frames": sum(bool(f["provenance"]["frozen"]) for f in rows),
               "episodes": sorted({f["provenance"]["episode"] for f in rows})}
    for f in rows:
        summary["stamp_basis"][f.get("stamp_basis")] = summary["stamp_basis"].get(f.get("stamp_basis"), 0) + 1
    for name in SOURCES:
        entries = [f["provenance"]["sources"][name] for f in rows]
        new = [e for e in entries if e["acquired"] and not e["reused"]]
        sim_gaps = [b["sim_time"] - a["sim_time"] for a, b in zip(new, new[1:])]
        seq_gaps = [b["seq"] - a["seq"] for a, b in zip(new, new[1:])]
        summary["sources"][name] = {
            "new_samples": len(new), "reused_samples": sum(e["reused"] for e in entries),
            "unacquired_frames": sum(not e["acquired"] for e in entries),
            "acquisitions_between_frames_p50_p95_max": _percentiles(seq_gaps),
            "sim_seconds_between_published_samples_p50_p95_max": _percentiles(sim_gaps),
            "age_ms_p50_p95_max": _percentiles([e["age_ns"] / 1e6 for e in entries if "age_ns" in e]),
            "age_bound_ms_p50_max": (lambda v: v and [v[0], v[2]])(
                _percentiles([e["age_bound_ns"] / 1e6 for e in entries if "age_bound_ns" in e])),
            "emit_minus_acquisition_ms_p50_p95_max": _percentiles(
                [e["emit_minus_acquisition_ns"] / 1e6 for e in entries if e["emit_minus_acquisition_ns"] is not None])}
    samples = [f["provenance"]["clock_sample"] for f in rows if f["provenance"]["clock_sample"]]
    if samples:
        offsets = [s["offset_ns"] for s in samples]
        summary["clock"] = {"exchanges": len(samples), "offset_ms_min_max": [min(offsets) / 1e6, max(offsets) / 1e6],
                            "bound_ms_p50_p95_max": _percentiles([s["bound_ns"] / 1e6 for s in samples]),
                            "round_trip_ms_p50_p95_max": _percentiles([s["round_trip_ns"] / 1e6 for s in samples])}
    # Header stamps that reached ROS equal the bridge's acquisition-mapped stamps.
    mapped = {f["provenance"]["sources"][n].get("ros_stamp_ns") for f in rows for n in SOURCES}
    stamped = [m for m in messages if m.get("topic") in ("lidar", "imu", "front_camera", "left_encoder", "right_encoder")]
    summary["ros_header_stamps"] = {"messages": len(stamped),
                                    "equal_to_acquisition_mapping": sum(m.get("stamp_ns") in mapped for m in stamped),
                                    "provenance_messages": sum(m.get("topic") == "provenance" for m in messages)}
    if freeze_test:
        frozen = [i for i, f in enumerate(rows) if freeze_test in f["provenance"]["frozen"]]
        result = {"source": freeze_test, "frozen_frames": len(frozen), "passed": False}
        if frozen:
            first, last = frozen[0], frozen[-1]
            during = [rows[i]["provenance"]["sources"][freeze_test] for i in frozen[1:]]
            after = [rows[i]["provenance"]["sources"][freeze_test] for i in range(last + 1, len(rows))]
            others = [rows[i]["provenance"]["sources"][n] for i in frozen[1:] for n in SOURCES if n != freeze_test]
            ages = [e["age_ns"] for e in during if "age_ns" in e]
            resumed = next((k + 1 for k, e in enumerate(after) if not e["reused"]), None)
            result.update(
                reused_during_freeze=sum(e["reused"] for e in during), checked_during_freeze=len(during),
                telemetry_seq_advanced=rows[last]["provenance"]["telemetry_seq"] > rows[first]["provenance"]["telemetry_seq"],
                age_monotonic_during_freeze=all(a < b for a, b in zip(ages, ages[1:])),
                max_age_ms_during_freeze=max(ages) / 1e6 if ages else None,
                other_sources_new_during_freeze=all(not e["reused"] for e in others if e["acquired"]),
                frames_until_resumed=resumed)
            result["passed"] = bool(len(during) >= 3 and result["reused_during_freeze"] == len(during)
                                    and result["telemetry_seq_advanced"] and result["age_monotonic_during_freeze"]
                                    and result["other_sources_new_during_freeze"] and resumed is not None
                                    and resumed <= 2 and summary["final_hook_rejections"] == 0)
        summary["freeze"] = result
    return summary
