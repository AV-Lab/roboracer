# Installed AutoDRIVE First — Proposed SIM1 Deferral

Version: **1.1-B, not adopted — decision history only**, 2026-09-29. [Chinese explanation](../stages/SIM1-deferral.zh-CN.md). Related: [approved v1.0](development-plan.md), [source-build route 1.1-A](simulator-build-amendment.md), [observed interface limits](../stages/PRE-interface-qualification.md).

**User decision:** continue the original plan, completing PRE before S1. This S1a dependency exception is not adopted. The four todos below are inactive proposal history and remain unchecked; do not implement them or include them in active-stage completion counts. The proposal text and former confirmation request below are retained for traceability.

**Recommendation: defer SIM0/SIM1 until after a bounded integration demonstration using the installed player. Preserve their affected acceptance obligations.** The user's question requests evaluation of this scheduling change; it is not recorded as final approval of the changed prerequisites, motion or implementation.

The installed player already supplies continuous neutral observations through the adapted Humble Devkit. The current evidence does not establish source acquisition freshness, receiver-side expiry, moving stopping behavior or complete scoring. These limitations prevent full v1.0 acceptance, but they need not prevent a separately labelled, bounded simulation demonstration after its own prerequisites are met.

## Proposed sequence

1. Qualify only the remaining prerequisites of an installed-player demonstration and prepare its numerical motion protocol.
2. Deliver **S1a: bounded installed-player integration demonstration**, described below. Review its results before entering further work.
3. Reassess each deferred capability against observed installed-player behavior and verified external tooling. Implement source changes only for requirements that those cannot satisfy. If needed, execute the separately approved SIM0 baseline build and SIM1 instrumentation stages.
4. Complete original PRE-03/04 and full S1 acceptance, then resume the original S2–S5 stage gates. Scenario-specific extensions can remain with their consuming stages. This proposal does not authorize starting all later stages before their dependencies pass.

SIM0 serves the source-build route, so it is also deferred. Installing/activating Unity is not a prerequisite for S1a. The original installation, Humble, AVLite plugin boundary, independent supervisor and selected racing strategy B remain unchanged; reactive A and explicitly labelled GT remain the early integration baseline.

## S1a — Bounded installed-player integration demonstration

**Feature:** AVLite loads the plugin, consumes actual local AutoDRIVE observations, produces target-speed/steering requests through the independent supervisor/backend conversion, and demonstrates observable short-course feedback and normal commanded stopping. This is a simulation integration feature; it does not certify the original fault-stop, source-freshness or full-lap criteria.

**Prerequisites:** explicit approval of this amendment; retain the scope-qualified PRE-01/02 evidence; verify command mode/sign/units, selected start/clearance and usable motion feedback; approve the separate numerical motion protocol before sending any motion command. Manual initial setup and one recorded fixed start are permitted for this proposed milestone. Missing indispensable control/feedback capability blocks the demonstration rather than authorizing guessed actuator semantics.

**Scope:** plugin discovery/configuration, isolated Humble bridge, explicit receipt-time observations, labelled early GT, reactive driving A, target-speed/steering conversion, independent command supervision, a bounded single-episode runner and result export. Keep code import-safe and follow the official plugin guide. Use the existing parameterized evaluation design rather than scripts per experiment.

**Retained controls:** validate finite/ranged requests, original request identity/age and receipt liveness; bound speed request, steering, slew and duration under the approved protocol; stop/disarm on invalid input or algorithm loss while the command path is alive; isolate and supervise owned simulator/bridge/supervisor processes. On loss of the final command path or an unverified stop, mark the episode failed and terminate only the owned simulation session under its approved containment deadline. This fallback does not constitute braking and cannot be reused as a physical-car stop argument. A live transport repeating old sensor data can remain undetectable without source identity; record that residual limitation explicitly.

**Evidence and acceptance D1:** three independently initialized short driving segments on the same recorded start/configuration, each demonstrating actual AVLite feedback control followed by a normal commanded stop under the frozen protocol. Record requested commands, observed motion, receipt intervals, terminal state, process cleanup and all failed attempts. The protocol must define segment duration/distance, physical bounds, observation windows and normal-stop tolerances before the tests. Require the agreed outcomes for all three segments; no invented lap-time or control-frequency target. A sensor-forwarding-only or direct actuator-only test is not an AVLite closed loop.

