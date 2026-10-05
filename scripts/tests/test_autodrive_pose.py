"""Diagnostic gate and causal-attribution tests, including actual C# serialization."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location("autodrive_pose", ROOT/"scripts/autodrive_pose.py")
pose=importlib.util.module_from_spec(spec);spec.loader.exec_module(pose)


class PoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import numpy as np
        cls.np=np
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        data=Path('/tmp/roboracer-work/toolchains/2021.3.9f1/Editor/Data')
        cls.mono=data/'MonoBleedingEdge/bin/mono';cls.exe=Path(cls.temp.name)/'pose.exe'
        if not cls.mono.is_file():raise unittest.SkipTest('Pinned compiler unavailable; not validated')
        sources=[ROOT/'integration/autodrive/diagnostics'/s for s in ['KinematicsProbe.cs','ContactProbe.cs','ContactRelay.cs','PoseTrace.cs']]
        sources += [ROOT/'scripts/tests/fixtures'/s for s in ['KinematicsProbeFixture.cs','PoseTraceFixture.cs']]
        r=subprocess.run([str(cls.mono),str(data/'MonoBleedingEdge/lib/mono/4.5/csc.exe'),'-nologo','-main:PoseFixture','-out:'+str(cls.exe),*[str(p) for p in sources]],capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)

    def fixture(self,case):
        dest=Path(self.temp.name)/case;dest.mkdir()
        r=subprocess.run([str(self.mono),str(self.exe),str(dest),case],capture_output=True,text=True)
        self.assertEqual(0,r.returncode,r.stderr)
        status=json.loads((dest/'pose-fixture.json').read_text())
        self.assertEqual(0,status['physics_setters'])
        return dest,status

    def test_binary_roundtrip_and_correct_statement_attribution(self):
        dest,status=self.fixture('valid');self.assertEqual('',status['error'])
        binding=json.loads((dest/'pose-binding.json').read_text())
        self.assertEqual(216,struct.calcsize(binding['layout']))
        data=self.np.fromfile(dest/'pose.bin',dtype=pose.record_dtype())
        result=pose.summarize_records(data)
        self.assertEqual(82,len(data));self.assertTrue(status['pose_window_complete'])
        self.assertEqual(8*2**-24,result['body_endpoint_delta_xyz_m'][2])
        self.assertEqual(0,result['checkpoint_read_effect']['nonzero_Z_count'])
        self.assertEqual(0,result['between_step_gaps']['nonzero_Z_count'])
        for wheel in range(4):
            self.assertEqual(2*2**-24,result['intervals'][f'13:{wheel} -> 14:{wheel}']['gap_excluding_prior_read_effect']['sum_xyz_m'][2])
        for corrupt in ['index','stage','wheel','monotonic_ns','fixed_time']:
            changed=data.copy();changed[corrupt][42]=changed[corrupt][41]
            if corrupt=='wheel':changed[corrupt][42]+=1
            if corrupt=='fixed_time':changed[corrupt][42]+=1
            with self.subTest(corrupt=corrupt),self.assertRaises(ValueError):pose.summarize_records(changed)
        with self.assertRaises(ValueError):pose.summarize_records(data[:-1])

    def test_fail_closed_faults(self):
        for case,fragment in [('reorder','reordered'),('nonfinite','Nonfinite'),('recorder','inactive recorder'),
                              ('nonzero','exact-zero'),('cap','1 GiB'),('binding','binding'),('duration','oversized'),('foreign','Foreign')]:
            with self.subTest(case=case):
                dest,status=self.fixture(case);self.assertIn(fragment,status['error'])
                if (dest/'pose.bin').exists():self.assertEqual(0,(dest/'pose.bin').stat().st_size%216)

    def test_no_statement_records_without_requested_window(self):
        dest,status=self.fixture('pending');self.assertEqual('',status['error'])
        self.assertEqual(0,(dest/'pose.bin').stat().st_size)
        self.assertFalse(status['pose_window_complete'])

    def test_exact_vendor_lines_remain_and_markers_bracket_the_setters(self):
        source=Path('/tmp/roboracer-work/autodrive-native-20260929T122535Z-authoring/Assets/Scripts/VehicleController.cs')
        if not source.exists():self.skipTest('Pinned source unavailable')
        original=source.read_bytes();patched=pose.patch_controller(original)
        stripped=b''.join(l for l in patched.splitlines(keepends=True) if not l.rstrip().endswith(pose.MARKER.encode()))
        self.assertEqual(original,stripped)
        lines=patched.decode().splitlines()
        for statement,before,after in [('_collider.GetWorldPose(out _pos, out _quat);',11,12),
                                      ('_transform.position = _pos;',13,14),('_transform.rotation = _quat;',15,16)]:
            i=next(i for i,l in enumerate(lines) if l.strip()==statement)
            self.assertIn(f'Mark(this, {before},',lines[i-1]);self.assertIn(f'Mark(this, {after},',lines[i+1])
        with self.assertRaises(ValueError):pose.patch_controller(original+b'\n')

    def test_cli_rejects_incompatible_mode_or_budget_before_launch(self):
        import sys
        for extra in [['--duration','11'],['--duration','10','--contact-mode','treatment'],['--duration','10','--startup-timeout','181']]:
            r=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/autodrive_neutral.py'),'run','--results','/tmp/pose-must-not-start',
                '--profile','drift-diagnostic','--kinematics-probe','--pose-trace','--contact-mode','control','--contact-target','floor',*extra],capture_output=True,text=True)
            self.assertEqual(2,r.returncode);self.assertIn('Pose tracing requires',r.stderr)


if __name__=='__main__':unittest.main()
