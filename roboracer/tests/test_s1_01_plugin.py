"""S1-01: AVLite loads/registers the plugin, round-trips and rejects settings, and every
command consumer behaves as recorded. Run with the AVLite interpreter:
``<avlite python> -m unittest discover -s roboracer/tests -t .``
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PLUGIN = Path(__file__).resolve().parents[1]
PROBE = Path(__file__).with_name("s1_01_probe.py")


def probe(case):
    with tempfile.TemporaryDirectory() as scratch:
        env = {k: v for k, v in os.environ.items() if not k.startswith(("AVLITE_", "XDG_"))}
        env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", MPLCONFIGDIR=f"{scratch}/mpl",
                   **{name: f"{scratch}/{name.lower()}" for name in (
                       "AVLITE_CONFIG_DIR", "AVLITE_PLUGINS_DIR", "AVLITE_DATA_DIR",
                       "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME")})
        result = subprocess.run([sys.executable, "-B", str(PROBE), case, str(PLUGIN)], env=env, cwd=scratch,
                                capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise AssertionError(f"probe {case} failed:\n{result.stderr[-3000:]}")
        return json.loads(result.stdout.strip().splitlines()[-1])


class PluginLoadingTests(unittest.TestCase):
    def test_import_registers_exports_without_side_effects(self):
        r = probe("import")
        self.assertEqual(["AutoDriveBridge", "GapFollowController", "HoldController", "PluginSettings",
                          "RaceLineGlobalPlanner", "RacingLineController", "SpeedStepController",
                          "TargetSpeedSteeringCommand"], r["exports"])
        self.assertTrue(r["registered_bridge"] and r["registered_controller"])
        self.assertTrue(r["settings_filepath"].endswith("plugin_roboracer.yaml"), r["settings_filepath"])
        for key in ("threads", "sockets", "children", "watched_modules"):
            self.assertEqual(r["before"][key], r["after"][key], key)
        self.assertNotIn("avlite.plugins.roboracer.tests.s1_01_probe", r["loaded_modules"])

    def test_factory_loads_plugin_and_command_reaches_bridge(self):
        r = probe("factory")
        self.assertEqual(("AutoDriveBridge", "HoldController"), (r["bridge"], r["controller"]))
        # Ground-truth LOCALIZATION from the bridge (as BasicSim) enables AVLite's control path.
        self.assertEqual(["LOCALIZATION"], r["stack_capabilities"])
        self.assertTrue(r["can_actuate"])
        self.assertGreaterEqual(r["accepted"], 1)
        self.assertEqual({}, r["rejections"])
        self.assertEqual({"type": "TargetSpeedSteeringCommand", "target_speed": 0.0, "steer": 0.0}, r["last_request"])
        self.assertEqual({"acceleration": 0.0, "steer": 0.0}, r["gauge"])

    def test_avlite_gt_filter_removes_localization_and_actuation(self):
        r = probe("factory-gt-filtered")
        # AVLite's own Bridge Setting filter, not a plugin setting, switches the ground truth off.
        self.assertFalse(r["can_actuate"])
        self.assertEqual((0, {}, None), (r["accepted"], r["rejections"], r["last_request"]))


class SettingsTests(unittest.TestCase):
    def test_round_trip_and_invalid_values_rejected(self):
        r = probe("settings")
        self.assertTrue(r["round_trip_loaded"])
        self.assertEqual(r["expected"], r["round_trip"])
        self.assertTrue(r["profile_path"].startswith(r["config_dir"]), "profile written outside the isolated config dir")
        self.assertEqual(7, len(r["invalid"]))
        for name, outcome in r["invalid"].items():
            with self.subTest(case=name):
                self.assertEqual({"load_returned": False, "unchanged": True, "strict": "SettingsValidationError"}, outcome)


class CommandConsumerTests(unittest.TestCase):
    def test_bridge_controller_gui_and_basic_sim(self):
        r = probe("consumers")
        rejected = {k for k, v in r["bridge"].items() if v == "rejected"}
        self.assertEqual(set(r["bridge"]) - {"zero speed at steering limit"}, rejected)
        self.assertEqual("accepted", r["bridge"]["zero speed at steering limit"])
        self.assertIn("unsupported command type AckermannControlCommand", r["rejection_reasons"])
        # BasicSim integrates acceleration; the plugin command must fail loudly there, never drive it.
        self.assertTrue(r["basic_sim_with_plugin_command"].startswith("AttributeError"))
        self.assertEqual(("TargetSpeedSteeringCommand", [0.0, 0.0]), (r["hold_returns"], r["hold_values"]))
        self.assertTrue(r["gauge_numeric"])
        self.assertEqual(0.0, r["headless_acceleration_display"])


if __name__ == "__main__":
    unittest.main()
