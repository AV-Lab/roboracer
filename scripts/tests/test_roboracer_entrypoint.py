"""S5-03 (D71): the single entrypoint maps to the qualified tools unchanged, and compare summarises exports."""

import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import roboracer  # noqa: E402


def write_export(directory: Path, laps, contact_free=True, obstacle=None, blocked=None):
    directory.mkdir(parents=True)
    score = {"laps": [{"lap_time_s": t} for t in laps], "min_clearance_m": 0.29, "min_obstacle_clearance_m": obstacle}
    (directory / "episode.json").write_text(json.dumps({
        "stage": "s4", "outcome": {"state": "finished", "reason": "distance" if laps else "blocked"}, "score": score,
        "completed_laps": len(laps), "contact_free_and_on_track": contact_free, "s4_blocked": blocked}))


class EntrypointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.context = self.dir / "run-context.json"
        self.context.write_text(json.dumps({"avlite_python": "/fresh/avlite-venv/bin/python"}))

    def tearDown(self):
        self.tmp.cleanup()

    def run_dry(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(0, roboracer.main(["--context", str(self.context), "--dry-run", *argv]))
        return [line[2:].split(" ") for line in out.getvalue().splitlines() if line.startswith("+ ")]

    def test_live_s4_with_fixture_and_judge_uses_the_context_python_and_qualified_defaults(self):
        cmds = self.run_dry("live", "--stage", "s4", "--fixture", "t2", "--judge", "t2",
                            "--results", str(self.dir / "r"), "--output", str(self.dir / "e"))
        episode, judge = cmds
        self.assertEqual("/fresh/avlite-venv/bin/python", episode[0])
        self.assertTrue(episode[2].endswith("scripts/roboracer_episode.py"))
        self.assertEqual("s4", episode[episode.index("--stage") + 1])
        self.assertTrue(episode[episode.index("--obstacle-fixture") + 1].endswith("s4-fixtures/t2-right-pass.json"))
        self.assertTrue(episode[episode.index("--player") + 1].endswith("20261007T-sim1-04/AutoDRIVE.x86_64/AutoDRIVE.x86_64"))
        self.assertTrue(judge[2].endswith("roboracer_s4_judge.py"))
        self.assertEqual("t2", judge[judge.index("--case") + 1])

    def test_live_passes_fault_and_rearm_options_through(self):
        episode = self.run_dry("live", "--stage", "s4", "--fixture", "t1", "--f4-case", "f4-2",
                               "--results", "r", "--output", "e")[0]
        self.assertEqual("f4-2", episode[episode.index("--f4-case") + 1])
        episode = self.run_dry("live", "--stage", "s3m3b", "--m3-ic", "2", "--results", "r", "--output", "e")[0]
        self.assertEqual("2", episode[episode.index("--m3-ic") + 1])
        self.assertNotIn("--obstacle-fixture", episode)

    def test_replay_and_export_map_to_the_qualified_tools(self):
        replay = self.run_dry("replay", "--run", "run-01", "--output", "o.json")[0]
        self.assertEqual(["replay", "--run", "run-01"], replay[3:6])
        fixtures = self.run_dry("replay", "--fixtures", "--output", "o.json")[0]
        self.assertEqual("fixtures", fixtures[3])
        export = self.run_dry("export", "--results", "res", "--output", "ep")[0]
        self.assertEqual("recorded", export[3])

    def test_compare_groups_episode_exports(self):
        write_export(self.dir / "a1", [68.3], obstacle=0.37)
        write_export(self.dir / "a2", [68.9], obstacle=0.35)
        write_export(self.dir / "b1", [], obstacle=1.45, blocked={"reason": "no collision-free in-bounds edge"})
        out = self.dir / "cmp.json"
        with contextlib.redirect_stdout(io.StringIO()):
            roboracer.main(["--context", str(self.context), "compare", "--group", f"T1={self.dir / 'a1'},{self.dir / 'a2'}",
                            "--group", f"T3={self.dir / 'b1'}", "--output", str(out)])
        result = json.loads(out.read_text())
        self.assertEqual({"episodes": 2, "laps": 2, "blocked": 0}, {k: result["groups"]["T1"][k] for k in ("episodes", "laps", "blocked")})
        self.assertEqual([68.3, 68.9], result["groups"]["T1"]["lap_s"])
        self.assertAlmostEqual(0.35, result["groups"]["T1"]["min_obstacle_clearance_m"])
        self.assertEqual(1, result["groups"]["T3"]["blocked"])
        self.assertIn("| T3 | 1 | 1 | 0 | 1 |", out.with_suffix(".md").read_text())


if __name__ == "__main__":
    unittest.main()
