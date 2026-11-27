"""Regression tests for candidate ranking, CLI compatibility and STL export."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import numpy as np
import trimesh

from orientation_optimizer import export_orientation, optimize_candidates


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.mesh = trimesh.creation.box(extents=(30, 20, 8))
        self.mesh.apply_transform(trimesh.transformations.rotation_matrix(
            np.deg2rad(10), [1, 0, 0]))

    def test_candidate_metrics_and_priorities(self):
        candidates = optimize_candidates(self.mesh, samples=128, custom_weights=(1, 0, 2))
        modes = {mode: report for _, report in candidates for mode in report['candidate_modes']}
        self.assertEqual(set(modes), {'Surface quality', 'Balanced', 'Minimum supports proxy',
                                      'Minimum height', 'Custom'})
        directions = {tuple(report['build_up_input']) for _, report in candidates}
        self.assertGreater(len(directions), 1)
        self.assertEqual(len(directions), len(candidates))
        for mode in ('Surface quality', 'Balanced', 'Custom'):
            self.assertAlmostEqual(modes[mode]['before']['bad_area_mm2'], 600)
            self.assertEqual(modes[mode]['after']['bad_area_mm2'], 0)
        height = 'build_height_mm'
        proxy = 'downward_projection_proxy_mm2'
        self.assertAlmostEqual(modes['Minimum height']['after'][height],
                               min(report['after'][height] for _, report in candidates))
        self.assertAlmostEqual(modes['Minimum supports proxy']['after'][proxy],
                               min(report['after'][proxy] for _, report in candidates))
        for mesh, report in candidates:
            self.assertAlmostEqual(mesh.bounds[0, 2], 0)
            self.assertAlmostEqual(report['after'][height], mesh.extents[2])
            self.assertAlmostEqual(mesh.volume, self.mesh.volume)
            up = np.asarray(report['build_up_input'])
            self.assertAlmostEqual(np.ptp(self.mesh.vertices @ up), mesh.extents[2])

    def test_invalid_custom_weights(self):
        for weights in ((0, 0, 0), (-1, 0, 0), (np.nan, 1, 1), (1, 2)):
            with self.subTest(weights=weights), self.assertRaises(ValueError):
                optimize_candidates(self.mesh, samples=32, custom_weights=weights)

    def test_selected_orientation_round_trip(self):
        mesh, report = optimize_candidates(self.mesh, samples=64)[-1]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'selected.stl'
            result = export_orientation(mesh, report, path)
            saved = trimesh.load(path, force='mesh')
            self.assertTrue(result['exported_watertight'])
            self.assertEqual(result['candidate_modes'], report['candidate_modes'])
            self.assertEqual(result['exported_build_height_mm'], saved.extents[2])
            np.testing.assert_allclose(saved.extents, mesh.extents, atol=5e-6)
            self.assertEqual(json.loads(path.with_suffix('.json').read_text()), result)

    def test_legacy_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            input_path = Path(folder) / 'input.stl'
            output_path = Path(folder) / 'output.stl'
            self.mesh.export(input_path)
            cli = Path(__file__).with_name('orientation_optimizer.py')
            run = subprocess.run(
                [sys.executable, str(cli), str(input_path), str(output_path),
                 '--low', '5', '--high', '13', '--margin', '.5', '--overhang', '45',
                 '--samples', '64'], check=True, capture_output=True, text=True)
            report = json.loads(run.stdout)
            self.assertEqual(report, json.loads(output_path.with_suffix('.json').read_text()))
            self.assertEqual(report['angle_band_deg'], [5, 13])
            self.assertEqual(report['exported_bad_area_mm2'], 0)
            self.assertTrue(report['exported_watertight'])


if __name__ == '__main__':
    unittest.main()
