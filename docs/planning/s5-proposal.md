# S5 proposal — reproducible AutoDRIVE-qualified release

Version **0.1, 2026-11-01**. Entry: S4 accepted, then S5 approved ("accept, go ahead S5"). **No motion and no environment change is proposed in this document.** Every run set will need its own approval.

**S5 goal (plan):** a clean plugin environment connects to the identified AutoDRIVE distribution, reproduces the frozen qualification suite, and exports a reviewable comparison through one entrypoint.

**Non-goals:**
- redistributing the simulator;
- GitHub publication;
- real-car certification;
- future-event compliance.

## 1. Where things stand

| Part | Today | Gap for S5-01 |
| --- | --- | --- |
| AVLite environment | `preflight-20260928T113745Z/avlite-venv` (26 packages + AVLite; *corrected from 173, see S5 §1*); AVLite source pinned: AVLite `50dcd00` (package metadata 0.6.3; the PRE tarball's `git archive` commit). *Corrected 2026-11-01: earlier text said `c8b0ce1`, which does not exist in the AVLite repository.* | no lock file in the repository; built by hand in PRE |
| Devkit environment | `preflight-20260928T120809Z/devkit-venv` (16 packages; *corrected from 162*); colcon build of the pinned Devkit; compatibility overlay; attrdict patch (file hashes recorded in `run-context.json`) | the PRE freeze exists only as evidence (`devkit-freeze-after-repair.json`); no rebuild script |
| Simulator | patch-04 player, frozen (D18); identity in `artifacts/sim1-06/.../player-files.sha256` (604 files) | already verifiable; it is provided separately, not rebuilt (plan) |
| Plugin | `roboracer/` in this repository | no packaging metadata; installed by AVLite's plugin loader from a path |
| Pip cache | empty | **a fresh rebuild needs PyPI or a local wheelhouse (D70)** |

## 2. Decisions requested

- **D69 — release candidate.** Freeze the code at the S5 entry commit:
  - **recommended profile:** B on map ICP, V1 envelope;
  - **with S4:** obstacle detection, the C0 lattice and the D58 blocked stop (stage `s4` without a fixture = a clear track);
  - **pins:** AVLite `50dcd00` (corrected; see §1), A2RL port provenance `0b5cfa8` / `fe2fc01`, Devkit 0.3.0 with overlays, player patch 04.

  After D69, no algorithm or configuration change before the held-out M5 evaluation (S5-02).
- **D70 — dependency locks and the fresh environment:**
  - **A (recommended):** export exact locks now from the two qualified venvs (`pip freeze --all` with versions) and commit them. Download wheels for them **once from PyPI** into a local wheelhouse under `~/roboracer-work`, record the sha256 of every wheel, then build the fresh environment **offline from the wheelhouse** (`pip install --no-index --require-hashes`).
  - **B:** rebuild directly from PyPI at install time, with hashes. This depends on PyPI at every rebuild.
  - **C:** no network: copy the existing venvs. This is not a rebuild and does not meet S5-01.
  - The Devkit colcon build, overlay and attrdict patch are scripted from the recorded hashes. The simulator is verified by its 604-file sha256 list.
- **D71 — single entrypoint (S5-03):** `scripts/roboracer.py` with subcommands:
  - `live` (a stage episode with export);
  - `replay` (recorded-input, open-loop);
  - `export`;
  - `compare` (A/B or run-to-run summary from episode exports).

  It wraps the existing tools and does not change production defaults.
- **D72 — M5 run set (plan, frozen before running):**
  - **regression:** 3 nominal B laps (stage `s4`, no fixture); T1, T2 and T3 once each; every applicable F1–F4 case once with B (F1-1, F1-3, F1-7 on V1/ICP; F2 cases as recorded in S2 for the batch runner; F3-1/2/3; F4-1/2/3); and the frozen fixtures re-run offline (interface, map, truth isolation, replay);
  - **held-out:** **H1** = start from a new initial condition at s = 21.875 m (between the M3 ICs, never used) via the D49 approach; **H2** = T1 with the box at s = 8.0 m instead of 7.5 m (a held-out obstacle placement). Each × 5 with B. They are labelled held-out on the same layout, not unseen-map evidence.
  - **three fresh-environment smoke runs:** these are the three nominal laps above, run from the D70 fresh environment, not counted twice.
- **D73 — release thresholds (frozen before M5):** reuse the accepted criteria:
  - laps and held-out H1: S3 T1–T8 (D48), on the clear track;
  - T1/T2/T3 and H2: S4 U1–U7 (D66);
  - F cases: their stage criteria (D37/D39 B, D50, §11);
  - fixtures: exact, as recorded.

  The rule is strict, as D52/D68.
- **D74 — GUI and settings check (S5-04):** in an isolated AVLite profile on desktop `:1`, show the plugin and its strategies visible in AVLite's standard GUI, and the plugin's settings edited, saved and reloaded. The evidence is screenshots plus the saved profile files. There is no motion and no custom dashboard. This needs the desktop for a few minutes, as for the simulator.
- **D75 — documentation and audit (S5-04, S5-05):**
  - supported versions;
  - launch and reset;
  - calibration boundaries and limitations;
  - an audit of every todo, evidence path, metric and deviation;
  - a private-repository-ready working tree on a branch.

  **Nothing is published.**

## 3. Order of work (after D69–D75)

1. Locks, wheelhouse and the rebuild script; build the fresh environment and verify it (no motion): imports, plugin registration, offline fixtures.
2. The entrypoint `scripts/roboracer.py`, with tests.
3. GUI and settings check (D74).
4. **Run approval:** M5 regression, held-out cases and the smoke runs, from the fresh environment.
5. Documentation, audit, release tree; then the S5 review.
