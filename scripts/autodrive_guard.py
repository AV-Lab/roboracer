#!/usr/bin/env python3
"""SIM1-02 receiver-guard tooling for the roboracer.guard/1 AutoDRIVE extension.

Import-safe: no ROS/Unity/network access at import time. Provides
  - the bridge-side request format and the simulator's acknowledgement parser;
  - a supervisor stand-in that runs as its own OS process (`supervise` below);
    it only ever generates exact-zero normalized requests;
  - a phase-scripted driver for the disarmed P1a cases, run inside the bridge;
  - an analysis of the player's guard-trace.jsonl, which is the authoritative
    record of what reached the actuation hook.

Request times are the bridge host's CLOCK_MONOTONIC (Python time.monotonic_ns
in the supervisor and bridge, one kernel clock). The simulator never assumes a
shared epoch with it; it bounds the offset itself from its own stamps.
"""

import argparse
import json
import math
import os
import re
import signal
import socket
import time

SCHEMA = "roboracer.guard/1"
STATES = ("disarmed", "armed", "stopped", "fault")
FIELDS = ("RR Guard Schema", "RR Guard State", "RR Guard Reason", "RR Guard Epoch", "RR Guard Origin",
          "RR Guard Accepted", "RR Guard Applied", "RR Guard Lease Remaining", "RR Guard Clock",
          "RR Guard Counters", "RR Guard Config", "RR Guard Event Seq", "RR Guard Events")
COUNTERS = ("accepted", "rejected", "expired", "applied_steps", "legacy_ignored", "manual_ignored",
            "gui_blocked", "violations", "interlock_steps")
REPLY_FIELDS = {"RR Guard Arm", "RR Guard Request", "RR Guard Envelope", "RR Reply To"}
TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")


class GuardError(ValueError):
    """A guard acknowledgement violates the contract; the consumer must reject it."""


def _integer(text, name, minimum=None):
    try:
        value = int(text)
    except (TypeError, ValueError):
        raise GuardError(f"{name} is not an integer: {text!r}") from None
    if minimum is not None and value < minimum:
        raise GuardError(f"{name} below {minimum}: {value}")
    return value


def format_request(epoch, origin, seq, gen_ns, deadline_ns, throttle, steering, inputs):
    """Wire form; throttle/steering are passed as text so fault cases can carry NaN etc."""
    return " ".join(str(v) for v in (epoch, origin, seq, gen_ns, deadline_ns, throttle, steering, inputs))


def parse_guard(frame):
    """Parse one telemetry frame's guard acknowledgement fields."""
    missing = [key for key in FIELDS if key not in frame]
    if missing:
        raise GuardError("Missing guard fields: " + ", ".join(missing))
    if frame["RR Guard Schema"] != SCHEMA:
        raise GuardError(f"Unsupported guard schema {frame['RR Guard Schema']!r}")
    state = frame["RR Guard State"]
    if state not in STATES:
        raise GuardError(f"Unknown guard state {state!r}")
    counters = frame["RR Guard Counters"].split()
    if len(counters) != len(COUNTERS):
        raise GuardError("Malformed guard counters")
    config = frame["RR Guard Config"].split()
    if len(config) != 4 or config[3] not in ("interlock", "motion-authorized"):
        raise GuardError("Malformed guard config")
    clock = frame["RR Guard Clock"].split()
    if clock and len(clock) != 3:
        raise GuardError("Malformed guard clock")
    events = []
    for item in filter(None, frame["RR Guard Events"].split(";")):
        number, _, text = item.partition(" ")
        if number == "overflow":
            raise GuardError("Guard event buffer overflowed: " + text)
        events.append((_integer(number, "event number", 1), text))
    record = {
        "state": state, "reason": frame["RR Guard Reason"], "epoch": _integer(frame["RR Guard Epoch"], "epoch", 0),
        "origin": frame["RR Guard Origin"], "accepted": _integer(frame["RR Guard Accepted"], "accepted", -1),
        "applied": _integer(frame["RR Guard Applied"], "applied", -1),
        "lease_remaining_ns": _integer(frame["RR Guard Lease Remaining"], "lease remaining"),
        "clock": None, "counters": {k: _integer(v, k, 0) for k, v in zip(COUNTERS, counters)},
        "config": {"max_lease_ns": _integer(config[0], "max lease", 1),
                   "max_clock_width_ns": _integer(config[1], "max clock width", 1),
                   "clock_window_ns": _integer(config[2], "clock window", 1), "mode": config[3]},
        "event_seq": _integer(frame["RR Guard Event Seq"], "event seq", 0), "events": events}
    if clock:
        lower, upper, samples = (_integer(v, "clock") for v in clock)
        if lower > upper or samples < 1:
            raise GuardError("Inconsistent guard clock bounds")
        record["clock"] = {"lower_ns": lower, "upper_ns": upper, "width_ns": upper - lower, "samples": samples}
    return record


class GuardTracker:
    """Check acknowledgement continuity across frames of one connection."""

    def __init__(self, require_interlock=True):
        self.require_interlock = require_interlock
        self.event_seq = 0

    def check(self, frame):
        if "guard" not in frame.get("RR Capabilities", "").split():
            raise GuardError("Guard capability not advertised")
        record = parse_guard(frame)
        if self.require_interlock and record["config"]["mode"] != "interlock":
            raise GuardError("Player is not in the zero-output interlock mode required for disarmed trials")
        for number, _ in record["events"]:
            if number != self.event_seq + 1:
                raise GuardError(f"Guard event gap: {number} after {self.event_seq}")
            self.event_seq = number
        if record["event_seq"] != self.event_seq:
            raise GuardError(f"Guard event seq {record['event_seq']} does not match delivered {self.event_seq}")
        return record


