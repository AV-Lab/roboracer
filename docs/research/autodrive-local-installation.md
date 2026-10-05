# Existing AutoDRIVE Simulator: Local Inspection

Date: **2026-09-28**. Scope: **historical read-only research follow-up**. The user supplied an existing installation at `/home/a2rl/Workspace/AutoDRIVE Simulator [Linux]`. During that initial inspection, no simulator was launched, no API connection was attempted, and no installation file or permission was changed.

**Current update:** [continuous PRE qualification](../stages/PRE-interface-qualification.md) now establishes disarmed live telemetry through a pinned Devkit overlay into Humble/AVLite, two static Reset/reconnect observations and read-only extraction of installed collider geometry. Zero-only replies were used in Manual mode; no motion command was sent. Exact release/source equivalence, acquisition identity/time, receiver expiry/braking and complete scoring/scenario support remain unqualified. Selected installation fingerprints are unchanged.

## Observations and limits

| Item | Observed evidence | What it establishes |
| --- | --- | --- |
| Directory | Supplied path exists and resolves to itself. | A local application distribution is available. |
| Executable | `AutoDRIVE Simulator.x86_64` is an x86-64 ELF executable with execute permission already present. | Binary identity and permission, not successful startup. The README's permission workaround was not needed or executed. |
| Application | `Data/app.info` identifies AutoDRIVE Ecosystem / AutoDRIVE Simulator; Unity player and IL2CPP application libraries are present. | Application branding and packaging. |
| Vehicle scene | `Data/globalgamemanagers` contains `Assets/Scenes/F1TENTH.unity`; `Data/level0` also contains F1TENTH labels. | An F1TENTH scene is packaged. This does not enumerate every supported vehicle or prove active scene behavior. |
| Unity marker | `2021.3.9f1` appears in the serialized data. | Engine-version marker only; it is not an AutoDRIVE release or competition version. |
| Integration clues | Scene strings include `SocketIO` and `ToggleSocketConnection`. | A socket integration is suggested; exact payload, port, command semantics and matching Devkit remain unidentified. |
| Native plugin | `libRobotecGPULidar.so` is present. | Packaged library only; active sensor selection, GPU requirements and headless behavior remain unverified. |
| Provenance | SHA256 fingerprints recorded for the executable, application/player libraries and selected metadata. | A reproducible local identity for subsequent comparison, not a match to an official release checksum. |

Evidence: [static inventory and fingerprints](evidence/autodrive-local-inventory.json), [local README](</home/a2rl/Workspace/AutoDRIVE Simulator [Linux]/README.md>), [application identity](</home/a2rl/Workspace/AutoDRIVE Simulator [Linux]/Data/app.info>). Inspection used filesystem metadata, text reads, `file`, selected binary strings and hashing; no application code was loaded.

**Verification level at initial inspection:** local files observed; AutoDRIVE release and matching API version unknown; startup, graphics/headless operation, ROS connectivity, reset, closed-loop behavior and performance unverified. The original research statement that this project had not installed or run a simulator remains true; it must not be interpreted as absence of an existing user installation.

## Relation to official interfaces

The [official AutoDRIVE site](https://autodrive-ecosystem.github.io/) describes a general simulator/devkit/testbed ecosystem, and its linked [Devkit repository](https://github.com/Tinker-Twins/AutoDRIVE/tree/AutoDRIVE-Devkit) provides multiple APIs including ROS 2. Therefore, AutoDRIVE should not be treated as exclusively a virtual-competition tool. These pages were accessed on 2026-09-28 and do not establish compatibility with this local binary.

The separate [2026 competition technical guide](https://autodrive-ecosystem.github.io/competitions/roboracer-sim-racing-guide-2026/) describes a particular competition integration. No evidence yet matches this installation to that release. Its launch flags, topic names, observations and actuator conventions must not be assigned to the local binary merely because the application name matches. Two initially attempted standalone repository URLs returned 404; the official site's linked repository is the reference used here.

## Planning effect

**User-confirmed revision, 2026-09-28:** prioritize this existing AutoDRIVE installation for the first AVLite closed loop. Gym is a later candidate and is no longer a required first-release backend. This supersedes the initial proposal to keep AutoDRIVE as complementary validation. The [current development plan](../planning/development-plan.md) applies that direction to integration, stages, measurements and risks.

The benefit is reuse of the available application and alignment of the first demonstration with the user's intended simulator. The cost is bringing Devkit/Humble transport and runtime qualification into S1. Existing binaries do not establish API compatibility, deterministic stepping, automatic reset, throughput or headless sensor operation.

Qualify the local release and matching Devkit; then, under an explicitly approved runtime scope or the final approved plan, test startup in the selected permitted display mode, observations, command semantics, stop/reset/time ownership and measurement export. Display-free operation is optional. If commands are normalized throttle/steering rather than target speed/radians, an explicit validated conversion/control layer is required. Zero throttle must not be assumed to brake. These are conditional design obligations, not claims about the unverified local API.

The revised plan treats AutoDRIVE as externally advancing unless a supported step API is demonstrated. It separates recorded-input regression from live closed-loop evidence and makes required map, automated reset and static-obstacle capabilities explicit qualification gates. The user has excluded dynamic obstacles and multi-car interaction from mandatory first-release acceptance; unavailable opponent control does not block that release. It promises neither identical seeded trajectories nor programmable multi-car scenes. If Gym is added later, model differences must not be presented as pure transport overhead.

The physical-racing goal, B, Humble and independent hardware-stop decisions remain in force. All R2 scope choices are now confirmed, including one track/five initial conditions/static cases and graphical/virtual-display unattended operation. The subsequent explicit v1.0 approval authorizes PRE + S1; API, operational limits and runtime capabilities remain engineering gates. The [PRE report](../stages/PRE.md) supersedes the original startup-not-performed status, while retaining the limits on sensor/API/closed-loop claims.
