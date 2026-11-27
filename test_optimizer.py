import unittest
import numpy as np
import trimesh
from orientation_optimizer import metrics, optimize

class TestOptimizer(unittest.TestCase):
    def test_band_is_upward_and_area_weighted(self):
        angles = np.deg2rad([0, 5.5, 10, 13.5, 20])
        n = np.column_stack((np.sin(angles), np.zeros(5), np.cos(angles)))
        n = np.vstack((n, -n))
        a = np.arange(1., 11.)
        result = metrics(n, a, [[0,0,1]])[0]
        self.assertAlmostEqual(result[0], 5.)
        self.assertAlmostEqual(result[1], 9.)
    def test_box(self):
        m = trimesh.creation.box(extents=[10,20,30])
        m.apply_transform(trimesh.transformations.rotation_matrix(np.deg2rad(10), [1,0,0]))
        out, report = optimize(m, samples=128)
        self.assertGreater(report['before']['bad_area_mm2'], 0)
        self.assertEqual(report['after']['bad_area_mm2'], 0)
        self.assertTrue(out.is_watertight)
        self.assertAlmostEqual(out.volume, m.volume)
        self.assertAlmostEqual(out.bounds[0,2], 0)
    def test_invalid_band(self):
        with self.assertRaises(ValueError): optimize(trimesh.creation.box(), low=13, high=5)

if __name__ == '__main__': unittest.main()
