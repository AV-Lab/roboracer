# Research Decision Follow-up

Date: **2026-09-28**. Status: **v1.0 approved; PRE + S1 authorized; preflight blocked**. This addendum supersedes the pending-decision status of the original [English report](report.md) and [Chinese translation](report.zh-CN.md). The user's subsequent explicit v1.0 approval authorizes PRE + S1. Motion and later stages retain their stated gates; see the [PRE report](../stages/PRE.md).

## 1. User decisions and their boundaries

| Decision | Confirmed instruction | Consequence |
| --- | --- | --- |
| Q01 | Physical racing is the design goal; event, year and category are undecided. | Build a physical-car-oriented stack. IROS 2026 remains a reference, not an applicable future rulebook. AutoDRIVE virtual-league delivery is outside the current proposal. |
| Q02 | Derive the hardware reference from official Build documentation. | Use the current linked Master BOM and driver interfaces as documentary inputs; distinguish them from an inspected or calibrated car. No additional hardware questionnaire is needed to draft the software plan. |
| Q03 | Prefer option B. | Plan modular map-based racing. Keep A as the proposed small integration baseline and explicit comparator. The later Q10 decision removes mandatory first-release dynamic/multi-car acceptance. |
| Q04 | Retain current Humble. | Target Ubuntu 22.04 / Python 3.10 / ROS 2 Humble. No Jazzy migration. The earlier Gym branch-pair recommendation was a proposal, not part of this user decision; the later AutoDRIVE-first instruction supersedes it. Pin and qualify actual source/dependencies before accepting compatibility. |
| Q05 | Labelled early ground-truth use is allowed. | Permit explicit GT interface profiles; keep evaluation truth separate and require later estimated-pose validation. |
| Q06 | Approve the prepared isolated AVLite contract probe. | Executed once, unchanged, within its recorded scope. Results are below. This does not authorize simulator installation or functional implementation. |
| Q07 | Eventually push to a private GitHub repository. | Develop a standalone plugin following the community extension guide; use local-path registration. A private GitHub repository does not automatically imply the AV-Lab member registry. Remote creation, publication and pushing remain later actions. |
| Q08 | Hardware stop remains independent. | Keep software command ownership and stop/rearm explicit. A joystick/ROS deadman is not, by itself, proof of an independent hardware stop. Physical wiring, timeout and stopping performance remain hardware-validation obligations. |
| Q09 | Revise the plan to prioritize the existing AutoDRIVE installation for the first closed loop; Gym is not mandatory for release 1. | Bring simulator/API and Humble transport qualification into S1. Keep Gym as a later candidate. This authorizes planning changes, not simulator execution or final-plan implementation. |
| Q10 | Dynamic obstacles and multi-car interaction are not mandatory first-release acceptance. | Replace the required traffic stage/matrix with static-obstacle behavior. Keep moving opponents/multi-car as later candidates; their unavailable simulator APIs do not block release 1. Q14 settles the static-obstacle behavior. |
| Q11 | Reuse/extend AVLite's built-in ICP localization. | Retain `LocalizationStrategy` and reuse suitable matching routines/tests; add validated map-target and loss-handling behavior in the plugin. Native PF and AMCL are no longer planned first-release implementations. No core-interface change is authorized. |
| Q12 | Approve imported maps/reference paths, initial Pure Pursuit tracking, target-speed/steering interface and an independent command-supervision process. | Treat these as fixed design inputs. Backend mapping, process-failure behavior and performance still require qualification; selecting a design is not a successful runtime test or final-plan approval. |
| Q13 / R2-01 | Adopt simulation acceptance as the first-release delivery boundary. | Physical-car integration, calibration and testing follow in a separate approved stage. The physical-racing design goal remains unchanged. |
| Q14 / R2-02 | Avoid static obstacles when a traversable corridor exists; stop when fully blocked. | Require both passing and blocked-track stopping cases. An always-stop policy does not satisfy the passable-obstacle cases. |
| Q15 / R2-03 | Accept operator-supplied initial pose and stop/manual reinitialization after localization loss. | No mandatory automatic global localization/recovery in release 1. Predefined initial-pose configurations can support healthy batches; detected loss is a failed episode and pauses driving until operator recovery/rearm. |
| Q16 / R2-04 | Accept one qualified track, five reproducible initial conditions, and left-pass/right-pass/fully-blocked static cases as minimum release-1 coverage. | Fix the matrix to C0: 100 M3 A/B episodes, 30 M4 static episodes and 10 additional M5 held-out episodes, plus the defined fault/regression/measurement runs. Multi-track generalization is later scope; the actual local initialization and scene capabilities remain unverified. |
| Q17 / R2-05 | Allow a graphical session or virtual display for unattended experiments. | Require qualified unattended sensor output; display-free operation is not mandatory. This is acceptance of a runtime mode, not evidence that the local build supports it or blanket execution authorization. |

