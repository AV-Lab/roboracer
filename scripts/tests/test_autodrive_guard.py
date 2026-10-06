"""SIM1-02 receiver-guard cases: the C# core under the pinned Mono, the acknowledgement
contract, the reply guard, and the live scenario driver against a simulated receiver."""
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autodrive_guard import (COUNTERS, SCENARIO_PHASES, SCHEMA, GuardError, GuardTracker, ScenarioDriver,
                             analyze_trace, cross_check, format_request, parse_guard, read_trace)
from autodrive_neutral import check_zero_reply

ROOT = Path(__file__).resolve().parents[2]
MONO = Path("/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Data/MonoBleedingEdge")
MS = 1_000_000


class GuardCoreCSharpTests(unittest.TestCase):
    @unittest.skipUnless((MONO / "bin/mono").is_file(), "pinned Editor Mono not available")
    def test_core_cases_pass_under_pinned_mono(self):
        with tempfile.TemporaryDirectory() as scratch:
            exe = Path(scratch) / "guard-core-tests.exe"
            subprocess.run([str(MONO / "bin/mono"), str(MONO / "lib/mono/4.5/csc.exe"), "-nologo", "-out:" + str(exe),
                            str(ROOT / "integration/autodrive/sim1/RoboRacer/GuardCore.cs"),
                            str(ROOT / "integration/autodrive/sim1/tests/GuardCoreTests.cs")], check=True)
            result = subprocess.run([str(MONO / "bin/mono"), str(exe)], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn(" 0 failures", result.stdout)


def ack(state="armed", events="", event_seq=0, counters=None, mode="interlock", clock="10 20 3", capabilities="provenance clock-echo guard"):
    return {"RR Capabilities": capabilities, "RR Guard Schema": SCHEMA, "RR Guard State": state,
            "RR Guard Reason": "requested", "RR Guard Epoch": "1", "RR Guard Origin": "sup-1",
            "RR Guard Accepted": "3", "RR Guard Applied": "3", "RR Guard Lease Remaining": "-1",
            "RR Guard Clock": clock, "RR Guard Counters": counters or " ".join("0" * len(COUNTERS)),
            "RR Guard Config": f"1000000000 400000000 2000000000 {mode}",
            "RR Guard Event Seq": str(event_seq), "RR Guard Events": events}


class GuardContractTests(unittest.TestCase):
    def test_acknowledgement_parses(self):
        record = parse_guard(ack(events="1 state armed epoch 1 sup-1;2 accept 3 400 0 0 sup-1.3", event_seq=2))
        self.assertEqual([(1, "state armed epoch 1 sup-1"), (2, "accept 3 400 0 0 sup-1.3")], record["events"])
        self.assertEqual(10, record["clock"]["width_ns"])
        self.assertIsNone(parse_guard(ack(clock=""))["clock"])

    def test_malformed_acknowledgements_rejected(self):
        for change in ({"RR Guard Schema": "roboracer.guard/0"}, {"RR Guard State": "running"},
                       {"RR Guard Counters": "1 2"}, {"RR Guard Config": "1 2 3 maybe"},
                       {"RR Guard Clock": "30 20 1"}, {"RR Guard Events": "x text"},
                       {"RR Guard Events": "overflow 3"}, {"RR Guard Epoch": "-1"}):
            with self.subTest(change=change), self.assertRaises(GuardError):
                parse_guard(dict(ack(), **change))
        with self.assertRaises(GuardError):
            parse_guard({k: v for k, v in ack().items() if k != "RR Guard Events"})

    def test_tracker_requires_capability_interlock_and_contiguous_events(self):
        tracker = GuardTracker()
        tracker.check(ack(events="1 a;2 b", event_seq=2))
        tracker.check(ack(events="", event_seq=2))
        with self.assertRaises(GuardError):
            tracker.check(ack(events="4 c", event_seq=4))  # event 3 never delivered
        with self.assertRaises(GuardError):
            GuardTracker().check(ack(event_seq=1))         # counter ahead of delivered events
        with self.assertRaises(GuardError):
            GuardTracker().check(ack(mode="motion-authorized"))
        with self.assertRaises(GuardError):
            GuardTracker().check(ack(capabilities="provenance clock-echo"))

    def test_request_format(self):
        self.assertEqual("2 sup-1 7 100 600 0 NaN sup-1.7", format_request(2, "sup-1", 7, 100, 600, "0", "NaN", "sup-1.7"))

    def test_reply_guard_keeps_legacy_zero_unless_probe(self):
        base = {"V1 Throttle": "0", "V1 Steering": "0", "RR Ping Mono": "5", "RR Reply To": "3",
                "RR Reply Frame Receipt": "4", "RR Guard Arm": "disarm", "RR Guard Envelope": "1",
                "RR Guard Request": "garbage"}
        check_zero_reply("Bridge", base)
        with self.assertRaises(ValueError):
            check_zero_reply("Bridge", dict(base, **{"V1 Throttle": "0.5"}))
        check_zero_reply("Bridge", dict(base, **{"V1 Throttle": "0.5", "V1 Steering": "-0.3"}), allow_legacy=True)
        for bad in ("1.5", "nan", "inf"):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                check_zero_reply("Bridge", dict(base, **{"V1 Throttle": bad}), allow_legacy=True)
        for key in ("RR Reply To", "RR Reply Frame Receipt"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                check_zero_reply("Bridge", dict(base, **{key: "-1"}))
        with self.assertRaises(ValueError):
            check_zero_reply("Bridge", dict(base, **{"RR Guard Extra": "x"}))


# ---- simulated receiver (Python model of GuardCore's documented semantics) ----------

class ModelGuard:
    def __init__(self, defect=None, max_lease=1000 * MS, max_width=400 * MS, window=2000 * MS):
        self.defect, self.max_lease, self.max_width, self.window = defect, max_lease, max_width, window
        self.state, self.reason, self.epoch, self.origin = "disarmed", "startup", 0, "-"
        self.last_accepted = self.last_applied = -1
        self.lease = None
        self.samples, self.events, self.pending, self.envelope = [], [], [], -1
        self.counters = dict.fromkeys(COUNTERS, 0)
        self.trace = []

    def log(self, text, now, step=0):
        self.events.append(text)
        number = len(self.events)
        self.pending.append(f"{number} {text}")
        self.trace.append({"k": "event", "mono": now, "step": step, "text": f"{number} {text}"})

    def leave(self, state, reason, now):
        self.lease = None
        if (self.state, self.reason) != (state, reason):
            self.state, self.reason = state, reason
            self.log(f"state {state} {reason}", now)

    def clock(self, now):
        self.samples = [s for s in self.samples if now - s[0] <= self.window]
        if not self.samples:
            return None
        return max(s[1] for s in self.samples), min(s[2] for s in self.samples)

    def exchange(self, now, frame_receipt, ping, emit):
        lower, upper = emit - frame_receipt, now - ping
        current = self.clock(now)
        if current and (lower > current[1] or upper < current[0]):
            self.samples = []
            self.log("clock clock-discontinuity", now)
            if self.state in ("armed", "stopped"):
                self.leave("fault", "clock-discontinuity", now)
            return
        self.samples.append((now, lower, upper))

    def usable(self, now):
        current = self.clock(now)
        if current is None:
            return None, "clock-unavailable"
        if current[1] - current[0] > self.max_width:
            return None, "clock-uncertain"
        return current, None

    def handle(self, reply, now, session, episode):
        if reply.get("arm") is None and reply.get("request") is None:
            return
        text = reply.get("envelope")
        if text is None or not text.isdigit():
            self.counters["rejected"] += 1
            return self.log("reject envelope - malformed", now)
        if int(text) <= self.envelope:
            self.counters["rejected"] += 1
            return self.log(f"reject envelope {text} envelope-replay", now)
        self.envelope = int(text)
        if reply.get("arm") is not None:
            self.arm(reply["arm"], now, session, episode)
        if reply.get("request") is not None:
            self.request(reply["request"], now)

    def arm(self, text, now, session, episode):
        f = text.split(" ")
        if f == ["disarm"]:
            self.log("disarm-request", now)
            return self.leave("disarmed", "requested", now)
        reason = None
        if len(f) != 4 or f[0] != "arm" or not f[2].isdigit():
            reason = "malformed"
        elif self.state == "armed":
            reason = "already-armed"
        elif f[1] != session:
            reason = "wrong-session"
        elif int(f[2]) != episode:
            reason = "wrong-episode"
        else:
            reason = self.usable(now)[1]
        if reason:
            self.counters["rejected"] += 1
            return self.log(f"reject arm {reason}", now)
        self.epoch += 1
        self.origin, self.last_accepted, self.lease = f[3], -1, None
        self.state, self.reason = "armed", "requested"
        self.log(f"state armed epoch {self.epoch} {self.origin}", now)

    def request(self, text, now):
        f = text.split(" ")
        seq = int(f[2]) if len(f) >= 3 and f[2].isdigit() else None
        reason = self.validate(f, now)
        if reason:
            self.counters["rejected"] += 1
            self.log(f"reject {seq if seq is not None else '-'} {reason}", now)

    def validate(self, f, now):
        if len(f) != 8 or not all(v.isdigit() for v in (f[0], f[2], f[3], f[4])):
            return "malformed"
        try:
            throttle, steering = float(f[5]), float(f[6])
        except ValueError:
            return "malformed"
        if f[5].lower().startswith("0x"):
            return "malformed"
        if not (math.isfinite(throttle) and math.isfinite(steering)):
            return "nonfinite"
        if abs(throttle) > 1 or abs(steering) > 1:
            return "out-of-range"
        if self.state != "armed":
            return "not-armed"
        epoch, seq, gen, deadline = int(f[0]), int(f[2]), int(f[3]), int(f[4])
        if epoch != self.epoch:
            return "stale-epoch"
        if f[1] != self.origin:
            return "foreign-origin"
        if seq == self.last_accepted and self.defect != "accept-duplicates":
            return "duplicate"
        if seq < self.last_accepted:
            return "out-of-order"
        if deadline <= gen:
            return "invalid-deadline"
        if deadline - gen > self.max_lease:
            return "lease-too-long"
        current, reason = self.usable(now)
        if reason:
            return reason
        if gen + current[0] > now:
            return "future-generation"
        expiry = min(deadline + current[0], now + self.max_lease)
        if expiry <= now:
            return "expired"
        self.counters["accepted"] += 1
        self.last_accepted, self.lease = seq, (expiry, throttle, steering)
        self.log(f"accept {seq} {expiry - now} {f[5]} {f[6]} {f[7]}", now)

    def step(self, now, step):
        if self.state == "armed" and self.lease and now >= self.lease[0]:
            self.counters["expired"] += 1
            self.leave("stopped", f"lease-expired {self.last_accepted}", now)
        applied = -1
        if self.state == "armed" and self.lease:
            applied = self.last_accepted
            self.counters["applied_steps"] += 1
            if applied != self.last_applied:
                self.last_applied = applied
                self.log(f"applied {applied} step {step}", now, step)
        self.trace.append({"k": "step", "step": step, "mono": now, "state": self.state, "epoch": self.epoch,
                           "applied": applied, "cmd": [0, 0], "out": [0, 0], "mode": 1, "manual": 0,
                           "motor": [0, 0, 0, 0], "brake": [2.352] * 4, "steer": [0, 0]})

    def telemetry(self, now):
        current = self.clock(now)
        frame = ack(state=self.state, events=";".join(self.pending), event_seq=len(self.events),
                    counters=" ".join(str(self.counters[k]) for k in COUNTERS),
                    clock=f"{current[0]} {current[1]} {len(self.samples)}" if current else "")
        frame.update({"RR Guard Reason": self.reason, "RR Guard Epoch": str(self.epoch), "RR Guard Origin": self.origin,
                      "RR Guard Lease Remaining": str(self.lease[0] - now if self.lease else -1)})
        self.pending = []
        return frame


class SimInbox:
    """Supervisor stand-in at 20 Hz in bridge time; killable and respawnable like the real child."""

    def __init__(self, clock):
        self.clock, self.keep, self.forwarded, self.received = clock, 16, set(), 0
        self.origin_index, self.alive, self.requests, self.next_ns = 1, True, [], 0
        self.seq = 0

    def latest(self, count=1):
        now = self.clock()
        while self.alive and self.next_ns <= now:
            self.seq += 1
            gen = self.next_ns
            origin = f"sup-{self.origin_index}"
            self.requests.append({"origin": origin, "seq": self.seq, "gen_ns": gen, "deadline_ns": gen + 1000 * MS,
                                  "throttle": "0", "steering": "0", "inputs": f"{origin}.{self.seq}"})
            self.received += 1
            self.next_ns += 50 * MS
        del self.requests[:-self.keep]
        return self.requests[-count:]

    def respawn(self):
        self.alive, self.origin_index, self.seq = True, self.origin_index + 1, 0
        self.next_ns = self.clock()


def simulate(mode="scenario", defect=None, duration_s=5, max_frames=4000, stop_requests_after_s=None,
             trigger=None, case=None):
    """Lock-step bridge/player loop on simulated time; returns (driver, model).
    ``stop_requests_after_s``: the request source goes silent then (calibration expiry case)."""
    bridge_now = [10_000 * MS]
    start_ns = bridge_now[0]
    offset = 7_000 * MS + 123  # sim = bridge + offset; never assumed by the code under test
    model = ModelGuard(defect)
    inbox = SimInbox(lambda: bridge_now[0])
    done = set()
    driver = ScenarioDriver(inbox, lambda number: number in done, mode=mode, duration_ns=duration_s * 1000 * MS,
                            clock=lambda: bridge_now[0],
                            trigger=(lambda: trigger(bridge_now[0] - start_ns)) if trigger else None, case=case)
    session, episode, step, seq = "c" * 32, 1, 0, 0
    tracker = GuardTracker()
    killed = False
    for _ in range(max_frames):
        seq += 1
        if stop_requests_after_s is not None and bridge_now[0] - start_ns >= stop_requests_after_s * 1000 * MS:
            inbox.alive = False
        emit = bridge_now[0] + offset
        frame = dict(model.telemetry(emit))
        bridge_now[0] += 15 * MS                                    # frame transit
        received = bridge_now[0]
        driver.on_frame(tracker.check(frame), session, episode)
        bridge_now[0] += 100 * MS                                   # pacing delay
        reply = driver.next_reply()
        if driver.action and driver.action["id"] not in done:
            kind = driver.action["kind"]
            if kind == "kill-bridge":
                killed = True
                break
            if kind == "kill-supervisor":
                inbox.alive = False
            elif kind == "spawn-supervisor":
                inbox.respawn()
            elif kind == "manual-input":
                model.counters["manual_ignored"] += 50
                model.counters["gui_blocked"] += 1
                model.log("blocked driving-mode", bridge_now[0] + offset)
            done.add(driver.action["id"])
        bridge_now[0] += int(reply.get("hold_s", 0) * 1e9)
        skew = reply.get("ping_skew_ns", 0)
        ping = bridge_now[0] + skew
        receipt_stamp = ping if reply.get("no_frame_receipt") else received + skew
        if reply.get("legacy"):
            model.counters["legacy_ignored"] += 2
        before = bridge_now[0]
        bridge_now[0] += 10 * MS                                    # reply transit
        sim_receipt = bridge_now[0] + offset
        for t in range(before + offset - 120 * MS, sim_receipt, 20 * MS):  # physics steps in the gap
            step += 1
            model.step(t, step)
        model.exchange(sim_receipt, receipt_stamp, ping, emit)
        model.handle(reply, sim_receipt, session, episode)
        bridge_now[0] += 120 * MS                                   # simulator work before next frame
        if driver.complete:
            break
    if killed:  # Devkit loss: no more replies; the model's lease must still expire on its own.
        for _ in range(50):
            bridge_now[0] += 20 * MS
            step += 1
            model.step(bridge_now[0] + offset, step)
    return driver, model, killed


class ScenarioDriverTests(unittest.TestCase):
    def test_full_scenario_passes_against_correct_receiver(self):
        driver, model, killed = simulate()
        self.assertTrue(killed, "scenario must end with the Devkit-loss kill request")
        phases = {p["phase"]: p for p in driver.phases}
        self.assertEqual(list(SCENARIO_PHASES[:-1]), [p["phase"] for p in driver.phases])
        failed = {name: [c for c in p["checks"] if not c["ok"]] for name, p in phases.items() if not p["passed"]}
        self.assertEqual({}, failed)
        self.assertEqual(driver.current["phase"], "devkit-loss")
        self.assertTrue(any(e.startswith("state stopped lease-expired") for e in model.events[-3:]),
                        "lease must expire after the bridge is gone")
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "guard-trace.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in [{"k": "start", "schema": SCHEMA, "session": "c" * 32,
                                                               "config": "x"}] + model.trace) + "\n")
            analysis = analyze_trace(path)
            self.assertTrue(analysis["passed"], analysis["problems"])
            self.assertEqual(0, analysis["nonzero_output_steps"])
            self.assertEqual([], cross_check(driver.phases, read_trace(path)[1]))
        for reason in ("malformed", "nonfinite", "out-of-range", "duplicate", "out-of-order", "expired",
                       "envelope-replay", "lease-too-long", "invalid-deadline", "stale-epoch", "foreign-origin",
                       "not-armed", "wrong-session", "wrong-episode", "already-armed", "clock-uncertain"):
            self.assertIn(reason, " ".join(model.events))

    def test_defective_receiver_fails_the_duplicate_phase(self):
        driver, _, _ = simulate(defect="accept-duplicates")
        phases = {p["phase"]: p for p in driver.phases}
        self.assertFalse(phases["duplicate"]["passed"])

    def test_observe_mode_forwards_continuously_without_expiry(self):
        driver, model, killed = simulate(mode="observe", duration_s=20)
        self.assertFalse(killed)
        self.assertTrue(driver.complete and driver.summary()["passed"], driver.phases)
        self.assertEqual(0, model.counters["expired"])
        self.assertGreater(model.counters["accepted"], 50)

    def test_calibration_mode_requires_exactly_one_final_lease_expiry(self):
        driver, model, killed = simulate(mode="calibration", duration_s=20, stop_requests_after_s=15)
        self.assertFalse(killed)
        self.assertTrue(driver.complete and driver.summary()["passed"], driver.phases)
        self.assertEqual("disarmed", driver.summary()["state"])
        self.assertTrue(any(e.startswith("state stopped lease-expired") for e in model.events))
        # Without the expiry case the calibration phase must not pass.
        driver, _, _ = simulate(mode="calibration", duration_s=10)
        checks = {c["name"]: c["ok"] for c in driver.phases[0]["checks"]}
        self.assertFalse(checks["one final lease expiry"])
        self.assertFalse(driver.summary()["passed"])

    def test_trace_analysis_flags_torque_and_unaccepted_application(self):
        rows = [{"k": "start", "schema": SCHEMA},
                {"k": "event", "mono": 1, "step": 1, "text": "1 state armed epoch 1 sup-1"},
                {"k": "step", "step": 2, "mono": 2, "state": "armed", "epoch": 1, "applied": 5, "cmd": [0, 0],
                 "out": [0, 0], "mode": 1, "manual": 0, "motor": [0, 0, 0.1, 0], "brake": [0] * 4, "steer": [0, 0]}]
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "trace.jsonl"
            path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
            problems = analyze_trace(path)["problems"]
        self.assertTrue(any("without an armed acceptance" in p for p in problems))
        self.assertTrue(any("nonzero" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
