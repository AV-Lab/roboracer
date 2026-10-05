# Development Plan v1.0 — Approval Summary

**Execution update, 2026-10-05:** SIM0 complete after option A (inherited creep, 10 mm P0 bound); the user's “go on the development plan” accepted SIM0 and entered SIM1. SIM1-01 (source provenance) and SIM1-02 (receiver guard and lease, disarmed) pass; amendment 6/10. [SIM0](../stages/SIM0-completion.md), [SIM1-01](../stages/SIM1-provenance.md), [SIM1-02](../stages/SIM1-guard.md). Next: SIM1-03 disarm/reset/epoch/rearm, still disarmed.

Date: **2026-09-28**. Status: **approved by the user's explicit response; PRE + S1 authorized**. The [full plan](development-plan.md) defines the contracts, 34 todos, measurements, evidence and stage gates. The [decision record](../research/decision-follow-up.md) distinguishes confirmed choices from runtime evidence. Numerical motion limits remain subject to the stated pre-motion gate.

**Sequencing decision, 2026-09-29:** the user explicitly retained complete PRE before S1. [S1a/deferral draft 1.1-B](installed-binary-first-amendment.md) is not adopted. Continue the reviewed [SIM0/SIM1 source-build route](simulator-build-amendment.md), retaining stage-entry and numerical motion gates. Pinned Editor startup is verified and **SIM0-01 is accepted**. Windows is unavailable; the subsequent native-track recovery scope is approved. Its acceptance remains subject to the execution update above. Source-build acceptance now follows the execution update above; neutral-run acceptance remains open.

## Confirmed delivery and architecture

Release 1 delivers simulation qualification for a future physical RoboRacer stack. It uses the existing AutoDRIVE installation, ROS 2 Humble, imported maps/reference paths, plugin-level reuse/extension of AVLite ICP, Pure Pursuit-based tracking, target-speed/steering commands and an independent command-supervision process. Hardware stop remains independent and is outside simulation qualification.

The minimum coverage is **one qualified track C0, five reproducible initial conditions, and left-pass/right-pass/fully-blocked static-obstacle cases**. Passable cases require avoidance and resumed progress; full blockage requires stopping. Unattended runs may use a qualified graphical session or virtual display. The user accepts configured initial pose and stopping with manual reinitialization/rearm after detected ICP loss.

Dynamic obstacles, multi-car interaction, multi-track generalization, automatic global localization/recovery, Gym, PF/AMCL, real-car integration/testing and GitHub publication are outside mandatory release-1 delivery. The future event/year/category remains undecided; this release makes no future-rule compliance or real-car performance claim.

## Demonstrable stages

| Stage | Feature delivered | Main acceptance coverage |
| --- | --- | --- |
| S1 | AVLite loads the plugin and closes the loop through Humble and AutoDRIVE, with GT-labelled reactive A, command supervision, stopping and result export. | Three valid circuit demonstrations; each F1 fault three times; five timing/resource runs. |
| S2 | One entrypoint runs unattended episodes, records/replays inputs, owns processes and handles defined failures. | Ten healthy unattended episodes; each F2 fault three times; five timing/resource runs; three fresh-process replays per selected fixture. |
| S3 | Known-map B drives with extended ICP and Pure Pursuit using allowed observations. | Five initial conditions × ten repetitions × A/B = **100 episodes**; each F3 case three times. Both A/B use the same qualified ICP/motion-state provider, with GT filters off. |
| S4 | B avoids passable static obstacles and stops when fully blocked. | T1/T2/T3 × ten repetitions = **30 episodes**; each F4 fault three times. |
| S5 | A fresh dependency environment reproduces the release, including standard AVLite GUI/profile checks and export. | Frozen regression fixtures and faults; three fresh-environment nominal laps; one run of each T case; two held-out C0 cases × five = **10 held-out episodes**. The nominal laps also serve as the fresh-environment smoke runs. |

M1/M2 timing runs each use 10 seconds of warm-up followed by 120 seconds of wall-time measurement. These are experiment durations, not achieved performance or permission to move. Behavioral episodes have independent progress, terminal-failure and maximum-duration rules. Failed initialization, contact, off-track, localization loss and timeouts remain recorded; healthy unattended batches cannot hide manual failure recovery.

Baseline runs are separate from acceptance. Unknown numerical performance targets must be measured, proposed, confirmed and then tested with frozen criteria. No lap-time, localization-error, completion-rate or latency target has been invented. All stages stop for review and explicit next-stage confirmation.

## Authorized scope

The user approved v1.0 and entry to **PRE + S1** within the existing filesystem/access constraints:

- Preserve repository state; implement the plugin, tests and reusable evaluation tools in the workspace; keep runtime results and isolated dependency environments in permitted paths.
- Identify/pin the matching official Devkit/API and required dependencies; download/build them in isolated environments, without changing the borrowed A2RL venv, AVLite core or existing simulator installation.
- Inspect and record commands, launch arguments, writes, ports and process ownership; perform bounded owned-process startup/shutdown and disarmed sensor observations through Humble using the permitted display mode.
- Prepare the concrete simulated-motion protocol. **Numerical speed/steering/slew/duration, freshness/expiry and stop limits require confirmation before any motion command.** Once confirmed, implement and validate S1 within those limits without repeated questions about routine details.

An access denial, unsupported required capability or material architecture/acceptance change pauses the affected work. No global package installation, privileged container, blanket network/display permission, user-session termination, physical actuation or publication is authorized by this plan. S2 entry requires a separate confirmation after the S1 report.

## What remains to be established by engineering

The [PRE report](../stages/PRE.md) records isolated dependencies, GPU/display/DDS access, continuous disarmed live data and two static Reset/reconnect observations. A narrow Devkit overlay resolves attrdict compatibility, TF publisher growth and shutdown. PRE-01/02 passed; 32 original todos remain unchecked. Actual acquisition identity/time, downstream expiry/stop, full geometry/scoring and requested scene initialization remain unqualified. The [selected source-build route](simulator-build-amendment.md) has SIM0-01 accepted. The approved track recovery has passed native generation/repetition and primary scene checks; final clean import, build and both neutral trials remain required. SIM1 requires its later stage-entry review. No motion or closed-loop/plugin acceptance is established.

If qualification fails, report evidence and alternatives; do not silently substitute Gym, change ROS, patch core interfaces or reduce acceptance. These are named execution gates, not additional unresolved product-preference questions.

**Approval recorded:** the user's explicit “Approved” response authorizes the [v1.0 plan](development-plan.md) and scoped PRE + S1 work. No repeated approval is needed for routine actions within that scope. Motion-protocol, performance-threshold and later stage-entry gates remain in force.
