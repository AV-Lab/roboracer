# S5 — Completion report and stage review

Date: **2026-11-09**.
- **Running report, with every run:** [S5.md](S5.md).
- **Audit:** [S5-audit.md](S5-audit.md).
- **Proposal:** [s5-proposal.md](../planning/s5-proposal.md) (D69–D75).
- **Decisions:** D69–D81, in the [approval record](../planning/s1-motion-approval.json).
- **Operations guide:** [release/README.md](../../release/README.md).
- **Backend:** the frozen patch-04 player (D18), unchanged after every S5 run.

**S5 goal (plan):** a clean plugin environment connects to the identified AutoDRIVE distribution, reproduces the frozen qualification suite, and exports a reviewable comparison through one entrypoint.

## Summary

- **All five S5 items are delivered.** Every release criterion passes from the fresh environment. Two of those criteria were changed during S5, both by your decisions, and are stated below.
- **Fresh environment:** rebuilt offline from hashed locks (D70) and verified 7/7. The simulator's 604-file identity was checked, not rebuilt.
- **The held-out evaluation did its job: it found real stack problems, and they were fixed.**
  1. **H2 0/5 (M5):** the lattice committed to its detour too late, and its blocked latch fired beside the box. Fixed by D78 A: early avoidance, a gated latch with a stop-distance guard, AVLite's overtake mode off, and a wall inset equal to the U3 wall margin. H3 was drawn and sealed before the fix.
  2. **H3 0/5 on the wall:** the racing plan's boundary data is up to 0.24 m outside the real walls. Fixed by D79 A: lattice bounds built from the map. H4 was drawn and sealed before the change.
  3. **The narrow-gap mismatch:** with about 0.07 m of controller tracking error, U3 needs a passing gap of about 0.88 m, but the fixture rule admits gaps down to 0.49 m. **Decided by D80 A: U3 is gap-tiered**, and narrow gaps are held to U3n (0.10/0.10 m). This criterion changed after H3 failed it; that is stated openly.
- **Final qualification of the release stack** (fresh environment, D73 strict):

| Item | Result |
| --- | --- |
| M4 matrix (T1/T2/T3 × 10) | 30/30 (with the D81 re-run) |
| F4 | 9/9 |
| Clear laps | 3/3 |
| **Held-out H4** | **5/5** |
| H3, H2 (development cases) | 5/5 each |
| F1, F3, held-out H1 (§8; stages without the lattice) | pass |
| Offline | all pass |

- **One infrastructure stop:** in s1-t1-r02, a runner main-loop stall expired the supervisor lease, and the car stopped safely. It is retained and counted; one T1 re-run decided the item (D81 A). The stall coincides to the second with host maintenance: a systemd reload and a snap auto-refresh ([audit §6](S5-audit.md)).
- **No failure is waived.** Every attempt is retained: M5 attempt 1 (no run started), H2 0/5, H3 0/5, and the runner-lease stop.
- **Nothing was published.** The private-repository-ready tree is the local branch `release-1`, and a clean clone of it passes all tests.

## 1. S5 items

| Item | Delivered | Evidence |
| --- | --- | --- |
| **S5-01** fresh environment from locks; simulator identity; installation and registration | Locks and a one-time wheelhouse, then an offline hashed rebuild (`scripts/roboracer_s5_env.py`). Verify 7/7. Plugin registered in AVLite; the release profile loads | [S5 §2, §7](S5.md) |
| **S5-02** freeze before held-out M5; run the approved cases; keep every attempt | Frozen by D69; M5 run (§8). The freeze was lifted only by D78/D79 for the held-out findings, and each new held-out case was sealed before its change. Re-qualified | [S5 §8–§21](S5.md) |
| **S5-03** one entrypoint for replay, live export and A/B comparison | `scripts/roboracer.py` with `live`, `replay`, `export` and `compare`. Replay is exact; `compare` reproduces the S4 acceptance numbers; production defaults unchanged | [S5 §3](S5.md) |
| **S5-04** documentation; GUI visibility; settings in an isolated profile | [Operations guide](../../release/README.md) and [plugin README](../../roboracer/README.md). Strategies shown in AVLite's stock dropdowns; settings saved and reloaded through AVLite's own code path | [S5 §4, §22](S5.md) |
| **S5-05** audit; private-repository-ready tree | 375 cited paths and 60 manifests (18,776 files) verified; 12 deviations and 2 corrections registered; local branch `release-1` | [S5 audit](S5-audit.md), [S5 §23–§24](S5.md) |

## 2. Unverified, not skipped (plan acceptance clause)

- **Interactive settings editing in AVLite's settings window:** not done. Desktop `:1` is your live session, and synthetic clicks did not reach the Tk dialog. The same save and load code path was shown programmatically ([S5 §4](S5.md)).
- **Starting a live run from the AVLite visualizer:** not supported (D76). The bridge does not implement ground-truth perception, by design. The stage runner and `scripts/roboracer.py live` are the launch paths.
- **F2 with profile B:** its harness drives configuration A, so it is unverified with B ([S5 §8](S5.md)).

## 3. Deviations and changed criteria for your review

These are numbered as in the [deviations register](S5-audit.md) §3:
- **#8 — the freeze was lifted (D78, D79):** after the held-out failures, by your decisions; re-qualified afterwards.
- **#9 — U3 is gap-tiered (D80):** changed after H3 failed it. It is held to U3n (0.10/0.10 m) for passing gaps < 0.88 m.
- **#10 — one infrastructure-stopped episode re-run (D81):** under the strict rule (D68).
- **#11 — the held-out cases moved from H2 to H3 to H4:** each was drawn by a committed rule and sealed before the change it evaluated.

## 4. Limits to note at review

**Thin margins:**
- H2 obstacle clearance is 0.257 m, 0.007 m over U3.
- T2's worst is 0.279 m.
- D78 lowered pass clearances from 0.37–0.42 m to 0.29–0.34 m.

**Narrow gaps:** passes keep only 0.10 m guaranteed (U3n). Measured on H4: 0.159–0.168 m from the box.

**Licence:** the A2RL source export has no licence file. Its terms must be confirmed with AV-Lab before the repository is shared outside AV-Lab ([THIRD_PARTY.md](../../THIRD_PARTY.md)). No repository licence is declared.

**Host:**
- Runs need desktop `:1` left alone.
- Host auto-updates should be held during run sessions.
- Some script defaults point at this host's paths.

Full list: [operations guide §7](../../release/README.md).

## 5. Review requested

The S5 boxes in the plan now say "delivered; awaiting review". **I recommend you accept S5-01 to S5-05,** with the changed criteria in §3 and the unverified items in §2 as stated.

**If accepted:**
- the original plan goes to **34/34**;
- release 1 is the simulation-qualified boundary. The plan gate stops here: physical-car work needs a separate, approved later stage.

**Open choices for you, none of them required to close S5:**
- publish `release-1` to a private remote (not done; D75);
- the A2RL licence terms;
- a repository licence;
- holding host auto-updates during runs.
