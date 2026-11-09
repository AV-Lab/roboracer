# RoboRacer

An AVLite community plugin and its qualification harness for the AutoDRIVE F1TENTH simulator. It was developed stage by stage (PRE, S1–S5) under a written plan, recorded decisions and per-run motion approvals.

**Status:** release 1 (S5): simulation only, C0 track, 0.5 m/s, map-ICP localization, static-obstacle avoidance. **Private; not published.**

## Start here

| If you want to | Read |
| --- | --- |
| install, launch, reset, and know the limits | [`release/README.md`](release/README.md), the operations guide |
| use the plugin in AVLite | [`roboracer/README.md`](roboracer/README.md) |
| see what was qualified and how | [`docs/stages/S5.md`](docs/stages/S5.md), [`docs/stages/S5-audit.md`](docs/stages/S5-audit.md), and the earlier stage reports in [`docs/stages/`](docs/stages/) |
| see the plan and every decision | [`docs/planning/development-plan.md`](docs/planning/development-plan.md), [`docs/planning/s1-motion-approval.json`](docs/planning/s1-motion-approval.json) (decisions D1–D81, approvals, corrections) |
| follow the history | [`docs/DEVELOPMENT_LOG.md`](docs/DEVELOPMENT_LOG.md) |

## Layout

| Path | Content |
| --- | --- |
| `roboracer/` | The AVLite plugin: bridge, localization, perception, planning, control, supervisor, data files, and tests |
| `scripts/` | The stage runner (`autodrive_neutral.py`), the entrypoint (`roboracer.py`), judges and scorers, fixture builders, environment and audit tools, and tests |
| `integration/autodrive/` | Guard and provenance sources added to the simulator, and vendor patches 01–04 |
| `release/` | Pins, locks and patches for the environment, plus the operations guide |
| `docs/` | Plan, proposals, stage reports, architecture notes, research |

**Evidence** (run outputs with sha256 manifests) lives outside the repository, in the workspace's `artifacts/` (ignored by git). The docs cite it by path; `scripts/roboracer_s5_audit.py` checks that every cited path exists and that every manifest verifies.

## Tests

```bash
<avlite-venv>/bin/python -B -m unittest discover -s roboracer/tests -t .
<avlite-venv>/bin/python -B -m unittest discover -s scripts/tests
```

Tests that need this host's evidence skip when it is absent.

Third-party code, patches and their licences: [`THIRD_PARTY.md`](THIRD_PARTY.md).
