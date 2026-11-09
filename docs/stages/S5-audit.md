# S5-05 audit (D75): todos, evidence, metrics, deviations

Audit of the project record for release 1. Offline only; no motion.
- **Evidence:** `artifacts/s5/20261109T-s5-05-audit/`.
- **Tool:** `scripts/roboracer_s5_audit.py`, read-only.

## 1. Evidence paths and manifests

`scripts/roboracer_s5_audit.py` scans every `docs/**/*.md`, `release/README.md` and `roboracer/README.md` for cited `artifacts/...` paths. Each path must exist, and each cited evidence directory must still verify against its `MANIFEST.sha256`.

| Check | Result |
| --- | --- |
| Documents scanned | 78 |
| Cited evidence paths | 375; **0 missing** |
| Excluded as not evidence (with the reason recorded) | 3: two template placeholders (`.../`, `REPLACE_WITH_RUN_ID`); `artifacts/s1a/`, the planned output of the inactive S1A amendment |
| Evidence manifests verified | **60, 18,776 files, 0 problems** (every listed file present with its recorded sha256) |

Report: `evidence-audit.json`.

## 2. Todos

- **Code:** no `TODO`, `FIXME` or `XXX` markers in `roboracer/` or `scripts/`.
- **Plan:** the only unchecked boxes in `docs/planning/development-plan.md` are S5-01 to S5-05. They are ticked at the S5 review.
- **Inactive amendment:** `installed-binary-first-amendment.md` has unchecked S1A boxes, but it was never adopted (its line 5).

## 3. Deviations register

Every deviation from a plan, protocol or decision text, with where it was reported and how it was settled.

| # | Stage | Deviation | Settled |
| --- | --- | --- | --- |
| 1 | S1-06 | The F1-2 and F1-4 fault hooks wrap the stack's instances instead of adding hooks to the plugin source. The NaN-scan rejection reason is the scan-layout check. | Decided before any F1 run ([S1-06 M1 progress](S1-06-M1-progress.md)); S1 accepted |
| 2 | S2 | F2-4 ends the episode, and the next one starts after a GUI Reset, instead of re-arming within the episode. F2-5 likewise. | Reported ([S2 "Deviation from proposal §5"](S2.md), [S2 completion](S2-completion.md)); S2 accepted |
| 3 | S3 | No lattice local planner in the S3 stack (D30 named it). | Accepted as "deferred to S4" ([S3 completion §5.1](S3-completion.md)); the lattice was added in S4 |
| 4 | S3 | Stale velocity feedback was inherited from S1/S2, not re-run with B. | Reported ([S3 completion §5.2](S3-completion.md)); S3 accepted |
| 5 | S4 | No separate whole-footprint check (D57); AVLite's corridor test is used instead. | Accepted at S4 review ([S4 completion §5.1](S4-completion.md)). **S5 finding:** that corridor models the car as centred on the path, which allowed the late detour behind H2 (D78; [S5 §11](S5.md)) |
| 6 | S4 | Fixtures go through `--obstacle-fixture`, and they are virtual (D54 A), not simulator scene objects. | Accepted ([S4 completion §5.2](S4-completion.md)) |
| 7 | S4 | Edge-on clusters keep their observed face length (AVLite substitutes a 4.5 × 2.0 m box). | Recorded ([S4](S4.md)) |
| 8 | S5 | D69 froze the release candidate; **D78 lifted the freeze** to fix the H2 failure, and D79 changed the bounds. | Decisions D78 A, D79 A; re-qualified ([S5 §18–§21](S5.md)) |
| 9 | S5 | **U3 changed after H3 failed it:** gap-tiered U3, with narrow gaps under U3n (D80 A). | Stated openly before H4 was run ([S5 §16–§17](S5.md)) |
| 10 | S5 | D68 is strict, but one infrastructure-stopped episode was re-run (D81 A). | The stopped run is retained and counted; the re-run decided the item ([S5 §19–§21](S5.md)) |
| 11 | S5 | H2 was planned as held out (D72), but was used to develop the D78 fix. H3 then became the held-out case, and H4 after D79. | Each new held-out case was drawn by a committed rule and sealed before the change ([S5 §10, §14](S5.md)) |
| 12 | S5 | F2 was not re-run with profile B in M5. | Recorded as unverified ([S5 §8](S5.md); [release limitations](../../release/README.md)) |

## 4. Corrections on record

The approval record (`docs/planning/s1-motion-approval.json`, `corrections`) holds two:
1. **AVLite pin (D69):** the pin is `50dcd00`; the earlier `c8b0ce1` does not exist.
2. **H2 cause:** S5 §5, §8 and §9 said H2 failed because the track narrows. It does not: the committed detour came too late, and the latch fired beside the box ([S5 §11](S5.md)).

## 5. Metrics of record (release 1)

All from the fresh environment; worst value over the runs, against its criterion.

| Metric | Value | Criterion | Evidence |
| --- | --- | --- | --- |
| Clear-lap time | 68.0–68.4 s | ≤ 72 s (U6) | `20261102T153137Z-d80-requal` |
| Wall clearance, clear lap / T1 / T2 / T3 | ≥ 0.290 m | ≥ 0.20 m (U3) | same |
| Obstacle clearance T1 / T2 / H2 (full tier) | 0.302 / **0.279** / **0.257** m | ≥ 0.25 m (U3) | same |
| H4 / H3 (narrow tier): obstacle, wall | 0.159 / 0.253 m obstacle; 0.296 / 0.176 m wall | ≥ 0.10 m (U3n) | same |
| T3 and F4-1 at rest | ≥ 1.311 m | ≥ 1.0 m (U4) | same |
| ICP error max | ≤ 0.117 m | ≤ 0.15 m (U5) | same |
| Stack tick max | ≤ 53 ms | ≤ 80 ms (U7) | same |
| Peak heading error | ≤ 0.175 rad | safe stop at 0.35 rad | same |
| Held-out start H1, lap from the IC | 62.84–62.96 s; clearance ≥ 0.314 m | S3 T1–T8 | `20261102T062705Z-m5-rerun` |

## 6. Runner main-loop stall (D81): finding

- **What happened:** s1-t1-r02 stopped when the supervisor's runner lease expired. The runner withheld 95 heartbeats while driving ([S5 §18, §20](S5.md)).
- **Exact time:** from the run's monotonic-to-UTC anchors (start 15:42:34.62 UTC, observation 13.43 s later), the expiry was at **15:43:34.3 UTC**.
- **What the system journal shows in that second:**
  - `systemd[1]: Reloading.` (a daemon reload; there was another at 15:43:35);
  - a snap auto-refresh of `obsidian` (snap mount and an apparmor profile reload);
  - the start of `apt-daily` and of `fwupd-refresh`.
- **Interpretation:** this is a strong correlation, not a proof. Host maintenance (snapd/systemd reloads) briefly starved the runner's main loop.
- **Mitigation (a host setting, so the owner's decision; not changed here):** hold snap auto-refresh and the apt timers during run sessions, for example `snap refresh --hold` and stopping `apt-daily.timer` / `apt-daily-upgrade.timer`.
- **Not a stack problem:** the fail-safe worked as designed; the car stopped at rest, and the stack was unaffected.
- **Recording:** since D81 the runner records every main-loop gap over 0.2 s while heartbeats are due (`run.json` `runner_heartbeat.long_gaps_while_due`). The Connect gap is also counted there; tell it apart by time.

## 7. Items carried into the release limitations

All of §3 #5, #9 and #12, the thin margins in §5, and §6 are listed in the [release operations guide](../../release/README.md) §7.
