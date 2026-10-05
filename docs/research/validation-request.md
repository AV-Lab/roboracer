# Authorized minimal AVLite validation

Date: 2026-09-28. Stage: research follow-up. Status: **authorized by user decision Q06; executed once; results reviewed**.

The plugin guide and checked-out source disagree about settings persistence, available bridge methods, sensor fields, and localization requirements. The following bounded probe inspected these specific contracts without implementing a RoboRacer feature. See the [results and limitations](decision-follow-up.md).

Executed command (retained for reproduction; not rerun for documentation checks):

```sh
/home/a2rl/avlite/.venv/bin/python -B /home/a2rl/Workspace/roboracer/docs/research/evidence/avlite_contract_probe.py
```

The probe uses the existing interpreter and dependencies, explicitly imports `/home/a2rl/Workspace/avlite`, and reports the actual source location and installed metadata separately. It writes a disposable profile only inside a temporary directory under `/tmp`, isolates AVLite/XDG/Matplotlib configuration paths, and removes that temporary directory on exit. Registry changes exist only in the short-lived Python process.

Checks:

1. Actual imported code path, metadata version, and sensor/command dataclass fields.
2. Presence of the documented `WorldBridge.control_type` method.
3. Plugin settings save/load location and round trip using the current core APIs.
4. The localization capability gate using an in-memory stub; no vehicle or executer is started.
5. Registry cleanup for dummy control and localization entries; no plugin package is loaded.

No dependency installation, simulator launch, ROS node, port listener, device access, GUI, source modification, or change to existing user profiles is involved. This verifies only the listed API behavior; it cannot establish plugin loading, simulator connectivity, closed-loop operation, or race performance.

Disposition: retain the script as reproducible research evidence through planning. After approved implementation provides equivalent contract coverage, migrate useful checks into the project's tests or remove the probe explicitly. It is not a runtime or experiment-runner dependency. The unchanged script executed at 2026-09-28T09:52:28Z and exited 0. Each observation was reviewed; this is not a general compatibility pass. Evidence: [run metadata](evidence/avlite-contract-probe.run.json), [observations](evidence/avlite-contract-probe.stdout.json), [stderr](evidence/avlite-contract-probe.stderr.txt).
