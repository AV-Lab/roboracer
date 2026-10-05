"""S1 command supervisor logic (``roboracer.supervisor/1``). Pure: no sockets, clock injected.

The supervisor runs in its own OS process (``supervisor_process.py``) and owns the only
command path to the simulator's receiver guard. It accepts ``TargetSpeedSteeringCommand``
requests from the AVLite bridge (kind ``request``), scripted calibration requests (kind
``calibration``, only inside a confirmed motion-protocol stage) and liveness heartbeats from
the runner, and forwards a request only when every check below passes. Expiry is always
measured from the request's original generation time, so forwarding never makes an old
request fresh.

AVLite requests: the motion gate is closed, so only exact zero (target speed 0, steer 0) is
forwarded, as normalized throttle/steering "0"/"0". Speed control comes with S1-03.

Calibration requests (motion protocol v0.1, D2): normalized throttle/steering, bounded in code
by the stage profile: ``m0`` (steering only, throttle exactly 0), ``m1`` (forward throttle
pulses 0.002–0.02, steering exactly 0), ``m2`` (throttle 0.01 for the hang/runner-loss
stop cases, steering exactly 0) and ``m3`` (S1-03 identification holds 0.005–0.02, steering 0). The process opens a stage only with the committed
approval record (``s1-motion-approval.json``) naming it.

Validation order (the first failure is the reason):
  malformed, inhibited (runner lease lost) / no-runner, origin, duplicate, out-of-order,
  non-finite, future-request, stale-request, observation-identity, stale-observation,
  future-observation, then limit / motion-not-authorized (AVLite) or no-stage / stage-limit
  (calibration).
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

PROTOCOL = "roboracer.supervisor/1"
TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
STATES = ("waiting-runner", "active", "inhibited")
# Confirmed stage profiles (s1-motion-protocol.md v0.1 §4). Values are exact normalized commands.
STAGES = {"m0": {"throttle": (0.0,), "steering": (0.0, 0.1, -0.1, 0.5, -0.5, 1.0, -1.0)},
          "m1": {"throttle": (0.0, 0.002, 0.005, 0.01, 0.02), "steering": (0.0,)},
          "m2": {"throttle": (0.0, 0.01), "steering": (0.0,)},
          "m3": {"throttle": (0.0, 0.005, 0.01, 0.02), "steering": (0.0,)}}


@dataclass(frozen=True)
class Limits:
    request_life_ns: int = 500_000_000       # from generation; ≤ the guard's 1 s lease
    max_observation_age_ns: int = 500_000_000  # observation acquisition → supervisor decision
    future_tolerance_ns: int = 100_000_000   # acquisition stamps carry the ~40–60 ms clock bound
    runner_lease_ns: int = 500_000_000       # runner heartbeat silence before inhibition
    max_target_speed_mps: float = 0.0
    max_steer_rad: float = 0.5235987755982988
    motion_authorized: bool = False          # AVLite target-speed motion: closed until S1-03

    def __post_init__(self):
        if not 0 < self.request_life_ns <= 1_000_000_000:
            raise ValueError("request life must be in (0, 1 s]")
        if self.motion_authorized:
            raise ValueError("AVLite motion is not authorized before the S1-03 controller is confirmed")


@dataclass
class Decision:
    accepted: bool
    reason: str
    forward: dict | None = None


def _number(value) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float))


@dataclass
class SupervisorCore:
    origin: str
    limits: Limits = field(default_factory=Limits)
    stage: str | None = None
    state: str = "waiting-runner"
    reason: str = "startup"
    runner_seq: int = 0
    runner_last_ns: int | None = None
    request_origin: str | None = None
    request_seq: int = 0
    out_seq: int = 0
    counters: dict = field(default_factory=dict)

    def __post_init__(self):
        if not TOKEN.match(self.origin):
            raise ValueError("origin must be a guard token")
        if self.stage is not None and self.stage not in STAGES:
            raise ValueError(f"unknown stage {self.stage!r}")

    def _count(self, key):
        self.counters[key] = self.counters.get(key, 0) + 1

    # -- runner liveness ---------------------------------------------------------------------
    def heartbeat(self, runner_seq, now_ns: int) -> str | None:
        """Accept one runner heartbeat; returns a rejection reason or None."""
        if isinstance(runner_seq, bool) or not isinstance(runner_seq, int) or runner_seq <= self.runner_seq:
            self._count("heartbeat-rejected")
            return "heartbeat sequence not increasing"
        self.runner_seq, self.runner_last_ns = runner_seq, now_ns
        if self.state == "waiting-runner":
            self.state, self.reason = "active", "runner"
        return None

    def tick(self, now_ns: int) -> str | None:
        """Lease check; returns the new state when it changed. Inhibition is sticky."""
        if self.state == "active" and now_ns - self.runner_last_ns > self.limits.runner_lease_ns:
            self.state, self.reason = "inhibited", "runner-lease-expired"
            return self.state
        return None

    # -- requests ----------------------------------------------------------------------------
    def _reject(self, reason: str) -> Decision:
        self._count("reject " + reason)
        return Decision(False, reason)

    def submit(self, message: dict, now_ns: int) -> Decision:
        self.tick(now_ns)
        kind = message.get("kind", "request") if isinstance(message, dict) else None
        keys = ("throttle", "steering") if kind == "calibration" else ("target_speed", "steer")
        try:
            origin, seq, gen = message["origin"], message["seq"], message["gen_ns"]
            first, second, obs = message[keys[0]], message[keys[1]], message["observation"]
            telemetry, stamp = obs["telemetry_seq"], obs["stamp_ns"]
        except (KeyError, TypeError):
            return self._reject("malformed")
        integers = (seq, gen, telemetry, stamp)
        if kind not in ("request", "calibration") or not isinstance(origin, str) or not TOKEN.match(origin) or \
                any(isinstance(v, bool) or not isinstance(v, int) for v in integers) or \
                not (_number(first) and _number(second)):
            return self._reject("malformed")
        if self.state != "active":
            return self._reject("inhibited" if self.state == "inhibited" else "no-runner")
        if self.request_origin is None:
            self.request_origin = origin
        elif origin != self.request_origin:
            return self._reject("origin")
        if seq == self.request_seq:
            return self._reject("duplicate")
        if seq < self.request_seq:
            return self._reject("out-of-order")
        self.request_seq = seq  # consumed even if later checks fail: a sequence is never reusable
        if not (math.isfinite(first) and math.isfinite(second)):
            return self._reject("non-finite")
        if gen > now_ns:
            return self._reject("future-request")
        if now_ns - gen > self.limits.request_life_ns:
            return self._reject("stale-request")
        if telemetry <= 0 or stamp <= 0:
            return self._reject("observation-identity")
        if now_ns - stamp > self.limits.max_observation_age_ns:
            return self._reject("stale-observation")
        if stamp - now_ns > self.limits.future_tolerance_ns:
            return self._reject("future-observation")
        if kind == "calibration":
            if self.stage is None:
                return self._reject("no-stage")
            profile = STAGES[self.stage]
            if float(first) not in profile["throttle"] or float(second) not in profile["steering"]:
                return self._reject("stage-limit")
            throttle, steering = _text(float(first)), _text(float(second))
        else:
            speed, steer = first, second
            if speed < 0 or speed > self.limits.max_target_speed_mps or abs(steer) > self.limits.max_steer_rad:
                return self._reject("limit")
            if not self.limits.motion_authorized and (speed != 0 or steer != 0):
                return self._reject("motion-not-authorized")
            throttle = steering = "0"
        self.out_seq += 1
        self._count("forwarded")
        forward = {"origin": self.origin, "seq": self.out_seq, "gen_ns": gen,
                   "deadline_ns": gen + self.limits.request_life_ns, "throttle": throttle, "steering": steering,
                   "inputs": f"{origin}.{seq}.t{telemetry}"}
        return Decision(True, "forwarded", forward)

    def status(self) -> dict:
        return {"protocol": PROTOCOL, "origin": self.origin, "stage": self.stage, "state": self.state,
                "reason": self.reason, "runner_seq": self.runner_seq, "request_origin": self.request_origin,
                "request_seq": self.request_seq, "out_seq": self.out_seq, "counters": dict(self.counters),
                "limits": {k: getattr(self.limits, k) for k in self.limits.__dataclass_fields__}}


def _text(value: float) -> str:
    """Exact normalized value for the guard's wire format ("0" for zero, never "-0")."""
    return "0" if value == 0 else repr(value)
