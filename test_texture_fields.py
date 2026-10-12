"""Continuous field engine of the Texture Creator (numpy only, runs without Qt)."""
import unittest

import numpy as np

from modules.texture_creator import fields as F

N = 128


def seam_ratio(a):
    inner = np.abs(np.diff(a, axis=1)).mean() + np.abs(np.diff(a, axis=0)).mean()
    edge = np.abs(a[:, 0] - a[:, -1]).mean() + np.abs(a[0] - a[-1]).mean()
    return edge / inner


class FieldTests(unittest.TestCase):
    GENERATORS = {
        'perlin': lambda: F.perlin(N, 4, 5, .5, 2, 'fbm', 1, 1),
        'ridged': lambda: F.perlin(N, 3, 5, .5, 2, 'ridged', 1, 2),
        'streaks': lambda: F.perlin(N, 2, 4, .5, 2, 'fbm', 8, 3),
        'fibers': lambda: F.fibers(N, 400, 60, 1, 20, 40, .5, 4),
        'cracks': lambda: F.cracks(N, 30, 2.5, 'cracks', 1, .5, 5),
        'crackle': lambda: F.cracks(N, 100, 1, 'crackle', .45, .4, 6),
        'marble': lambda: F.veins(N, 'marble', 2, 1, 3, 6, 'vertical', 9),
        'grain': lambda: F.veins(N, 'grain', 8, 1, 6, 2, 'horizontal', 10),
        'satin': lambda: F.weave(N, 20, 'satin'),
        'triangle': lambda: F.gradient_field(N, 'triangle', 30, 2),
    }

    def test_generators_are_normalised_deterministic_and_seamless(self):
        for name, make in self.GENERATORS.items():
            with self.subTest(name=name):
                a = make()
                self.assertEqual(a.shape, (N, N)); self.assertEqual(a.dtype, np.float32)
                self.assertGreaterEqual(float(a.min()), 0); self.assertLessEqual(float(a.max()), 1)
                self.assertTrue(np.array_equal(a, make()))
                self.assertLess(seam_ratio(a), 1.8)

    def test_seed_changes_the_field(self):
        self.assertFalse(np.array_equal(F.perlin(N, seed=1), F.perlin(N, seed=2)))

    def test_operations_keep_range_and_seamlessness(self):
        a, b = F.perlin(N, 3, 4, .5, 2, 'fbm', 1, 1), F.perlin(N, 5, 4, .5, 2, 'fbm', 1, 2)
        for mode in F.BLEND_MODES:
            r = F.blend(a, b, mode, .7, F.gradient_field(N, 'triangle', 0, 1))
            self.assertTrue(0 <= r.min() and r.max() <= 1, mode)
        for r in (F.warp(a, b, 30, 'value', 45), F.warp(a, b, 30, 'gradient'), F.warp(a, b, 20, 'direction', 0, 1.5),
                  F.multiscale(a, 3), F.blur(a, 6, 30, 4), F.erosion(a, .6, 4), F.wear(a, .5)):
            self.assertLess(seam_ratio(r), 1.8)

    def test_levels_threshold_posterize_invert(self):
        a = F.gradient_field(N, 'linear', 0, 1)
        self.assertTrue(set(np.unique(F.levels(a, .5, .5001))) <= {0.0, 1.0})
        self.assertEqual(len(np.unique(F.levels(a, steps=4))), 4)
        self.assertAlmostEqual(float(F.levels(a, invert='yes')[0, 0]), 1 - float(a[0, 0]), places=5)

    def test_contours_enclose_exactly_the_region_above_the_level(self):
        field = F.perlin(64, 3, 4, .5, 2, 'fbm', 1, 7)
        g = (np.arange(64) + .5) * 512 / 64
        X, Y = np.meshgrid(g, g); X = X + .013; Y = Y + .017
        for level in (.3, .5, .7):
            inside = np.zeros(X.shape, bool)
            for loop in F.iso_loops(field, level):
                P = np.array(loop); x1, y1 = P[:, 0], P[:, 1]; x2, y2 = np.roll(x1, -1), np.roll(y1, -1)
                for i in range(len(P)):
                    crosses = (y1[i] > Y) != (y2[i] > Y)
                    xi = (x2[i] - x1[i]) * (Y - y1[i]) / ((y2[i] - y1[i]) or 1e-12) + x1[i]
                    inside ^= crosses & (X < xi)
            self.assertGreater((inside == (field >= level)).mean(), .995)


