"""Disposable research probe; not a RoboRacer plugin or acceptance test suite."""

import dataclasses
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace


def main():
    source_root = Path("/home/a2rl/Workspace/avlite")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(source_root))
    with tempfile.TemporaryDirectory(prefix="roboracer-contract-", dir="/tmp") as scratch:
        for name, directory in {
            "XDG_CONFIG_HOME": "xdg-config",
            "XDG_CACHE_HOME": "xdg-cache",
            "XDG_DATA_HOME": "xdg-data",
            "AVLITE_CONFIG_DIR": "profiles",
            "AVLITE_PLUGINS_DIR": "plugins",
            "MPLCONFIGDIR": "matplotlib",
        }.items():
            os.environ[name] = str(Path(scratch) / directory)

        import avlite
        import yaml
        from avlite.c10_perception.c13_localization_strategy import LocalizationStrategy
        from avlite.c30_control.c31_control_model import AckermannControlCommand
        from avlite.c30_control.c32_control_strategy import ControlStrategy
        from avlite.c40_execution.c41_world_bridge import WorldBridge
        from avlite.c40_execution.c42_execution_strategy import ExecutionStrategy
        from avlite.c50_common.c51_capabilities import StackCapability
        from avlite.c50_common.c52_world_sensor_datatypes import SensorFrame, Lidar
        from avlite.c60_apps.c63_plugins import unregister_plugin_package
        from avlite.c60_apps.c65_setting_utils import load_setting, save_setting, setting_section

        assert Path(avlite.__file__).resolve() == source_root / "avlite/__init__.py"
        results = {
            "source": avlite.__file__,
            "python": sys.executable,
            "runtime_version": avlite.__version__,
            "installed_metadata_version": importlib.metadata.version("avlite"),
            "sensor_frame_fields": [field.name for field in dataclasses.fields(SensorFrame)],
            "lidar_fields": [field.name for field in dataclasses.fields(Lidar)],
            "ackermann_fields": [field.name for field in dataclasses.fields(AckermannControlCommand)],
            "world_bridge_has_control_type": hasattr(WorldBridge, "control_type"),
        }

        probe_settings = type("ResearchSettings", (), {
            "filepath": "plugin_roboracer_research_probe.yaml",
            "probe_value": 7,
        })
        results["settings_section"] = setting_section(probe_settings)
        save_setting(probe_settings, profile="research_probe")
        profile_path = Path(os.environ["AVLITE_CONFIG_DIR"]) / "research_probe.yaml"
        results["profile_document"] = yaml.safe_load(profile_path.read_text())
        results["separate_plugin_file_exists"] = (
            profile_path.parent / "plugin_roboracer_research_probe.yaml"
        ).exists()
        probe_settings.probe_value = -1
        results["settings_loaded"] = load_setting(probe_settings, profile="research_probe")
        results["round_trip_value"] = probe_settings.probe_value

        capabilities = set()
        stub = SimpleNamespace(
            available_stack_capabilities=lambda: capabilities,
            _localization_missing_warned=False,
        )
        results["actuation_without_localization"] = ExecutionStrategy._can_actuate(stub)
        capabilities.add(StackCapability.LOCALIZATION)
        results["actuation_with_localization"] = ExecutionStrategy._can_actuate(stub)

        dummy = type("ResearchDummy", (), {
            "__module__": "avlite.plugins.roboracer_research_probe.dummy",
        })
        key = "RoboRacerResearchDummy"
        assert key not in ControlStrategy.registry and key not in LocalizationStrategy.registry
        ControlStrategy.registry[key] = dummy
        LocalizationStrategy.registry[key] = dummy
        unregister_plugin_package("roboracer_research_probe")
        results["control_entry_after_unregister"] = key in ControlStrategy.registry
        results["localization_entry_after_unregister"] = key in LocalizationStrategy.registry
        ControlStrategy.registry.pop(key, None)
        LocalizationStrategy.registry.pop(key, None)
        print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
