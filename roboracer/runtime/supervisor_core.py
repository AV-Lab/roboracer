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
stop cases, steering exactly 0), ``m3`` (S1-03 identification holds 0.005–0.02, steering 0) and
``m3b`` (identification holds 0.03–0.06 up to about 0.3 m/s, steering 0). The process opens a stage only with the committed
approval record (``s1-motion-approval.json``) naming it.

Validation order (the first failure is the reason):
  malformed, inhibited (runner lease lost) / no-runner, origin, duplicate, out-of-order,
  non-finite, future-request, stale-request, observation-identity, stale-observation,
  future-observation, then limit / motion-not-authorized (AVLite) or no-stage / stage-limit
  (calibration).
"""

from __future__ import annotations

from dataclasses import replace, dataclass, field
import math
import re

PROTOCOL = "roboracer.supervisor/1"
TOKEN = re.compile(r"^[A-Za-z0-9_.:-]{1,32}$")
STATES = ("waiting-runner", "active", "inhibited")
# Confirmed stage profiles (s1-motion-protocol.md v0.1 §4). Values are exact normalized commands.
STAGES = {"m0": {"throttle": (0.0,), "steering": (0.0, 0.1, -0.1, 0.5, -0.5, 1.0, -1.0)},
          "m1": {"throttle": (0.0, 0.002, 0.005, 0.01, 0.02), "steering": (0.0,)},
          "m2": {"throttle": (0.0, 0.01), "steering": (0.0,)},
          "m3": {"throttle": (0.0, 0.005, 0.01, 0.02), "steering": (0.0,)},
          "m3b": {"throttle": (0.0, 0.03, 0.045, 0.06), "steering": (0.0,)},
          # S3 speed proposal v0.1 (D38): identification holds up to ~0.6 m/s, steering 0.
          "m3c": {"throttle": (0.0, 0.08, 0.10, 0.12), "steering": (0.0,)},
          # S3 speed proposal V2 (D43): identification holds up to ~1.2 m/s, steering 0.
          "m3d": {"throttle": (0.0, 0.16, 0.20, 0.24), "steering": (0.0,)}}
# Confirmed S1-03 stages where AVLite target-speed requests drive the vehicle through the
# speed loop (s1-03-controller-proposal.md v0.2, D5/D8; approved "yes run M4 and M5").
AVLITE_STAGES = {"m4": {"max_speed_mps": 0.3, "max_steer_rad": 0.0},
                 "m5": {"max_speed_mps": 0.3, "max_steer_rad": 0.35},
                 # S1-05 lap proposal v0.1 (D10; approved "approve D9, D10, D11; run M6"): M5 limits.
                 "m6": {"max_speed_mps": 0.3, "max_steer_rad": 0.35},
                 # S3 B bring-up (s3-proposal v0.2, D32 A): the M6 limits, unchanged.
                 "s3b": {"max_speed_mps": 0.3, "max_steer_rad": 0.35},
                 # S3 speed step V1 (s3-speed-proposal v0.1, D35-D37): 0.5 m/s, u_max 0.12, overspeed 0.7 m/s.
                 "s3v1": {"max_speed_mps": 0.5, "max_steer_rad": 0.35, "u_max": 0.12, "overspeed_abs_mps": 0.7},
                 # S3 speed step V2 (s3-speed-v2-proposal v0.1, D40-D41): 1.0 m/s, u_max 0.24, overspeed 1.2 m/s.
                 "s3v2": {"max_speed_mps": 1.0, "max_steer_rad": 0.35, "u_max": 0.24, "overspeed_abs_mps": 1.2},
                 # S3-03: the V1 envelope with B on ICP pose (first S3-result laps).
                 "s3v1i": {"max_speed_mps": 0.5, "max_steer_rad": 0.35, "u_max": 0.12, "overspeed_abs_mps": 0.7}}
STEER_LIMIT_RAD = 0.5235987755982988  # normalized steering 1.0 (M0)


@dataclass(frozen=True)
class SpeedLoopParams:
    """D5 (v0.2) with K measured in M3/M3b. All per unit normalized throttle."""
    gain_mps: float = 5.02          # steady speed per unit throttle (M3b, M3 corrected)
    ki: float = 0.10                # integral trim per (m/s * s)
    trim: float = 0.01              # |integral trim| bound (about 0.05 m/s)
    u_max: float = 0.07             # about 0.35 m/s
    rise_per_s: float = 0.10        # 0.02 per 0.2 s frame
    overspeed_margin_mps: float = 0.15
    overspeed_abs_mps: float = 0.5
    # v0.3 (confirmed "yes rerun M4"): measured feedback age reaches 0.56 s at request time
    # (frame period p95 284 ms + ~155 ms delivery), so 0.4/0.6 s braked routinely.
    stale_ns: int = 600_000_000     # older feedback -> zero throttle (hard brake)
    lost_ns: int = 900_000_000      # older feedback -> inhibit (sticky)


class SpeedLoop:
    """Target speed -> normalized throttle: static inverse feedforward plus bounded integral
    trim, rise limit, overspeed and stale-feedback rules. Zero throttle is a hard brake."""

    def __init__(self, params: SpeedLoopParams = SpeedLoopParams()):
        self.p = params
        self.episode: int | None = None
        self.episode_restarts = 0
        self._restart()

    def _restart(self) -> None:
        """Start-up state: no feedback yet (zero throttle, not a loss), no trim, no rise history."""
        self.trim = 0.0
        self.last_u = 0.0
        self.last_ns: int | None = None
        self.speed = self.stamp_ns = self.seq = self.dt_s = None
        self.integrated_seq = None

    def observe_episode(self, episode) -> None:
        """S2 batches: a scene reload (new simulator episode) restarts the loop as at start-up. The GUI
        Reset leaves seconds without telemetry, so the previous episode's feedback would otherwise read
        as lost (sticky inhibition) on the first request of the next episode. Feedback loss within an
        episode is still detected; an older episode never takes the loop back."""
        if isinstance(episode, bool) or not isinstance(episode, int):
            return
        if self.episode is not None and episode > self.episode:
            self._restart()
            self.episode_restarts += 1
        if self.episode is None or episode > self.episode:
            self.episode = episode

    def feedback(self, speed_mps: float, stamp_ns: int, seq: int, dt_s: float, episode=None) -> None:
        if episode is not None:
            self.observe_episode(episode)
            if episode != self.episode:
                return  # a late sample of an earlier episode
        if math.isfinite(speed_mps) and dt_s > 0:
            self.speed, self.stamp_ns, self.seq, self.dt_s = speed_mps, stamp_ns, seq, dt_s

    def command(self, target_mps: float, now_ns: int) -> tuple[float, dict]:
        p = self.p
        age = (now_ns - self.stamp_ns) if self.stamp_ns is not None else None
        info = {"target": target_mps, "speed": self.speed, "feedback_age_ns": age, "feedback_seq": self.seq}
        if age is None:
            # Before the first sample (speed needs two snapshots): zero throttle, not a loss.
            u, info["rule"] = 0.0, "no-feedback-yet"
        elif age > p.lost_ns:
            u, info["rule"] = 0.0, "feedback-lost"
        elif age > p.stale_ns:
            u, info["rule"] = 0.0, "stale-feedback"
        elif target_mps == 0:
            self.trim, u, info["rule"] = 0.0, 0.0, "target-zero"
        else:
            error = target_mps - self.speed
            saturated = (self.last_u >= p.u_max and error > 0) or (self.last_u <= 0 and error < 0)
            if self.seq != self.integrated_seq and not saturated:
                self.trim = max(-p.trim, min(p.trim, self.trim + p.ki * error * self.dt_s))
            self.integrated_seq = self.seq
            if self.speed > target_mps + p.overspeed_margin_mps or self.speed > p.overspeed_abs_mps:
                u, info["rule"] = 0.0, "overspeed"
            else:
                u = max(0.0, min(p.u_max, target_mps / p.gain_mps + self.trim))
                # The first command counts as one request period (0.1 s) after a zero command.
                elapsed_s = (now_ns - self.last_ns) / 1e9 if self.last_ns is not None else 0.1
                u = min(u, self.last_u + p.rise_per_s * elapsed_s)
                info["rule"] = "control"
        u = round(max(0.0, u), 5)
        self.last_u, self.last_ns = u, now_ns
        info.update(u=u, trim=self.trim)
        return u, info


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
    control: dict | None = None


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
    speed_loop: SpeedLoop | None = None

    def __post_init__(self):
        if not TOKEN.match(self.origin):
            raise ValueError("origin must be a guard token")
        if self.stage is not None and self.stage not in STAGES and self.stage not in AVLITE_STAGES:
            raise ValueError(f"unknown stage {self.stage!r}")
        if self.stage in AVLITE_STAGES and self.speed_loop is None:
            overrides = {k: v for k, v in AVLITE_STAGES[self.stage].items() if k in ("u_max", "overspeed_abs_mps")}
            self.speed_loop = SpeedLoop(replace(SpeedLoopParams(), **overrides))

    def feedback(self, speed_mps: float, stamp_ns: int, seq: int, dt_s: float, episode=None) -> None:
        """Supervisor-owned encoder speed (D4 A); only used by the AVLite speed loop."""
        if self.speed_loop is not None:
            self.speed_loop.feedback(speed_mps, stamp_ns, seq, dt_s, episode)

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
        control = None
        if kind == "calibration":
            if self.stage is None or self.stage not in STAGES:
                return self._reject("no-stage")
            profile = STAGES[self.stage]
            if float(first) not in profile["throttle"] or float(second) not in profile["steering"]:
                return self._reject("stage-limit")
            throttle, steering = _text(float(first)), _text(float(second))
        elif self.stage in AVLITE_STAGES:
            profile = AVLITE_STAGES[self.stage]
            speed, steer = float(first), float(second)
            if speed < 0 or speed > profile["max_speed_mps"] or abs(steer) > profile["max_steer_rad"]:
                return self._reject("stage-limit")
            self.speed_loop.observe_episode(obs.get("episode"))  # the request's observation episode (S2)
            u, control = self.speed_loop.command(speed, now_ns)
            if control["rule"] == "feedback-lost":
                self.state, self.reason = "inhibited", "feedback-lost"
                return self._reject("feedback-lost")
            throttle, steering = _text(u), _text(round(steer / STEER_LIMIT_RAD, 6))
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
        return Decision(True, "forwarded", forward, control)

    def status(self) -> dict:
        return {"protocol": PROTOCOL, "origin": self.origin, "stage": self.stage, "state": self.state,
                "reason": self.reason, "runner_seq": self.runner_seq, "request_origin": self.request_origin,
                "request_seq": self.request_seq, "out_seq": self.out_seq, "counters": dict(self.counters),
                "speed_loop": ({"episode": self.speed_loop.episode, "episode_restarts": self.speed_loop.episode_restarts}
                               if self.speed_loop is not None else None),
                "limits": {k: getattr(self.limits, k) for k in self.limits.__dataclass_fields__}}


def _text(value: float) -> str:
    """Exact normalized value for the guard's wire format ("0" for zero, never "-0")."""
    return "0" if value == 0 else repr(value)
