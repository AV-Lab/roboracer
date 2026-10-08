# SIM1-06 — Qualified backend and PRE completion report

Date: **2026-10-08**. Request: "go on with SIM1-06". **No motion and no simulator change.** Evidence: `artifacts/sim1-06/20261008T070835Z/`.

SIM1-06 item: *Publish the qualified backend and PRE completion/blocker report, update only justified original todos, and stop for the required stage review before the S1 feature work. No failed required case may be waived by relabelling containment as stopping.*

## Summary

- **Backend published:** [qualified-backend.md](../architecture/qualified-backend.md), with a machine-readable manifest.
  - The patch-04 player matches its build record.
  - All 11 committed patch and component files are byte-identical to what was built.
  - The repository tree was clean at the manifest commit.
- **PRE is complete on evidence.** PRE-03 and PRE-04 meet their unchanged criteria, and every remaining PRE blocker (B05, B07, B08, B09) is closed for the S1 scope.
- **No required case is waived.** All failures are retained. Simulator-hang containment is recorded only as containment.
- **Stage review: accepted 2026-10-08** ("accept all recommended boxes"). All boxes in §5 are ticked: **PRE and S1 are complete**. The original plan is at 10/34 and the amendment at 10/10.

## 1. SIM1 items

| Item | Status | Evidence |
| --- | --- | --- |
| SIM1-01 provenance | accepted 2026-10-05; rechecked on patch 04 (LiDAR freeze pass) | [SIM1-provenance](SIM1-provenance.md), [SIM1-03 §5](SIM1-03-reset.md) |
| SIM1-02 receiver guard | accepted 2026-10-05; rechecked on patch 04 (16/16 phases, 0 nonzero steps) | [SIM1-guard](SIM1-guard.md), [SIM1-03 §5](SIM1-03-reset.md) |
| SIM1-03 reset/epoch/rearm | **delivered**: reset 3/3 (19/19 checks each) on patch 04; F1-5 disarm/re-arm 3/3 under motion | [SIM1-03](SIM1-03-reset.md) |
| SIM1-04 evaluator truth and fixtures | **delivered**: 10/10 laps pass all fixtures | [SIM1-04](SIM1-04-evaluator.md) |
| SIM1-05 protocol, P1b, PRE-03/04 | **delivered**: every P1b case ×3; hang containment 3/3 (separate) | [SIM1-05](SIM1-05-motion-qualification.md) |
| SIM1-06 publication and this report | **delivered** | this report |

**P1a (disarmed) three-times rule:** SIM1-02 ran 17 cases ×3. Reset and replay ran ×3 (SIM1-03). Source freeze ran ×3 (SIM1-01).

**P1b (motion) three-times rule:**
- actuator: M0 ×3 and M3b ×3, plus M1 and M3 once each, superseded by M3b;
- stop and fault: F1-1 to F1-9 ×3;
- laps: M6 ×3 and D13 ×5.

## 2. PRE items

| Item | Criterion (unchanged) | Status |
| --- | --- | --- |
| PRE-01 | identities, process ownership, write paths | accepted (2026-09-28) |
| PRE-02 | pinned Devkit/API, isolated Humble dependencies, bounded startup/shutdown | accepted (2026-09-28) |
| PRE-03 | transport, frames, units, timestamps, command retention and stop response within an approved bounded motion envelope | **met**: [SIM1-05 §4](SIM1-05-motion-qualification.md) |
| PRE-04 | S1 scene/start/geometry, clocks, display mode, evaluator inputs, reset method | **met**: [SIM1-05 §4](SIM1-05-motion-qualification.md) |

## 3. PRE blockers

| Blocker | Was | Closed by |
| --- | --- | --- |
| PRE-B05 | no numerical motion protocol; signs, limits, braking and speed conversion unqualified | protocol v0.1 + D4–D19; signs and conversion M0/M1/M3b ×3; braking (D1) and stops M2, F1 ×27 |
| PRE-B07 | no acquisition timestamps, sequences, simulator clock or acknowledgement IDs | patch 01 provenance (`roboracer.sim1/1`); acquisition-time ROS headers; clock bound ≤ 42 ms in motion |
| PRE-B08 | no receiver lease; autonomous commands retained; no moving-stop test | patch 02 guard lease immediately before actuation; expiry under motion (M2, F1-3/6/7/8 ×3) |
| PRE-B09 | one fixed start, GUI Reset at rest; no initial-state, obstacle or event API | **for S1:** C0 start verified (offset 0.000 m), GUI Reset through the guard (3/3), independent geometric scorer (no GUI counters). **Not closed, and moved by amendment §4:** five initial poses (S3), obstacle placement (S4), unattended reset (S2). |

**PRE-B09 is closed only for what PRE-04 asks for S1.** Its other parts were always scoped to S2–S4 in the amendment's effects table. They remain open and are not claimed here.

## 4. What is not waived

These failures and exceptions are all retained and reported:
- F1-1 v0.1 failure (timed from the request; D17);
- M4 trials 1–4;
- M0 attempts 1–2;
- reset attempt 1 (tooling);
- the patch-03 reset failure that led to D18;
- 4/27 player shutdown hangs.

Simulator-hang containment is a separate outcome in SIM1-05 §1. Every stop result comes from guard expiry, supervisor inhibition or explicit zero/disarm, with observed rest.

## 5. Review requested

The original todos changed in text only: PRE-03 and PRE-04 now say "met; awaiting review" and link here. **I recommend you accept these boxes:**

| Box | Basis |
| --- | --- |
| SIM1-03, SIM1-04, SIM1-05, SIM1-06 (amendment) | §1 |
| PRE-03, PRE-04 (original) | §2–§3 |
| S1-02 to S1-06 (original) | stage reports S1-02 … S1-06, M1 results; S1 acceptance needed PRE-03/04 and SIM1-03–06, which are now met |

**If accepted:**
- original plan **3/34 → 10/34**: PRE-01–04 and S1-01–06, so PRE and S1 complete;
- amendment **6/10 → 10/10**.

**The next stage would be S2**, which needs your entry confirmation. Nothing beyond S1 has started.

## 6. Checks

- **Tests:** 131 script tests and 41 plugin tests pass.
- **Player:** 604 files unchanged.
- **Manifest:** generated at commit `7badad6`, with a clean tree.
