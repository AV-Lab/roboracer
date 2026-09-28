# Optional minimal AVLite validation

Date: 2026-09-28. Stage: research. Status: **prepared; awaiting explicit authorization**.

The plugin guide and checked-out source disagree about settings persistence, available bridge methods, sensor fields, and localization requirements. The following bounded probe will resolve these questions without implementing a RoboRacer feature.

Command (not yet executed):

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

Disposition: retain the script as reproducible research evidence through planning. After approved implementation provides equivalent contract coverage, migrate useful checks into the project's tests or remove the probe explicitly. It is not a runtime or experiment-runner dependency. Its syntax was parsed successfully; none of its checks has been executed.
