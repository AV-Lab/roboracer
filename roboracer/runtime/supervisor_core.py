"""S1 command supervisor logic (``roboracer.supervisor/1``). Pure: no sockets, clock injected.

The supervisor runs in its own OS process (``supervisor_process.py``) and owns the only
command path to the simulator's receiver guard. It accepts ``TargetSpeedSteeringCommand``
requests from the AVLite bridge and liveness heartbeats from the runner, and forwards a
request only when every check below passes. Expiry is always measured from the request's
original generation time, so forwarding never makes an old request fresh.

Skeleton scope (before the numerical motion protocol is confirmed): the motion gate is
closed, so only exact-zero requests (target speed 0, steer 0) are forwarded, as normalized
throttle/steering "0"/"0". Speed control and steering conversion come with the protocol.

Validation order (the first failure is the reason):
  malformed, inhibited (runner lease lost) / no-runner, origin, duplicate, out-of-order,
  non-finite, future-request, stale-request, observation-identity, stale-observation,
  future-observation, limit, motion-not-authorized.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re

PROTOCOL = "roboracer.supervisor/1"
TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
STATES = ("waiting-runner", "active", "inhibited")


@dataclass(frozen=True)
class Limits:
    request_life_ns: int = 500_000_000       # from generation; ≤ the guard's 1 s lease
    max_observation_age_ns: int = 500_000_000  # observation acquisition → supervisor decision
    future_tolerance_ns: int = 100_000_000   # acquisition stamps carry the ~40–60 ms clock bound
    runner_lease_ns: int = 500_000_000       # runner heartbeat silence before inhibition
    max_target_speed_mps: float = 0.0
    max_steer_rad: float = 0.5235987755982988
    motion_authorized: bool = False          # closed until the motion protocol is confirmed

    def __post_init__(self):
        if not 0 < self.request_life_ns <= 1_000_000_000:
            raise ValueError("request life must be in (0, 1 s]")
        if self.motion_authorized:
            raise ValueError("motion is not authorized before the S1 motion protocol is confirmed")


@dataclass
class Decision:
    accepted: bool
    reason: str
    forward: dict | None = None


@dataclass
class SupervisorCore:
    origin: str
    limits: Limits = field(default_factory=Limits)
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
        try:
            origin, seq, gen = message["origin"], message["seq"], message["gen_ns"]
            speed, steer, obs = message["target_speed"], message["steer"], message["observation"]
            telemetry, stamp = obs["telemetry_seq"], obs["stamp_ns"]
        except (KeyError, TypeError):
            return self._reject("malformed")
        integers = (seq, gen, telemetry, stamp)
        if not isinstance(origin, str) or not TOKEN.match(origin) or \
                any(isinstance(v, bool) or not isinstance(v, int) for v in integers) or \
                any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in (speed, steer)):
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
        if not (math.isfinite(speed) and math.isfinite(steer)):
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
        if speed < 0 or speed > self.limits.max_target_speed_mps or abs(steer) > self.limits.max_steer_rad:
            return self._reject("limit")
        if not self.limits.motion_authorized and (speed != 0 or steer != 0):
            return self._reject("motion-not-authorized")
        self.out_seq += 1
        self._count("forwarded")
        forward = {"origin": self.origin, "seq": self.out_seq, "gen_ns": gen,
                   "deadline_ns": gen + self.limits.request_life_ns, "throttle": "0", "steering": "0",
                   "inputs": f"{origin}.{seq}.t{telemetry}"}
        return Decision(True, "forwarded", forward)

    def status(self) -> dict:
        return {"protocol": PROTOCOL, "origin": self.origin, "state": self.state, "reason": self.reason,
                "runner_seq": self.runner_seq, "request_origin": self.request_origin,
                "request_seq": self.request_seq, "out_seq": self.out_seq, "counters": dict(self.counters),
                "limits": {k: getattr(self.limits, k) for k in self.limits.__dataclass_fields__}}