class ReliefTests(unittest.TestCase):
    def setUp(self):
        X, Y = np.meshgrid(np.arange(64), np.arange(64))
        self.bump = np.exp(-((X - 32) ** 2 + (Y - 32) ** 2) / 80).astype(np.float32)

    def test_flat_surface_receives_sine_of_elevation(self):
        flat = np.full((32, 32), .5, np.float32)
        self.assertAlmostEqual(float(F.relief(flat, -135, 30, 4, 1).mean()), .5, places=3)

    def test_side_facing_the_light_is_brighter(self):
        r = F.relief(self.bump, -135, 45, 4, 1)  # light from the top-left
        self.assertGreater(r[24, 24], r[40, 40] + .3)

    def test_normal_map_conventions(self):
        flat = F.normal_map(np.full((8, 8), .5, np.float32))
        self.assertEqual(tuple(flat[0, 0]), (128, 128, 255))
        gl, dx = F.normal_map(self.bump, convention='opengl'), F.normal_map(self.bump, convention='directx')
        self.assertGreater(gl[24, 32, 1], 128); self.assertLess(dx[24, 32, 1], 128)  # green flips

    def test_height16_and_ramp(self):
        self.assertEqual(F.height_map16(np.array([0, 1.])).tolist(), [0, 65535])
        colours = F.ramp(np.array([0, .25, .5, 1]), [0, 0, 0], [1, 1, 1], [1, 0, 0], .5)
        self.assertEqual(colours[2].tolist(), [1, 0, 0]); self.assertEqual(colours[1].tolist(), [.5, 0, 0])


class StructuredFieldTests(unittest.TestCase):
    def test_new_generators_are_seamless_and_normalised(self):
        for name, make in {'brick': lambda: F.tiles(N, 6, 12, 'brick', 4, 6), 'hex': lambda: F.tiles(N, 8, 8, 'hex', 3, 6),
                           'scales': lambda: F.scales(N, 8, 14, .5), 'pebbles': lambda: F.pebbles(N, 50),
                           'stripes': lambda: F.stripes(N, 8, 30, 2, .6, 1)}.items():
            with self.subTest(name=name):
                a = make()
                self.assertTrue(0 <= a.min() and a.max() <= 1)
                self.assertTrue(np.array_equal(a, make()))
                self.assertLess(seam_ratio(a), 3.0)

    def test_tiles_have_mortar_and_bevel(self):
        a = F.tiles(N, 4, 4, 'grid', 8, 30, 'linear', 0)
        self.assertEqual(float(a.min()), 0.0)              # mortar
        self.assertAlmostEqual(float(a.max()), 1.0, 3)     # plateau after the bevel
        self.assertGreater(len(np.unique(np.round(a, 2))), 6)  # sloped bevel in between

    def test_distance_matches_a_disc(self):
        n = 128; g = (np.arange(n) + .5) * 512 / n; X, Y = np.meshgrid(g, g)
        r = np.hypot(X - 256, Y - 256); disc = (r < 100).astype(np.float32)
        d = F.distance_inside(disc, .5, 64); true = np.clip(100 - r, 0, 64)
        inside = (disc > 0) & (true < 60)
        self.assertLess(float(np.abs(d[inside] - true[inside]).mean()), 3.0)

    def test_operations(self):
        a = F.perlin(N, 3, 4, .5, 2, 'fbm', 1, 1)
        scan = F.histogram_scan(a, .5, 1)
        self.assertGreater(float(((scan < .01) | (scan > .99)).mean()), .99)  # a hard threshold
        mirror = F.symmetry(a, 'mirror x'); self.assertTrue(np.allclose(mirror, mirror[:, ::-1]))
        for value in (F.slope(a), F.curvature(a, 3, 'concave'), F.ambient_occlusion(a, 16), F.slope_blur(a, a, 10), F.bevel(a, .5, 8)):
            self.assertTrue(0 <= value.min() and value.max() <= 1)
        self.assertGreater(float(F.ambient_occlusion(a, 16).mean()), .5)  # mostly unoccluded

    def test_imported_image_becomes_tileable(self):
        rng = np.random.default_rng(1); gradient = np.tile(np.linspace(0, 255, 300), (200, 1))
        raw = F.from_image(gradient, N, tileable=False); tiled = F.from_image(gradient, N, tileable=True)
        self.assertGreater(seam_ratio(raw), 20)  # a left→right ramp has a hard seam
        self.assertLess(seam_ratio(tiled), seam_ratio(raw) / 4)


if __name__ == '__main__':
    unittest.main()