# ---- supervisor stand-in -------------------------------------------------------

def socket_name(pid):
    return f"roboracer-guard-{pid}"


class RequestInbox:
    """Bridge side: receive supervisor datagrams on a Linux abstract socket; keep the latest few."""

    def __init__(self, name, keep=16):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind("\0" + name)
        self.sock.setblocking(False)
        self.keep = keep
        self.requests = []
        self.received = 0
        self.forwarded = set()

    def drain(self):
        while True:
            try:
                payload = self.sock.recv(4096)
            except BlockingIOError:
                return
            message = json.loads(payload)
            self.received += 1
            self.requests.append(dict(message, received_ns=time.monotonic_ns()))
            del self.requests[:-self.keep]

    def latest(self, count=1):
        self.drain()
        return self.requests[-count:]

    def close(self):
        self.sock.close()


def supervise(target, origin, rate_hz, life_ns, status_path):
    """Child entrypoint: emit exact-zero requests until terminated."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setblocking(False)  # never block on a bridge that is not draining; count the drop instead
    sent = refused = dropped = 0
    stop = []
    signal.signal(signal.SIGTERM, lambda *_: stop.append(True))
    period = 1 / rate_hz
    seq = 0
    while not stop:
        seq += 1
        gen = time.monotonic_ns()
        message = {"origin": origin, "seq": seq, "gen_ns": gen, "deadline_ns": gen + life_ns,
                   "throttle": "0", "steering": "0", "inputs": f"{origin}.{seq}"}
        try:
            sock.sendto(json.dumps(message).encode(), "\0" + target)
            sent += 1
        except (ConnectionRefusedError, FileNotFoundError):
            refused += 1
        except BlockingIOError:
            dropped += 1
        if seq % max(1, int(rate_hz)) == 1:
            temporary = status_path + ".tmp"
            with open(temporary, "w") as stream:
                json.dump({"pid": os.getpid(), "origin": origin, "seq": seq, "sent": sent, "refused": refused,
                           "dropped": dropped,
                           "monotonic_ns": time.monotonic_ns()}, stream)
            os.replace(temporary, status_path)
        time.sleep(period)
    return 0


# ---- scenario driver -------------------------------------------------------------

SCENARIO_PHASES = ("baseline", "malformed", "nonfinite", "out-of-range", "duplicate", "out-of-order",
                   "expired-forward", "envelope-replay", "lease-too-long", "stale-epoch-origin", "not-armed",
                   "clock-uncertain", "clock-discontinuity", "legacy-bypass", "manual-bypass",
                   "supervisor-loss", "devkit-loss")


class Reply(dict):
    """Fields for one bridge reply. Keys: arm, request, envelope, hold_s, no_frame_receipt, ping_skew_ns, legacy."""


class ScenarioDriver:
    """Phase-scripted guard requests. Each reply's effect is observed in later frames' events.

    `mode` is "scenario" (all SCENARIO_PHASES, each in its own arm epoch) or "observe"
    (arm once, forward every fresh supervisor request for `duration_ns`).
    """

    def __init__(self, inbox, action_done, mode="scenario", duration_ns=None, clock=time.monotonic_ns,
                 trigger=None, case=None, episodes=1, episode_done=None, motion=True):
        self.inbox, self.action_done, self.mode = inbox, action_done, mode
        self.duration_ns, self.clock = duration_ns, clock
        # S1-06 (M1 protocol v0.1): calibration mode reads an external trigger each frame,
        # {"disarm": true, "rearm_after_s": float | null, "source": ...}, written by the AVLite stage
        # (F1-5 disarm/rearm) or by the runner (D16: disarm on runner error). `case` selects checks.
        self.trigger, self.case = trigger, case
        # S2 batch (D20 A): `episodes` per player; `episode_done(n)` is true once the AVLite stage reports
        # episode n finished (motion), or None for stationary batches, whose episodes last `duration_ns`.
        self.episodes, self.episode_done, self.motion = episodes, episode_done, motion
        self.external = None
        self.events, self.phases, self.record = [], [], None
        self.session = self.episode = None
        self.frames = self.envelope = self.actions = 0
        self.action = None
        self.skew_ns = 0
        self.complete = False
        self.started = False
        self.current = None
        self.script = {"observe": self._observe, "calibration": self._calibration,
                       "reset": self._reset, "batch": self._batch}.get(mode, self._scenario)()

    # Bridge interface -------------------------------------------------------------
    def on_frame(self, record, session, episode):
        self.frames += 1
        self.record, self.session, self.episode = record, session, episode
        self.events.extend((n, text, self.frames) for n, text in record["events"])

    def next_reply(self):
        if self.complete:
            return Reply(ping_skew_ns=self.skew_ns)
        try:
            reply = self.script.send(None) if self.started else next(self.script)
            self.started = True
        except StopIteration:
            self.complete = True
            if self.current:
                self._close_phase()
            reply = Reply()
        if reply.get("arm") is not None or reply.get("request") is not None:
            if "envelope" not in reply:
                self.envelope += 1
                reply["envelope"] = str(self.envelope)
        reply.setdefault("ping_skew_ns", self.skew_ns)
        return reply

    def summary(self):
        return {"mode": self.mode, "complete": self.complete, "frames": self.frames,
                "state": self.record["state"] if self.record else None,
                "phases": self.phases, "events_seen": len(self.events),
                "passed": self.complete and all(p["passed"] for p in self.phases)}

    # Helpers --------------------------------------------------------------------
    def _open_phase(self, name):
        if self.current:
            self._close_phase()
        self.current = {"phase": name, "first_frame": self.frames + 1, "checks": [], "forwarded": []}

    def _close_phase(self):
        self.current["last_frame"] = self.frames
        self.current["passed"] = bool(self.current["checks"]) and all(c["ok"] for c in self.current["checks"])
        self.phases.append(self.current)
        self.current = None

    def _check(self, name, ok, **detail):
        self.current["checks"].append(dict(name=name, ok=bool(ok), **detail))

    def _mark(self):
        return len(self.events)

    def _find(self, since, pattern):
        rx = re.compile(pattern)
        for n, text, frame in self.events[since:]:
            if rx.search(text):
                return [n, text]
        return None

    def _origin(self):
        latest = self.inbox.latest()
        return latest[-1]["origin"] if latest else None

    def _fresh(self, reforward=False):
        """Next unforwarded supervisor request (or, if allowed, the last one again)."""
        latest = self.inbox.latest(self.inbox.keep)
        # Never fall back to an older, skipped request once a newer one was forwarded: when the
        # source goes silent that would send stale, out-of-order requests.
        newest = getattr(self, "_newest_forwarded", {})
        unsent = [r for r in latest if (r["origin"], r["seq"]) not in self.inbox.forwarded
                  and r["seq"] > newest.get(r["origin"], 0)]
        if unsent:
            request = unsent[-1]
            newest[request["origin"]] = request["seq"]
            self._newest_forwarded = newest
        elif reforward and latest:
            request = latest[-1]
        else:
            return None
        self.inbox.forwarded.add((request["origin"], request["seq"]))
        return request

    def _text(self, request, **override):
        values = dict(epoch=self.record["epoch"], origin=request["origin"], seq=request["seq"],
                      gen_ns=request["gen_ns"], deadline_ns=request["deadline_ns"],
                      throttle=request["throttle"], steering=request["steering"], inputs=request["inputs"])
        values.update(override)
        if self.current is not None:
            self.current["forwarded"].append({k: values[k] for k in ("epoch", "origin", "seq", "throttle", "steering")})
        return format_request(**values)

    def _fresh_reply(self, reforward=False, **extra):
        request = self._fresh(reforward)
        return Reply(extra, request=self._text(request)) if request else Reply(extra)

    def _await(self, since, pattern, frames=12, reply=None):
        for _ in range(frames):
            hit = self._find(since, pattern)
            if hit:
                return hit
            yield reply() if reply else Reply()
        return self._find(since, pattern)

    def _expect(self, name, since, pattern, frames=12, reply=None):
        hit = yield from self._await(since, pattern, frames, reply)
        self._check(name, hit is not None, pattern=pattern, event=hit)
        return hit

    def _forbid(self, name, since, pattern):
        hit = self._find(since, pattern)
        self._check(name, hit is None, forbidden=pattern, event=hit)

    def _idle(self, frames, reply=None):
        for _ in range(frames):
            yield reply() if reply else Reply()

    def _arm(self, name="armed"):
        since = self._mark()
        yield Reply(arm=f"arm {self.session} {self.episode} {self._origin()}")
        return (yield from self._expect(name, since, r"^state armed epoch \d+ "))

    def _disarm(self):
        since = self._mark()
        yield Reply(arm="disarm")
        yield from self._expect("disarmed", since, r"^disarm-request$")

    def _act(self, kind, frames=60, reply=None):
        self.actions += 1
        self.action = {"id": self.actions, "kind": kind}
        yield (reply() if reply else Reply())
        for _ in range(frames):
            if self.action_done(self.action["id"]):
                break
            yield (reply() if reply else Reply())
        done = self.action_done(self.action["id"])
        self._check("action " + kind, done, action=self.action)
        self.action = None
        return done

    def _next_fresh(self):
        request = self._fresh()
        while request is None:
            yield Reply()
            request = self._fresh()
        return request

    def _forward_and_expect(self, count):
        """Forward `count` fresh requests and require accept + applied for each. Keeps
        forwarding fresh requests while waiting, so the lease is still live on return."""
        seqs = []
        since = self._mark()
        for _ in range(count):
            request = yield from self._next_fresh()
            seqs.append(request["seq"])
            yield Reply(request=self._text(request))
        yield from self._await(since, rf"^applied {seqs[-1]} step ", 8, lambda: self._fresh_reply())
        for seq in seqs:
            self._check(f"accept {seq}", self._find(since, rf"^accept {seq} ") is not None)
            self._check(f"applied {seq}", self._find(since, rf"^applied {seq} step ") is not None)
        return seqs

    # Scripts --------------------------------------------------------------------
    def _warmup(self):
        while self.record is None or self.record["clock"] is None or not self.inbox.latest():
            yield Reply()
        yield from self._idle(3)

    def _observe(self):
        yield from self._warmup()
        self._open_phase("observe")
        yield from self._arm()
        start, since = self.clock(), self._mark()
        while self.clock() - start < self.duration_ns:
            yield self._fresh_reply()
        self._forbid("no rejection", since, r"^reject ")
        self._forbid("no expiry", since, r"^state (stopped|fault)")
        self._check("accepted continuously", self.record["state"] == "armed", state=self.record["state"])
        yield from self._disarm()

    def _calibration(self):
        """Motion protocol M0 (motion-authorized player): arm once and forward every fresh
        supervisor request for `duration_ns`. The calibration source ends with an expiry case,
        so exactly one final `lease-expired` stop is required; no rejection and no fault."""
        yield from self._warmup()
        self._open_phase("calibration")
        yield from self._arm()
        start, since = self.clock(), self._mark()
        while self.clock() - start < self.duration_ns:
            trigger = (self.trigger() if self.trigger else None) or {}
            ext = self.external
            if trigger.get("disarm") and ext is None:
                ext = self.external = {"trigger": trigger, "old_epoch": self.record["epoch"],
                                       "disarm_mark": self._mark(), "disarm_ns": self.clock()}
                yield Reply(arm="disarm")
                continue
            rearm_after = (ext or {}).get("trigger", {}).get("rearm_after_s")
            if ext and rearm_after is not None and "rearm_mark" not in ext \
                    and self.clock() - ext["disarm_ns"] >= rearm_after * 1e9:
                ext["rearm_mark"] = self._mark()
                ext["rearm"] = yield from self._await(ext["rearm_mark"], r"^state armed epoch \d+ ", 12, lambda: Reply(
                    arm=f"arm {self.session} {self.episode} {self._origin()}") if not self._find(
                    ext["rearm_mark"], r"^(state armed|reject arm)") else Reply())
                # One deliberately stale request from the previous epoch must be rejected.
                stale = self._next_fresh_or_none()
                if stale is not None:
                    ext["stale_epoch_seq"] = stale["seq"]
                    yield Reply(request=self._text(stale, epoch=ext["old_epoch"]))
                continue
            if ext and rearm_after is None:
                yield Reply()  # D16: after a runner-requested disarm nothing more is forwarded
                continue
            yield self._fresh_reply()
        if self.case == "f1-5":
            self._check_rearm_case(since)
        elif self.external is not None:
            self._expect_seen("disarm-request", self.external["disarm_mark"], r"^disarm-request$")
            self._forbid("no rejection", since, r"^reject ")
            self._forbid("no fault", since, r"^state fault")
        else:
            self._forbid("no rejection", since, r"^reject ")
            self._forbid("no fault", since, r"^state fault")
            stops = [text for _, text, _ in self.events[since:] if text.startswith("state stopped")]
            self._check("one final lease expiry", len(stops) == 1 and stops[0].startswith("state stopped lease-expired"),
                        stops=stops)
        yield from self._disarm()

    def _reset(self):
        """SIM1-03 (P1a, disarmed or interlocked): GUI Reset reloads the scene. Required: the guard leaves
        `armed` with reason scene-load; the episode advances; the runner reviews the reloaded scene and
        reconnects; then a request while disarmed is rejected not-armed, an arm naming the old episode is
        rejected wrong-episode, re-arming in the new episode opens a new epoch, an old-epoch request and a
        replay of a pre-reset request are rejected stale-epoch, and fresh requests are accepted and applied."""
        yield from self._warmup()
        self._open_phase("reset")
        yield from self._arm()
        old_epoch, old_episode = self.record["epoch"], self.episode
        before = yield from self._next_fresh()
        replay_text = self._text(before)
        mark = self._mark()
        yield Reply(request=replay_text)
        yield from self._expect("pre-reset request accepted", mark, rf"^accept {before['seq']} ")
        yield from self._forward_and_expect(1)
        since = self._mark()
        self.reset_info = {"old_epoch": old_epoch, "old_episode": old_episode, "since_event": since}
        done = yield from self._act("gui-reset", frames=900)
        if not done:
            return
        self._check("guard disarmed by the scene load", self._find(since, r"^state disarmed scene-load$") is not None,
                    event=self._find(since, r"^state disarmed scene-load$"))
        self._check("episode advanced by one", self.episode == old_episode + 1, before=old_episode, after=self.episode)
        yield from self._idle(5)  # clock exchanges after the reconnect, before any arm
        request = yield from self._next_fresh()
        mark = self._mark()
        yield Reply(request=self._text(request))
        yield from self._expect("request while disarmed rejected not-armed", mark, rf"^reject {request['seq']} not-armed$")
        mark = self._mark()
        yield Reply(arm=f"arm {self.session} {old_episode} {self._origin()}")
        yield from self._expect("arm naming the old episode rejected", mark, r"^reject arm wrong-episode$")
        armed = yield from self._arm("re-armed in the new episode")
        self._check("new epoch after re-arm", bool(armed) and int(armed[1].split()[3]) == old_epoch + 1, event=armed)
        request = yield from self._next_fresh()
        mark = self._mark()
        yield Reply(request=self._text(request, epoch=old_epoch))
        yield from self._expect("old-epoch request rejected stale-epoch", mark, rf"^reject {request['seq']} stale-epoch$")
        mark = self._mark()
        yield Reply(request=replay_text)
        yield from self._expect("replayed pre-reset request rejected stale-epoch", mark,
                                rf"^reject {before['seq']} stale-epoch$")
        yield from self._forward_and_expect(2)
        self._forbid("no fault", since, r"^state fault")
        yield from self._disarm()

    def _batch(self):
        """S2 batch (D20 A, D21 A, D22): one player, `episodes` episodes with GUI Reset between them.

        Each episode: arm in a new epoch; from the second episode on, a replay of the previous epoch's
        last forwarded request must be rejected stale-epoch (no stale reapplication); forward every
        fresh supervisor request until the stage reports the episode finished (motion) or `duration_ns`
        elapses (stationary); then require the stop: motion ends with exactly one lease expiry, a
        stationary episode with none; no other rejection, no fault; disarm. Between episodes the runner
        performs the GUI Reset with its automated checks and reconnects; the scene-load disarm and the
        episode advance are checked here."""
        yield from self._warmup()
        replay = None
        for number in range(1, self.episodes + 1):
            self._open_phase(f"episode {number}")
            if not (yield from self._arm()):
                return
            armed_episode = self.episode
            # F2 cases in the first episode (D23): F2-1 reloads the scene under the episode, F2-4 jumps the clock.
            expect_reload = self.case == "f2-1" and number == 1
            expect_fault = self.case == "f2-4" and number == 1
            jumped = False
            if replay is not None:
                mark = self._mark()
                yield Reply(request=replay["text"])
                yield from self._expect("previous-epoch request rejected stale-epoch", mark,
                                        rf"^reject {replay['seq']} stale-epoch$")
            start, since, last = self.clock(), self._mark(), None

            def finished():
                return self.episode_done is not None and self.episode_done(number)

            while self.clock() - start < self.duration_ns and not finished():
                if expect_fault and not jumped and (self.trigger() if self.trigger else {}).get("clock_jump_ns"):
                    jumped = True
                    self.skew_ns = int(self.trigger()["clock_jump_ns"])  # one skewed ping, then back to 0
                    yield Reply()
                    self.skew_ns = 0
                    continue
                request = self._fresh()
                if request is not None and self.episode == armed_episode:
                    last = request
                    yield Reply(request=self._text(request))
                else:
                    yield Reply()
            if expect_reload or expect_fault:
                self._check("F2 injected and episode ended", finished(), case=self.case)
                pattern = r"^state disarmed scene-load$" if expect_reload else r"^state fault clock-discontinuity"
                self._check("expected F2 guard outcome", self._find(since, pattern) is not None, pattern=pattern)
                yield from self._disarm()
                if number == self.episodes:
                    break
                replay = {"text": self._text(last), "seq": last["seq"]} if last is not None else None
                if self.episode > armed_episode:   # F2-1 already reloaded the scene: no second reset
                    yield from self._idle(5)
                    continue
                old_episode, since = self.episode, self._mark()
                self._open_phase(f"reset {number}")
                if not (yield from self._act("gui-reset", frames=900)):
                    return
                self._check("guard disarmed by the scene load", self._find(since, r"^state disarmed scene-load$") is not None)
                self._check("episode advanced by one", self.episode == old_episode + 1, before=old_episode, after=self.episode)
                yield from self._idle(5)
                continue
            if self.motion:
                self._check("episode finished by the stage", finished(), elapsed_s=(self.clock() - start) / 1e9)
                # The stage stops requesting when it finishes; its last request's lease then expires.
                yield from self._await(since, r"^state (stopped|fault)", 12)
                stops = [t for _, t, _ in self.events[since:] if t.startswith("state stopped")]
                self._check("one final lease expiry", len(stops) == 1 and stops[0].startswith("state stopped lease-expired"),
                            stops=stops)
            else:
                self._forbid("no expiry", since, r"^state (stopped|fault)")
                self._check("accepted continuously", self.record["state"] == "armed", state=self.record["state"])
            self._forbid("no rejection", since, r"^reject ")
            self._forbid("no fault", since, r"^state fault")
            self._check("requests forwarded", last is not None)
            yield from self._disarm()
            if number == self.episodes:
                break
            replay = {"text": self._text(last), "seq": last["seq"]} if last is not None else None
            old_episode, since = self.episode, self._mark()
            self._open_phase(f"reset {number}")
            if not (yield from self._act("gui-reset", frames=900)):
                return
            self._check("guard disarmed by the scene load", self._find(since, r"^state disarmed scene-load$") is not None)
            self._check("episode advanced by one", self.episode == old_episode + 1, before=old_episode, after=self.episode)
            yield from self._idle(5)  # clock exchanges after the reconnect, before the next arm

    def _next_fresh_or_none(self):
        return self._fresh()

    def _expect_seen(self, name, since, pattern):
        hit = self._find(since, pattern)
        self._check(name, hit is not None, pattern=pattern, event=hit)
        return hit

    def _check_rearm_case(self, since):
        """F1-5: disarm stops the car; while disarmed requests are rejected not-armed; a re-arm opens
        a new epoch; a request from the old epoch is rejected stale-epoch; then normal operation ends
        with exactly one final lease expiry. No other rejection and no fault."""
        ext = self.external or {}
        self._check("disarm triggered", bool(ext), external=bool(ext))
        if not ext:
            return
        self._expect_seen("disarm-request", ext["disarm_mark"], r"^disarm-request$")
        rearm_mark = ext.get("rearm_mark", len(self.events))
        between = [text for _, text, _ in self.events[ext["disarm_mark"]:rearm_mark] if text.startswith("reject ")]
        self._check("rejected not-armed while disarmed", bool(between) and all(t.endswith(" not-armed") for t in between),
                    rejects=between[:5], count=len(between))
        armed = ext.get("rearm")
        epoch_ok = bool(armed) and int(armed[1].split()[3]) == ext["old_epoch"] + 1
        self._check("re-armed with a new epoch", epoch_ok, event=armed)
        after = [text for _, text, _ in self.events[rearm_mark:] if text.startswith("reject ")]
        stale = ext.get("stale_epoch_seq")
        self._check("old-epoch request rejected stale-epoch", stale is not None and f"reject {stale} stale-epoch" in after,
                    rejects=after[:5])
        self._check("no other rejection after re-arm", all(t == f"reject {stale} stale-epoch" for t in after), rejects=after[:5])
        self._forbid("no fault", since, r"^state fault")
        stops = [text for _, text, _ in self.events[rearm_mark:] if text.startswith("state stopped")]
        self._check("one final lease expiry after re-arm",
                    len(stops) == 1 and stops[0].startswith("state stopped lease-expired"), stops=stops)
        accepted = [text for _, text, _ in self.events[rearm_mark:] if text.startswith("accept ")]
        self._check("requests accepted after re-arm", bool(accepted), count=len(accepted))

    def _scenario(self):
        yield from self._warmup()
        for name in SCENARIO_PHASES:
            self._open_phase(name)
            yield from getattr(self, "_phase_" + name.replace("-", "_"))()

    def _phase_baseline(self):
        yield from self._arm()
        yield from self._forward_and_expect(6)
        yield from self._disarm()

    def _reject_cases(self, cases):
        """Each case: (label, request builder from a fresh request, expected reason)."""
        yield from self._arm()
        yield from self._forward_and_expect(1)
        for label, build, reason in cases:
            # A valid request first, so the invalid one arrives while a lease is live and armed.
            valid = yield from self._next_fresh()
            yield Reply(request=self._text(valid))
            request = yield from self._next_fresh()
            since = self._mark()
            yield Reply(request=build(request))
            yield from self._expect(label, since, r"^reject \S+ " + re.escape(reason) + "$",
                                    reply=lambda: self._fresh_reply())
            self._forbid(label + " not accepted", since, rf"^accept {request['seq']} ")
        yield from self._disarm()

    def _phase_malformed(self):
        yield from self._reject_cases([
            ("garbage", lambda r: "garbage", "malformed"),
            ("missing inputs field", lambda r: self._text(r)[: self._text(r).rindex(" ")], "malformed"),
            ("hex throttle", lambda r: self._text(r, throttle="0x1"), "malformed")])

    def _phase_nonfinite(self):
        yield from self._reject_cases([
            ("NaN throttle", lambda r: self._text(r, throttle="NaN"), "nonfinite"),
            ("Infinity steering", lambda r: self._text(r, steering="Infinity"), "nonfinite")])

    def _phase_out_of_range(self):
        yield from self._reject_cases([
            ("throttle 1.5", lambda r: self._text(r, throttle="1.5"), "out-of-range"),
            ("steering -2", lambda r: self._text(r, steering="-2"), "out-of-range")])

    def _phase_lease_too_long(self):
        yield from self._reject_cases([
            ("deadline 2 s", lambda r: self._text(r, deadline_ns=r["gen_ns"] + 2_000_000_000), "lease-too-long"),
            ("deadline before generation", lambda r: self._text(r, deadline_ns=r["gen_ns"]), "invalid-deadline")])

    def _phase_stale_epoch_origin(self):
        yield from self._reject_cases([
            ("previous epoch", lambda r: self._text(r, epoch=self.record["epoch"] - 1), "stale-epoch"),
            ("foreign origin", lambda r: self._text(r, origin="intruder"), "foreign-origin")])

    def _phase_duplicate(self):
        yield from self._arm()
        yield from self._forward_and_expect(1)
        request = yield from self._next_fresh()
        seq = request["seq"]
        since = self._mark()
        for _ in range(3):
            yield Reply(request=self._text(request))  # once, then the same original in fresh envelopes
        yield from self._expect("accepted once", since, rf"^accept {seq} ")
        yield from self._expect("duplicate rejected", since, rf"^reject {seq} duplicate$")
        yield from self._expect("original lease expires", since, rf"^state stopped lease-expired {seq}$",
                                reply=lambda: Reply(request=self._text(request)))
        accepts = [e for e in self.events[since:] if e[1].startswith(f"accept {seq} ")]
        self._check("never re-accepted", len(accepts) == 1, accepts=len(accepts))
        yield from self._disarm()

    def _phase_out_of_order(self):
        yield from self._arm()
        yield from self._idle(2)
        pair = []
        while len(pair) < 2:
            pair = [r for r in self.inbox.latest(4) if (r["origin"], r["seq"]) not in self.inbox.forwarded][-2:]
            if len(pair) < 2:
                yield Reply()
        older, newer = pair
        for r in pair:
            self.inbox.forwarded.add((r["origin"], r["seq"]))
        since = self._mark()
        yield Reply(request=self._text(newer))
        yield Reply(request=self._text(older))
        yield from self._expect("newer accepted", since, rf"^accept {newer['seq']} ")
        yield from self._expect("older rejected", since, rf"^reject {older['seq']} out-of-order$")
        yield from self._disarm()

    def _phase_expired_forward(self):
        yield from self._arm()
        held = None
        while held is None:
            held = self._fresh()
            if held is None:
                yield Reply()
        while self.clock() - held["gen_ns"] < held["deadline_ns"] - held["gen_ns"] + 200_000_000:
            yield Reply()  # hold the original past its own deadline; no lease exists meanwhile
        since = self._mark()
        yield Reply(request=self._text(held))  # never seen before, new envelope
        yield from self._expect("expired original rejected", since, rf"^reject {held['seq']} expired$")
        self._forbid("never accepted", since, rf"^accept {held['seq']} ")
        yield from self._disarm()

    def _phase_envelope_replay(self):
        yield from self._arm()
        yield from self._forward_and_expect(1)
        replayed = str(self.envelope)
        since = self._mark()
        request = self._fresh()
        while request is None:
            yield Reply()
            request = self._fresh()
        yield Reply(request=self._text(request), envelope=replayed)
        yield from self._expect("replayed envelope rejected", since, rf"^reject envelope {replayed} envelope-replay$")
        self._forbid("request inside replay not processed", since, rf"^(accept|reject) {request['seq']} ")
        yield from self._disarm()

    def _phase_not_armed(self):
        request = None
        while request is None:
            request = self._fresh()
            if request is None:
                yield Reply()
        since = self._mark()
        yield Reply(request=self._text(request))
        yield from self._expect("request while disarmed", since, rf"^reject {request['seq']} not-armed$")
        for label, text, reason in (
                ("wrong session", f"arm {'0' * 32} {self.episode} {self._origin()}", "wrong-session"),
                ("wrong episode", f"arm {self.session} {self.episode + 1} {self._origin()}", "wrong-episode"),
                ("malformed arm", "arm", "malformed")):
            since = self._mark()
            yield Reply(arm=text)
            yield from self._expect(label, since, r"^reject arm " + reason + "$")
        yield from self._arm()
        since = self._mark()
        yield Reply(arm=f"arm {self.session} {self.episode} {self._origin()}")
        yield from self._expect("arm while armed", since, r"^reject arm already-armed$")
        yield from self._disarm()

    def _phase_clock_uncertain(self):
        # Holding a reply past the clock window, without its frame-receipt stamp, leaves the
        # receiver one exchange whose bound is at least the hold.
        window = self.record["config"]["clock_window_ns"] / 1e9
        wide = dict(hold_s=window + 0.6, no_frame_receipt=True)
        since = self._mark()
        yield Reply(wide, arm=f"arm {self.session} {self.episode} {self._origin()}")
        yield from self._expect("arm on a single wide exchange", since, r"^reject arm clock-uncertain$")
        yield from self._idle(4)
        yield from self._arm("armed after normal exchanges")
        since = self._mark()
        request = None
        while request is None:
            request = self._fresh()
            if request is None:
                yield Reply()
        yield Reply(wide, request=self._text(request))
        yield from self._expect("request on a single wide exchange", since, r"^reject \S+ clock-uncertain$")
        yield from self._disarm()

    def _phase_clock_discontinuity(self):
        yield from self._arm()
        yield from self._forward_and_expect(1)
        since = self._mark()
        self.skew_ns = 1_000_000_000
        yield from self._expect("forward jump faults", since, r"^state fault clock-discontinuity$",
                                reply=lambda: self._fresh_reply())
        self._check("lease cleared on fault", self.record["lease_remaining_ns"] == -1,
                    lease_remaining_ns=self.record["lease_remaining_ns"])
        yield from self._idle(3)
        yield from self._arm("rearmed on relearned offset")
        since = self._mark()
        self.skew_ns = 0
        yield from self._expect("backward jump faults", since, r"^state fault clock-discontinuity$")
        yield from self._idle(3)
        yield from self._disarm()

    def _phase_legacy_bypass(self):
        yield from self._arm()
        yield from self._forward_and_expect(1)
        before = self.record["counters"]["legacy_ignored"]
        since = self._mark()
        for _ in range(3):
            yield self._fresh_reply(legacy=("0.5", "-0.3"))
        yield from self._idle(1, lambda: self._fresh_reply())
        self._check("legacy fields ignored and counted", self.record["counters"]["legacy_ignored"] - before == 6,
                    delta=self.record["counters"]["legacy_ignored"] - before)
        self._forbid("no fault", since, r"^state fault")
        yield from self._disarm()

    def _phase_manual_bypass(self):
        yield from self._arm()
        yield from self._forward_and_expect(1)
        before = dict(self.record["counters"])
        since = self._mark()
        yield from self._act("manual-input", reply=lambda: self._fresh_reply())
        yield from self._expect("GUI mode toggle blocked", since, r"^blocked driving-mode$",
                                reply=lambda: self._fresh_reply())
        yield from self._idle(2, lambda: self._fresh_reply())
        self._check("manual input observed and ignored",
                    self.record["counters"]["manual_ignored"] > before["manual_ignored"],
                    delta=self.record["counters"]["manual_ignored"] - before["manual_ignored"])
        self._check("still armed in guarded mode", self.record["state"] == "armed", state=self.record["state"])
        yield from self._disarm()

    def _phase_supervisor_loss(self):
        yield from self._arm()
        yield from self._forward_and_expect(2)
        yield from self._act("kill-supervisor", reply=lambda: self._fresh_reply(reforward=True))
        # Requests buffered before the kill are genuine: forward the newest once, then nothing new exists.
        buffered = self.inbox.latest(self.inbox.keep)
        request = self._fresh()
        self.inbox.forwarded.update((r["origin"], r["seq"]) for r in buffered)
        loss = self._mark()
        if request is not None:
            yield Reply(request=self._text(request))
            yield from self._await(loss, rf"^(accept|reject) {request['seq']} ", 4,
                                   lambda: self._fresh_reply(reforward=True))
        since = self._mark()
        yield from self._expect("lease expires after supervisor loss", since,
                                r"^state stopped lease-expired \d+$",
                                reply=lambda: self._fresh_reply(reforward=True))
        self._check("stale re-forwards rejected", self._find(loss, r"^reject \d+ duplicate$") is not None)
        self._forbid("no acceptance after the last genuine request", since, r"^accept ")
        yield from self._act("spawn-supervisor")
        while not self.inbox.latest() or self._origin() == self.current["forwarded"][-1]["origin"]:
            yield Reply()
        yield from self._disarm()

    def _phase_devkit_loss(self):
        yield from self._arm()
        yield from self._forward_and_expect(2)
        self.action = {"id": self.actions + 1, "kind": "kill-bridge"}
        self.actions += 1
        while True:  # the parent kills this process; it verifies expiry/disconnect from the player trace
            yield self._fresh_reply()


# ---- trace analysis --------------------------------------------------------------------

EVENT = re.compile(r"^(\d+) (.*)$")


def read_trace(path, live=False):
    """Parse guard-trace.jsonl. With `live`, a final line still being written is skipped."""
    start, events, steps, other = None, [], [], []
    with open(path) as stream:
        for line in stream:
            if live and not line.endswith("\n"):
                break
            row = json.loads(line, parse_constant=lambda c: (_ for _ in ()).throw(ValueError(c)))
            kind = row.get("k")
            if kind == "start":
                start = row
            elif kind == "event":
                match = EVENT.match(row["text"])
                if not match:
                    raise GuardError("Malformed trace event: " + row["text"])
                events.append(dict(row, n=int(match.group(1)), event=match.group(2)))
            elif kind == "step":
                steps.append(row)
            else:
                other.append(row)
    return start, events, steps, other


def analyze_trace(path, fixed_step_ns=1_000_000):
    """Authoritative check of what reached the actuation hook. Step records are stamped after
    actuation, so an application may be stamped up to one fixed step (pinned: 1 ms) past expiry."""
    start, events, steps, other = read_trace(path)
    problems = []
    if start is None or start.get("schema") != SCHEMA:
        problems.append("missing or wrong trace start record")
    if any(row.get("k") == "truncated" for row in other):
        problems.append("trace truncated")
    numbers = [e["n"] for e in events]
    if numbers != list(range(1, len(numbers) + 1)):
        problems.append("trace event numbers are not consecutive from 1")
    accepted, expiry, rejects, states = {}, {}, {}, []
    epoch, applied_seen = 0, set()
    for e in events:
        text = e["event"]
        if m := re.match(r"^state armed epoch (\d+) ", text):
            epoch = int(m.group(1))
        elif m := re.match(r"^accept (\d+) (-?\d+) (\S+) (\S+) ", text):
            key = (epoch, int(m.group(1)))
            accepted[key] = {"mono": e["mono"], "expiry_mono": e["mono"] + int(m.group(2)),
                             "throttle": float(m.group(3)), "steering": float(m.group(4))}
        elif m := re.match(r"^reject (.+) (\S+)$", text):
            rejects[m.group(2)] = rejects.get(m.group(2), 0) + 1
        elif m := re.match(r"^state stopped lease-expired (\d+)$", text):
            expiry[(epoch, int(m.group(1)))] = e["mono"]
        if text.startswith("state "):
            states.append(text)
    nonzero_steps, overshoot = [], []
    for s in steps:
        if any(v != 0 for v in s["motor"]) or any(v != 0 for v in s["out"]) or any(v != 0 for v in s["steer"]):
            nonzero_steps.append(s["step"])
        if s["mode"] != 1:
            problems.append(f"step {s['step']} not in guarded autonomous mode")
        if s["applied"] >= 0:
            key = (s["epoch"], s["applied"])
            if s["state"] != "armed" or key not in accepted:
                problems.append(f"step {s['step']} applied {key} without an armed acceptance")
            else:
                overshoot.append(s["mono"] - accepted[key]["expiry_mono"])
                if overshoot[-1] >= fixed_step_ns:
                    problems.append(f"step {s['step']} applied {key} after its lease")
            applied_seen.add(key)
    if nonzero_steps:
        problems.append(f"{len(nonzero_steps)} steps with nonzero output/torque/steer")
    lateness = [mono - accepted[key]["expiry_mono"] for key, mono in expiry.items() if key in accepted]
    if any(l < 0 for l in lateness):
        problems.append("a lease expired before its computed expiry")
    return {
        "trace": str(path), "session": start and start.get("session"), "config": start and start.get("config"),
        "events": len(events), "steps": len(steps), "nonzero_output_steps": len(nonzero_steps),
        "accepted": len(accepted), "applied_commands": len(applied_seen),
        "accepted_nonzero": sum(1 for a in accepted.values() if a["throttle"] or a["steering"]),
        "rejections_by_reason": dict(sorted(rejects.items())), "lease_expiries": len(expiry),
        "lease_expiry_lateness_ms_max": max(lateness) / 1e6 if lateness else None,
        "applied_step_latest_relative_to_expiry_ms": max(overshoot) / 1e6 if overshoot else None,
        "step_rate_hz": (len(steps) - 1) / ((steps[-1]["mono"] - steps[0]["mono"]) / 1e9) if len(steps) > 1 else None,
        "state_transitions": states, "problems": problems, "passed": not problems}


def cross_check(phases, trace_events):
    """Every event a scenario check relied on must appear identically in the player trace."""
    by_number = {e["n"]: e["event"] for e in trace_events}
    missing = []
    for phase in phases:
        for check in phase["checks"]:
            event = check.get("event")
            if check.get("pattern") and event and by_number.get(event[0]) != event[1]:
                missing.append([phase["phase"], check["name"], event])
    return missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("supervise", "analyze-trace"))
    parser.add_argument("--target")
    parser.add_argument("--origin")
    parser.add_argument("--rate", type=float, default=20.0)
    parser.add_argument("--life-ms", type=float, default=1000.0)
    parser.add_argument("--status")
    parser.add_argument("--trace")
    args = parser.parse_args()
    if args.mode == "supervise":
        if not (args.target and args.origin and TOKEN.match(args.origin) and args.status
                and math.isfinite(args.rate) and 0 < args.rate <= 100 and 0 < args.life_ms <= 1000):
            parser.error("supervise needs --target, a token --origin, --status, rate in (0,100], life in (0,1000] ms")
        return supervise(args.target, args.origin, args.rate, int(args.life_ms * 1e6), args.status)
    print(json.dumps(analyze_trace(args.trace), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