The current baseline is the [approved development plan v1.0](../planning/development-plan.md), with a concise [approval summary](../planning/approval-summary.md). Q13–Q17 close all five R2 preference questions. The user then explicitly approved v1.0 and PRE + S1. The [PRE report](../stages/PRE.md) records current qualification results and capability blockers; PRE-01/02 are accepted and 32 todos remain unchecked.

## 2. Official Build hardware follow-up

All sources below were accessed on **2026-09-28**. The linked Master BOM labels itself **updated 2026-05-15**. Its reference differs from the older static Build introduction; that difference is now recorded explicitly rather than choosing the static page silently.

| Area | Documentary reference | Planning use |
| --- | --- | --- |
| Chassis | The Master BOM lists Traxxas Fiesta ST Rally VXL, 1:10, with Slash 4x4 Ultimate as an alternative. | Ackermann vehicle with configurable footprint, wheelbase, reference-point offsets and steering limits. No geometry is inferred from the product name. |
| Compute | Jetson Orin Nano Super and 500 GB NVMe are listed. | Onboard execution target; host benchmarks remain host benchmarks. RAM, power mode, thermal state and actual OS image are not established by the BOM. |
| Primary sensing | Hokuyo 10LX at 40 Hz; SICK TiM 571 at 15 Hz is an alternative. D435i is optional. | Start with configurable planar LaserScan and odometry. Neither camera fusion nor a GPU algorithm is required by this design. Simulator scan defaults are not copied into a hardware specification. |
| Actuation and power | VESC 6 MkVI, powerboard and 3S 6000 mAh battery reference. | Keep VESC/servo calibration below the plugin's target-speed/steering interface; do not select firmware or electrical limits here. |
| Operator input | 8BitDo Ultimate 2C Wireless, with DualShock 4 as an alternative. | Button mappings must be supplied by the actual driver configuration. |

