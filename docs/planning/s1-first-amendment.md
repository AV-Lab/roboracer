# S1 Before Remaining PRE — Sequencing Amendment

Version: **1.2 — adopted**, 2026-10-05. Related: [approved v1.0](development-plan.md), [source-build route](simulator-build-amendment.md), [not-adopted S1a proposal](installed-binary-first-amendment.md).

## Decision

On 2026-10-05, after SIM1-02 passed, the user asked to postpone the PRE stage and start S1 immediately. Given three options, they selected **"Start S1 on the SIM1-02 build"**. This supersedes the 2026-09-29 instruction to complete PRE before S1.

## What changes

- **S1 entry.** S1 is entered now. Its v1.0 dependency on PRE-03/04 becomes a dependency of **S1 acceptance**, not of S1 entry.
- **Backend.** S1 runs on the source-built **SIM1-02 player** (`roboracer.sim1/1` provenance and the `roboracer.guard/1` receiver guard), not on the installed binary. This differs from the earlier S1a proposal: source acquisition identity and receiver-side expiry are already available.
- **Postponed.** These remain open and keep their stated criteria:
  - SIM1-03: reset, epoch and rearm;
  - SIM1-04: evaluator truth, geometry, contact and progress;
  - SIM1-05: motion protocol, P1b and PRE-03/04;
  - SIM1-06: backend publication.

  They are resumed when S1 needs them, or before S1 acceptance.
- **Motion gate.** The concrete numerical motion protocol (speed, steering, slew, duration, clearance, request/observation age, expiry, stop window and containment) becomes **S1's first deliverable**. No command that can move the vehicle is sent before the user confirms it. Until then the guard's zero-output interlock stays on (`-roboracerMotionAuthorized` is not passed).

## What does not change

- **Acceptance.** All S1 and M1 acceptance criteria, F1 fault coverage and the 34 original todos are unchanged. S1 cannot be marked complete while required scoring, stop qualification or reset/initialization evidence is missing.
- **Unverified metrics.** Lap, contact and off-track results without a qualified scorer are recorded as unverified, never as passes.
- **PRE-03/04** stay unchecked until their own evidence exists. Work done for S1 may supply that evidence only if it meets their unchanged criteria.
- **Architecture.** The independent supervisor process, target-speed/steering semantics, GT labelling, import-safe plugin structure and no-core-change rule all remain.
- **Later stages.** S2–S5 keep their entry gates.

## Order of work

1. **No motion:** S1-01 plugin loading, registration and settings; command-consumer compatibility.
2. **No motion:** S1-02 bridge observation path on the guarded player, with analytical fixtures.
3. **No motion:** the S1 supervisor skeleton.
4. **Draft the numerical motion protocol** from SIM1-02 evidence and stop for confirmation.
5. **After confirmation:** command signs, units and stop qualification; S1-03 onward.
