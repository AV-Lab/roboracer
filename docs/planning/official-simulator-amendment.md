# Amendment 1.3 (draft) — Integrate against the official AutoDRIVE simulator

Date: **2026-10-07**. Status: **not adopted.** The user chose D18 (patch and rebuild, then freeze the simulator) after the comparison; this draft is kept as decision history. Trigger: the user's direction after the SIM1-03 defect ([report](../stages/SIM1-03-reset.md)): *"It takes a lot of time to build a patched simulator. I think we shouldn't struggle on this; we should use the official simulator to integrate."*

This is option **B** of the [PRE interface qualification](../stages/PRE-interface-qualification.md): keep the installed official binary and **explicitly revise the acceptance criteria it cannot meet**. It replaces the source-build route ([amendment 1.1-A](simulator-build-amendment.md)) for all future work. No more simulator builds or vendor patches.

## 1. The official build

- **Location:** `/home/a2rl/Workspace/AutoDRIVE Simulator [Linux]/` (November 2023).
- **Fingerprints:** `AutoDRIVE Simulator.x86_64` sha256 `d31b1f58…`, `GameAssembly.so` sha256 `d7d095de…`.
- **Already qualified for:**
  - PRE-02, on 2026-09-28: the pinned Devkit plus our narrow overlays, isolated ROS 2 Humble, continuous disarmed data, bounded lifecycle;
  - the PRE neutral observation runs.

## 2. What the official build lacks, and how each gap is handled

| Patched-build feature | Official build | Proposed handling | What is lost |
| --- | --- | --- | --- |
| **In-simulator guard**: arming, epoch, lease ≤ 1 s, brake on expiry (SIM1-02) | None. The simulator keeps applying the last received throttle and steering (zero-order hold). | **Bridge-side lease (D19).** Our Devkit bridge process is the only sender. In every paced reply it sends a nonzero command only while the supervisor's latest request is within its 500 ms life; otherwise it sends exact zero (the brake). The supervisor, runner lease and stack limits are unchanged. | Faults *upstream* of the bridge (stack, supervisor, runner) still produce a commanded stop. If the **bridge itself** dies or hangs, the simulator keeps the last command. The only remedy is a separate **watchdog** that kills the simulator: containment, not braking. That case can no longer pass as "stop". |
| Per-sensor acquisition stamps, episode identity (SIM1-01) | Telemetry carries values only | Ages are measured from **receipt time** at the bridge. A frozen sensor is detected by **unchanged data** (repeated scan hash or unchanged IPS/encoders while commanded to move). | The 500 ms observation-age limit becomes a receipt-age limit. Frozen-source detection becomes heuristic. Old-episode samples can't be told apart by identity, so reset relies on the reconnect boundary. |
| Front-motor torque cleared at zero throttle (D1) | On zero throttle the rear torque is cleared; the **front keeps its last torque** against the 85.6 N·m brake | **Re-measure the stop** (M2-type stops at the M6 speed) before any lap. At our throttle (≤ 0.07 × 21.4 N·m ≈ 1.5 N·m per wheel) the brake should dominate, but that is to be verified. | The D1 deviation disappears; the stop response must be re-qualified. |
| Manual / GUI command bypass blocked by the guard | Keyboard or GUI input can drive the car | Operational rule: no keyboard or mouse input to the player while it is connected, except the scripted Connect click (as now). | Not enforced in software. |
| Reset with epoch/episode rejection (SIM1-03) | GUI Reset reloads the scene; no episode identity | Each episode uses a **fresh simulator process** (already the practice). Reset is out of scope for S1; S2 will decide on restart-based initialization. | SIM1-03 as written is dropped. |

## 3. What happens to existing evidence

- **All M0–M6 and M1 results stay valid as patched-build evidence.** They are not transferred to the official build.
- **On the official build**, before any lap, these must be re-qualified, each under your approval:
  1. disarmed and stationary checks with the bridge-side lease (no motion);
  2. stop qualification (M2-type) at the M6 speed;
  3. speed-loop identification (M3-type), in case the plant differs;
  4. one M6 lap;
  5. an adapted F1 matrix (§4).
- **Reused unchanged:** the plugin, the supervisor, the stack, the scorer, the measurement tools and the C0 geometry (if the official scene's collider export matches; to be checked).

## 4. Decisions needed

- **D19 — bridge-side lease replaces the in-simulator guard.** Stops on stack, supervisor or runner failure become stops commanded by the bridge. Bridge loss becomes **containment by simulator kill**, recorded as containment and not counted as a stop. *Recommended, if you keep the official build.*
- **D20 — revised S1 acceptance.** Concretely:
  - "downstream receiver expiry" is met by the bridge-side lease;
  - the bridge-loss F1 case is containment-only;
  - freshness checks use receipt age;
  - SIM1-03 to SIM1-06 are withdrawn, and with them the patched-build PRE-03/04 evidence requirement.

  This **lowers** the agreed acceptance; it does not just change the method.
- **D21 — order of work on the official build.** Bridge-side lease and watchdog (offline tests), then a disarmed check, then stop qualification, identification, one lap, and the adapted F1 matrix, each needing your go-ahead for motion.

## 5. What confirming this does not do

- It doesn't authorize any motion on the official build. Every motion stage still needs its own go-ahead.
- It doesn't delete the patched builds or their evidence.
- It doesn't change AVLite, the plugin's command interface or the speed and steering limits.