Source: [officially linked Master BOM](https://docs.google.com/spreadsheets/d/1WT-UdjLTnyrb7CvHcuCxKLnRIN8DWroQ/edit?ouid=109361333655731858904&rtpof=true&sd=true&usp=sharing). This is a reference description, not a purchasing recommendation, installed inventory or competition eligibility determination.

The [static BOM introduction](https://f1tenth.readthedocs.io/en/main/getting_started/build_car/bom.html) and [Build overview](https://f1tenth.readthedocs.io/en/main/getting_started/build_car/index.html) still name Slash 4x4 / Xavier NX. The [FAQ](https://f1tenth.readthedocs.io/en/main/getting_started/faq.html) names an Orin Nano reference and explicitly permits other supported computers and LiDARs. The planning reference follows the linked, dated Master BOM while preserving configurable vehicle and sensor contracts. No single universal mandatory hardware configuration is inferred.

The [system connection guide](https://f1tenth.readthedocs.io/en/main/getting_started/software_setup/index.html) describes onboard compute commanding the VESC, which controls the brushless motor and steering servo. LiDAR connects through its appropriate transport. This supports the software boundary; it does not provide the actual vehicle's actuator delay, mass, friction, wheelbase or sensor mount.

The [native driver guide](https://f1tenth.readthedocs.io/en/main/getting_started/firmware/drive_workspace.html) specifies Humble and `humble-devel`. Its broad JetPack/Ubuntu wording is insufficient to qualify every board image. The [autonomous-control page](https://f1tenth.readthedocs.io/en/main/getting_started/driving/drive_autonomous.html) documents `/scan`, `/odom`, `/sensors/imu/raw`, `/sensors/core` and `/drive`, with speed/steering commands and an RB-button deadman example; it still contains Foxy/container instructions. Adopt the current Humble driver route and validate its pinned configuration instead of merging those examples.

Two primary-source checks sharpen that boundary. [Humble's official installation source](https://raw.githubusercontent.com/ros2/ros2_documentation/humble/source/Installation/Ubuntu-Install-Debs.rst) specifies Ubuntu Jammy 22.04 packages; [NVIDIA's JetPack 6.2.1 page](https://developer.nvidia.com/embedded/jetpack-sdk-621) documents an Ubuntu 22.04 root filesystem and Orin Nano installation. This is a compatible documentary direction, not a selected or validated vehicle image. For UST-10LX, the [manufacturer specification](https://www.hokuyo-aut.jp/dl/UST-10LX_Specification.pdf) identifies Ethernet 100BASE-TX; the FAQ's conflicting USB example must not determine a device connection.

The [VESC configuration guide](https://f1tenth.readthedocs.io/en/main/getting_started/firmware/firmware_vesc.html) states that VESC configuration can be powered with the powerboard off. **Engineering inference:** the powerboard switch cannot be presumed to implement the user's independent traction stop. Physical stop design and testing remain a separate gate; this follow-up prescribes no wiring or firmware changes.

**Remaining hardware boundary:** actual board image and driver revisions, geometry/mounts, steering/speed calibration, odometry error, actuator delay, sustained compute capacity and the independent stop circuit require measurements before physical qualification. They do not block a simulation-first plan. No Build example supplies a justified real-car performance threshold.

## 3. Authorized contract-probe results

The exact [prepared script](evidence/avlite_contract_probe.py) ran once at **2026-09-28T09:52:28Z**, using the existing reference interpreter with target AVLite source explicitly prepended. It exited with code 0. Each result was inspected independently; successful process exit is not treated as a general compatibility result.

| Check | Observed result | Implication and remaining limit |
| --- | --- | --- |
| Source identity | Imported `/home/a2rl/Workspace/avlite/avlite/__init__.py`; target commit remains `50dcd0043db0cc17efbe82bda81cd0e8875810a0`. Runtime and installed-metadata version both report `0.6.1`. | Confirms the version helper prefers installed metadata. Use source path and commit independently. The borrowed venv is not the planned project environment. |
| Sensor/command fields | Named `cameras`/`lidars` and primary names are present. Lidar has mount, stamp and points. Ackermann has `steer` and `acceleration`, without target speed. | Confirms inspected datatype shapes, not coordinate transforms, timestamps in operation or GUI handling. |
| D01: settings | Saved `plugins.roboracer_research_probe.probe_value: 7` inside temporary `research_probe.yaml`; reload restored 7; no separate plugin file. | Confirms the tested current save/load API. Actual plugin discovery, automatic settings patching and GUI round trip still need integration tests. |
| D03: bridge method | `hasattr(WorldBridge, "control_type")` is false. | Do not implement against the documented nonexistent method. |
| D04: actuation gate | False without `LOCALIZATION`; true with that capability in the in-memory stub. | Reproduces the gate. It does not establish estimator quality or actual vehicle actuation. |
| D06: unregister | Dummy control registration removed; dummy localization registration remained. Both were explicitly cleaned up before process exit. | Reproduces this partial cleanup. Use fresh evaluation processes; full reload is unverified. |
| Isolation | Temporary probe directory removed; target AVLite remains clean. Reference repositories retain their recorded changes. | No dependencies installed, simulator/ROS/GUI launched or vehicle command sent. |

Evidence: [run metadata and script hash](evidence/avlite-contract-probe.run.json), [raw observations](evidence/avlite-contract-probe.stdout.json), [stderr](evidence/avlite-contract-probe.stderr.txt), [post-probe repository baseline](evidence/planning-baseline.json). The localization warning in stderr is expected from the negative gate check. The elapsed duration in run metadata is invocation bookkeeping, not a control-loop or simulator benchmark.

D02's named-field discrepancy is confirmed at datatype-introspection level. D05 launch behavior and D07 CLI discovery remain source-only; no implicit launch or CLI experiment was added to the authorization. Simulator installation, real plugin loading, reset/stop integration, closed-loop operation and race performance remain unverified.

## 4. Repository state update

The workspace is now a valid Git repository: `main`, HEAD `0bf647f8be823c9d6cfa00954297c7a8202f0e26` (`initial commit`), with no remote configured at inspection. It was clean before this follow-up's evidence/documents were added. This is an observed change since the original inventory; the agent did not initialize the repository or create that commit. The earlier invalid-`.git` blocker no longer applies. No commit, remote update or push was performed in this follow-up.

## 5. Planning implications

Proceed with B, Humble, official Build reference hardware, explicit early GT, independent hardware stop and AutoDRIVE first. Apply Q10–Q12: built-in ICP reuse/extension, imported maps/reference paths, Pure Pursuit, target speed/steering and separate command supervision. The revised stages are: AVLite–plugin–AutoDRIVE closed loop; unattended episodes/recording/fault recovery; known-map driving with extended ICP; agreed static-obstacle response; reproducible release qualification. Each implementation stage ends at a user confirmation gate. Gym and dynamic/multi-car acceptance are not mandatory in release 1.

Delivery boundary, static-obstacle behavior, ICP initialization/recovery, minimum track/start/obstacle coverage and unattended rendering are settled by Q13–Q17. The user's original instructions already require measured baselines followed by proposed numerical thresholds and explicit confirmation; do not ask the user to approve that principle again. The [v1.0 plan](../planning/development-plan.md) is explicitly approved for PRE + S1; bounded motion waits for a concrete numerical protocol, and later stages wait for their entry confirmations.

## 6. User-supplied simulator installation

The user subsequently identified an existing AutoDRIVE installation at `/home/a2rl/Workspace/AutoDRIVE Simulator [Linux]`. A [read-only follow-up](autodrive-local-installation.md) confirms application files and F1TENTH scene markers, with release/API/runtime qualification still outstanding. Plan v0.1.1 initially recorded it as a complementary candidate. The user's later instruction to revise the direction supersedes that recommendation; v0.2 makes it the first backend.

This route uses AutoDRIVE for physical-race development; it does not adopt a virtual-league target or assume this binary matches the 2026 competition release. Qualification must establish the matching API, actual actuator semantics, timing, selected display/sensor behavior, reset and scene/scoring capabilities. No live API, closed loop or performance result has been added by this documentation revision. The earlier Q06 approval remains limited to the already executed AVLite contract probe.

## 7. Confirmed ICP reuse and final-review boundaries

Read-only inspection confirms that the current built-in `LidarLocalization` stores a fixed first-scan reference, seeds from the current ego pose and updates planar pose. It declares `MAP_OCCUPANCY` but does not read a loaded occupancy grid in its matching implementation. Existing synthetic-scan tests establish intended cases in source; they were not run for this clarification. Whole-track AutoDRIVE behavior is unverified.

The approved direction is to reuse/extend that implementation through the plugin, with a validated known-map target and explicit match-validity/loss handling. Operator/configuration initial pose and stop/manual recovery are now accepted; automatic global initialization/recovery is outside required release-1 scope. Private-map injection is not assumed to be a supported integration API. Record any inherited internal-helper dependency and qualify it against the pinned source. Core changes require a separate reasoned proposal.

Questions R2-01–05 are resolved. The v1.0 candidate applies the confirmed one-track/five-start/static-case coverage and permits graphical/virtual-display unattended operation. Source/API compatibility is for engineering verification, not a decision for the user to guess. Final source review also fixes M3 A/B localization parity, preserves the independent supervisor alongside downstream expiry, and specifies behavioral episode termination/horizons and standard GUI registration/profile checks.

The v1.0 measurement protocol retains explicit run counts and five 120-second measurement windows after separate 10-second warm-up periods for M1/M2. These define a reviewable experiment, not measured performance or accepted numerical performance thresholds. Motion limits and compatible API semantics remain prerequisites to motion validation. All implementation items remain unchecked; no simulator execution or implementation approval is inferred from Q13–Q17.

## 8. Explicit plan approval and preflight execution

The user subsequently responded with explicit approval of v1.0 and PRE + S1. That approval remains valid. The first preflight run pinned official historical sources, verified writable paths and selected file integrity, created an isolated venv/source snapshot, performed a bounded no-control Unity startup, and checked system Humble imports/message serialization. DDS delivery and display access failed; the execution environment rejected the PyPI dependency download. See the [blocker report and evidence](../stages/PRE.md).

This advances evidence from static files to an observed startup with errors; it does not establish a working simulator API, sensor-producing headless mode, stopping behavior or closed-loop performance. No simulated motion command was sent. S1 feature work remains behind the incomplete PRE dependencies; no ordinary plan approval is being requested again.

## 9. Resumed PRE after CLI permission changes

The user resumed permission preflight. Specific approved host commands overcame dependency-download, display/GPU and basic DDS access restrictions; the sandbox still denied PyPI. The [resumed evidence](../stages/PRE-permission-recheck.md) establishes an isolated AVLite 0.6.3 installation, graphical Vulkan startup, one passive live telemetry frame and recorded scan/image transport between NumPy 1 and NumPy 2 environments. PRE-01 passed; 33 todos remain unchecked.

The historical Devkit's attrdict/Python 3.10 import failure is now reproduced. Native cv_bridge conversion works in the separate NumPy 1 environment; the combined AVLite NumPy 2 attempt failed. These are bounded compatibility findings, not an adopted new transport architecture or complete Devkit qualification. No motion command, stock control-node launch, plugin feature implementation or core change occurred. Continuous observations, timing/geometry, stop/reset/scoring and the concrete pre-motion protocol remain unresolved.

## 10. Continuous PRE qualification and pending capability decision

The user requested continued PRE completion. The [new English report](../stages/PRE-interface-qualification.md) and [Chinese report](../stages/PRE-interface-qualification.zh-CN.md) record a passing narrow Devkit overlay, continuous live Humble sensor delivery, two static Reset/reconnect trials, corrected normal shutdown and installed geometry extraction. Initial publisher-growth and shutdown failures remain retained. PRE-02 is now accepted alongside PRE-01; motion and S1 feature work remain held.

Actual payloads have no acquisition timestamps/sequences or simulation clock. The inspected historical receiver has no command lease; installed moving-stop behavior is unverified. Required start/static-scene control and scorer events remain unresolved. These affect explicit v1.0 acceptance rather than ordinary implementation preferences. A concrete options table recommends preparing a separate instrumented AutoDRIVE build, preserving the existing installation and acceptance goals. The user has been asked to choose that preparation route, explicit acceptance revision, or waiting for an upstream distribution. No answer, simulator-build change or acceptance amendment is inferred yet.

## 11. Option A confirmed; preparation delivered on 2026-09-29

The user explicitly confirmed the recommended option A from section 10. Its offered scope was source/toolchain feasibility and a reviewable amendment, not immediate instrumentation or reduced acceptance. This settles the preparation route; it does not select reactive driving A over the already confirmed map-based strategy B.

The [English feasibility report](../stages/PRE-option-A-feasibility.md), [Chinese report](../stages/PRE-option-A-feasibility.zh-CN.md) and [draft amendment 1.1-A](../planning/simulator-build-amendment.md) now provide that concrete result. All 223 tracked C# files, scene/project/package settings and asset identity metadata were retrieved from the pinned historical source. Official editor/module HEAD checks and four package metadata queries passed through approved host access. No editor was found in the inspected locations, Ubuntu 22.04 is outside its versioned documented Linux host list, and full asset import/build remains unverified. The project also needs a qualified Linux-host toolchain selection rather than assuming its Windows-host cross-toolchain is appropriate.

The amendment proposes SIM0 baseline build qualification, then SIM1 instrumented backend qualification, preserving v1.0 acceptance and later-stage scope. Ten proposed todos remain unchecked; the original 34 retain only PRE-01/02 accepted. No editor installation/activation, simulator instrumentation, simulator launch, motion, core change or S1 implementation occurred in this preparation. Original source repository states and nine selected installed-player fingerprints are unchanged.

Next review concerns the concrete amendment and SIM0 entry, not a repeated choice of the racing route. The remaining environment question asks whether Unity activation will use local user-managed Hub, an existing authorized build environment, or an undecided route. No credentials are requested. The numerical motion protocol and stage-entry gates remain in force.

## 12. SIM1 deferral question and installed-player-first proposal

On 2026-09-29 the user asked why SIM1 was needed and whether it could be completed later. Rechecked live measurements and historical receiver/actuator/reset source: the player runs and supplies observations; missing source acquisition identity, unqualified downstream expiry and incomplete scoring/scene control affect the approved acceptance. No installed-binary moving-stop failure or exact source equivalence was claimed.

Prepared [draft 1.1-B](../planning/installed-binary-first-amendment.md) and [Chinese explanation](../stages/SIM1-deferral.zh-CN.md). Recommendation: introduce S1a as a bounded installed-player AVLite closed-loop/normal-stop demonstration; defer SIM0 as well as SIM1; retain original source-freshness, downstream fault-stop and scoring requirements for subsequent acceptance. Unity activation becomes relevant only if the source-build route is resumed. Verified external tooling or demonstrated existing capabilities may satisfy some gaps without source changes.

The draft retains independent command supervision and numerical motion approval. Final-path loss without qualified receiver expiry permits only a failed/contained simulation outcome, not a braking pass. Manual fixed-start setup and explicitly unverified scoring are limited to S1a. The proposal has four new unchecked todos; original 34 todos retain two accepted, and the ten source-build draft todos remain unchecked. No new runtime evidence or implementation was added.

The user has asked about feasibility, not explicitly approved this new dependency exception. Confirmation must cover entering the bounded S1a before full PRE-03/04, preserving original release obligations and the stage/motion gates. Do not record the question itself as acceptance reduction or implementation authorization.

## 13. Full PRE-first continuation confirmed; Unity environment undecided

The user instructed: continue the original plan and enter S1 only after complete PRE. The S1a/deferral exception is not adopted. Retain its draft as inactive decision history, with all four proposed items unchecked. In the context of the reviewed source-build route, continue scoped SIM0 preparation/qualification; do not ask for the same sequence choice again. SIM1 still follows the SIM0 report and its explicit entry gate, and the numerical motion protocol remains required.

When asked which activation/build environment to use, the user answered **not yet determined**. No local entitlement or remote build host is assumed. Prepared the [English setup handoff](../stages/SIM0-activation-guide.md) and [Chinese steps](../stages/SIM0-activation-guide.zh-CN.md) from current official Hub/license/editor documentation. Recommend user-managed Hub login and applicable-license verification, followed by the pinned Unity 2021.3.9f1/IL2CPP environment. Do not infer license eligibility or purchase authorization.

Only documents and the decision state changed. Source-build/activation tests remain unperformed; original PRE-01/02 remain the only accepted original todos. No installation, GUI launch, instrumentation, motion or S1 code was added. Next prerequisite is a selected, activated build environment; the user's original sequencing instruction is settled.

## 14. Local Hub installed; user confirms login and license

The user subsequently requested Linux Unity Hub installation. Installed the official Hub 3.21.3 AppImage in the user's application directory, with the `unityhub` command, desktop entry and login callback association. File hashes, desktop validation and an owned visible window are recorded in `artifacts/preflight/20260929T062054Z/`. Installation did not include an Editor, license selection or account login by the agent.

The user then reported successful login and license confirmation. This selects the local build route and resolves the user-managed readiness question; actual pinned-Editor entitlement access is still a runtime check. Continue authorized SIM0 acquisition/import/build and neutral qualification without another sequence approval. The first Hub CLI inventory produced GUI-profile database-lock diagnostics and no Editor list; use the official pinned Editor/module archives in the already approved isolated toolchain path. Do not stop or alter the user's Hub/account state to force that query.

The [English setup record](../stages/SIM0-activation-guide.md) and [Chinese version](../stages/SIM0-activation-guide.zh-CN.md) reflect this progression. SIM0 evidence is under `artifacts/simulator-build/20260929T063510Z/`. All acceptance marks stay unchanged until their tests pass; SIM1 and numerical motion retain their explicit gates.

The continuation acquired the complete tracked source and exact Editor/module. Actual empty-project startup then exited 1 after 46.70 seconds at the entitlement handoff; an unavailable-access-token error followed a successful licensing-service connection. Hub CLI association exited 0 but later returned an empty installed-editor list. These are runtime findings, not evidence that the user failed to log in. The [English attempt report](../stages/SIM0-toolchain-attempt.md) / [Chinese report](../stages/SIM0-toolchain-attempt.zh-CN.md) preserves the source/toolchain, scoped build helper and unperformed acceptance. The user has been asked to associate/first-open this Editor through Hub and handle any account prompts; no credentials are requested. SIM0-B01 blocks dependent import/build work, and no stage-entry decision is reopened.