Test malformed/nonfinite requests, missing received observations and algorithm exit/hang three times per case through the guarded command path under that same protocol. State exactly which process remains alive to deliver the stop. Supervisor/Devkit-loss tests can establish detection/containment only until receiver expiry is qualified. Do not label them as passed braking tests. Compare analytical unit/frame fixtures using predeclared numeric tolerances. Truth, sample-age and motion-estimate limitations remain visible in the exported manifest.

**Non-goals:** source-acquisition-age guarantees, stopping after loss of every command sender, automatic scene setup, independently certified valid laps/collision-free/off-track metrics, unattended batches, ICP acceptance, real-car testing or race performance. Video and manual observation can illustrate the demo but cannot replace unqualified scoring. Record unavailable metrics as unverified, never as zero or pass.

**Deliverables/evidence:** documented invocation and profile, protocol, test results and per-run manifests under `artifacts/s1a/<run-id>/`; an English stage report plus Chinese explanation. Stop after the S1a review. Completion of this milestone does not complete PRE or original S1.

- [ ] S1A-01 — Qualify the installed-player demonstration prerequisites and obtain confirmation of the numerical motion protocol. **Blocked:** amendment approval; numerical bounds and essential actuation/feedback behavior remain unqualified.
- [ ] S1A-02 — Deliver plugin loading/configuration and the live Humble observation bridge, preserving honest receipt/source provenance and explicit GT labels. Verify registration/profile and frame/unit fixtures. **Depends on:** amendment approval; motion tests additionally depend on S1A-01.
- [ ] S1A-03 — Deliver reactive control through AVLite, target-speed/steering conversion, independent supervision and bounded owned-process containment. Pass the specified request/input/algorithm fault cases. **Depends on:** S1A-01/02.
- [ ] S1A-04 — Run D1's three short closed-loop/normal-stop demonstrations, retain failures and publish the stage report with deferred acceptance items. **Depends on:** S1A-03. Stop for the next-stage review.

## What is deferred, and what still blocks full acceptance

| Requirement | S1a treatment | Required before claiming the corresponding original acceptance |
| --- | --- | --- |
| Source acquisition sequence/time and coherent source age | Record receipt time; source age/unique acquisition rate remain unknown. Repeated publication is not treated as a newly proven acquisition. | Qualify an actual source identity/time interface, through existing capabilities if demonstrated or later instrumentation. Required for original PRE/S1 freshness and later fault acceptance. |
| Receiver-side command expiry | Independent supervisor handles upstream faults while alive. Final-path loss produces a failed, contained simulation session. | Verify downstream expiry and observed moving-stop behavior; containment does not satisfy it. |
| Normal command/stop response, usable motion feedback, units/limits | Must be qualified for the bounded demo; not deferred. | Original full-envelope and fault coverage still require their separate acceptance. |
| Complete C0 geometry/contact/off-track/lap scoring | Verify only the geometry/start/clearance needed for the approved short segment. Unavailable full metrics remain unverified. | Qualify independent full scoring before claiming original S1 circuit/M1 results. External tooling is acceptable when its inputs and correctness are verified. |
| Automated reset/start/scenario controls | Checked manual initialization for a single fixed start. | Qualified unattended initialization before S2 acceptance; five starts before S3; static fixtures before S4. A Unity modification is only one possible means of providing these capabilities. |

Original todos remain **34 total, 2 accepted**. The ten source-build draft todos remain unaccepted; these four new draft todos are separate. Work may later supply evidence for overlapping original items only if it actually meets their unchanged criteria; do not double-count a demonstration as complete S1/M1 coverage.

## Review and permission boundary

This revision changes sequencing and introduces a narrower intermediate feature. It does not delete original release obligations. Its benefit is earlier AVLite integration feedback without acquiring a Unity editor; its cost is provisional measurement/fault coverage and later requalification of a changed backend. Reuse the protocol/bridge/runner contracts to limit rework.

Proposed S1a writes, dependencies and owned-player/display/local-DDS access stay within the existing scoped permissions. No Unity installation, source instrumentation, physical device, core-interface edit or publishing is requested. The user's user-managed Unity activation question becomes relevant only when the source-build stage is resumed, not an immediate demonstration blocker.

**Confirmation requested:** adopt installed-player S1a first, defer SIM0/SIM1 as needed until after its review, and retain deferred original acceptance obligations. The material change is allowing this bounded milestone before full PRE-03/04; original v1.0 does not already authorize that dependency exception. Even after amendment approval, the concrete numerical motion protocol remains required before movement. No runtime behavior has been tested or acceptance status changed by writing this proposal.
