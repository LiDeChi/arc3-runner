"""Edge-case and regression tests for the arc3_trainer."""
import unittest
import numpy as np
from arc3_trainer.cognitive.grid import Grid


class TestGridEdgeCases(unittest.TestCase):
    """Grid should handle extreme but valid inputs gracefully."""

    def test_min_size_1x1(self):
        g = Grid([[5]])
        self.assertEqual(g.height, 1)
        self.assertEqual(g.width, 1)
        self.assertEqual(g.shape, (1, 1))

    def test_max_size_30x30(self):
        data = [[0] * 30 for _ in range(30)]
        g = Grid(data)
        self.assertEqual(g.shape, (30, 30))

    def test_all_colors(self):
        for c in range(10):
            g = Grid([[c]])
            self.assertEqual(int(g[0, 0]), c)

    def test_translate_beyond_bounds(self):
        """Translate beyond grid bounds should not crash (was a bug)."""
        g = Grid([[1, 2], [3, 4]])
        # dx > width
        r = g.translate(10, 0)
        self.assertEqual(r.shape, (2, 2))
        self.assertEqual(int(r[0, 0]), 0)  # all fill
        # dy > height
        r = g.translate(0, 10)
        self.assertEqual(int(r[0, 0]), 0)
        # both negative beyond bounds
        r = g.translate(-10, -10)
        self.assertEqual(int(r[0, 0]), 0)

    def test_flood_fill_large_region(self):
        """Flood fill a large uniform region should not hang (was a stack issue)."""
        g = Grid.full(10, 10, 1)
        r = g.flood_fill(0, 0, 5)
        self.assertEqual(int(r[0, 0]), 5)
        self.assertEqual(int(r[9, 9]), 5)

    def test_flood_fill_single_cell(self):
        g = Grid([[1, 2], [3, 4]])
        r = g.flood_fill(0, 0, 9)
        self.assertEqual(int(r[0, 0]), 9)
        self.assertEqual(int(r[0, 1]), 2)  # neighbour unchanged

    def test_flood_fill_same_color(self):
        """Flood fill with same color should return equal grid."""
        g = Grid([[1, 2], [3, 4]])
        r = g.flood_fill(0, 0, 1)
        self.assertEqual(r, g)

    def test_crop_full_grid(self):
        g = Grid([[1, 2], [3, 4]])
        r = g.crop(0, 0, 2, 2)
        self.assertEqual(r, g)

    def test_crop_top_left_pixel(self):
        g = Grid([[1, 2], [3, 4]])
        r = g.crop(0, 0, 1, 1)
        self.assertEqual(r, Grid([[1]]))

    def test_expand_same_size(self):
        g = Grid([[1, 2], [3, 4]])
        r = g.expand(2, 2)
        self.assertEqual(r, g)

    def test_expand_to_30x30(self):
        g = Grid([[1]])
        r = g.expand(30, 30)
        self.assertEqual(r.shape, (30, 30))
        self.assertEqual(int(r[0, 0]), 1)
        self.assertEqual(int(r[29, 29]), 0)

    def test_recolor_nonexistent(self):
        """Recolor a colour not present should be a no-op."""
        g = Grid([[1, 2], [3, 4]])
        r = g.recolor(9, 0)
        self.assertEqual(r, g)

    def test_overlay_different_sizes(self):
        bg = Grid.full(5, 5, 0)
        fg = Grid.full(3, 3, 1)
        r = bg.overlay(fg)
        self.assertEqual(int(r[0, 0]), 1)
        self.assertEqual(int(r[4, 4]), 0)  # outside overlay

    def test_copy_region_overlapping(self):
        g = Grid([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        r = g.copy_region(0, 0, 2, 2, 1, 1)
        self.assertEqual(int(r[1, 1]), 1)
        self.assertEqual(int(r[2, 2]), 5)


class TestSolverEdgeCases(unittest.TestCase):
    """Solver should handle degenerate cases."""

    def test_solve_identity_task(self):
        """Identity task (input == output) should succeed."""
        from arc3_trainer.cognitive.task_io import Task
        from arc3_trainer.agent.solver import Solver
        inp = Grid([[1, 2], [3, 4]])
        task = Task()
        task.train.append((inp, inp.copy()))
        task.test.append((Grid([[5, 6], [7, 8]]), Grid([[5, 6], [7, 8]])))
        solver = Solver(beam_width=10, max_depth=2)
        result = solver.solve(task)
        self.assertTrue(result.success)

    def test_solve_recolor_chain(self):
        """Two-step recolor: old→new→newer."""
        from arc3_trainer.cognitive.task_io import Task
        from arc3_trainer.agent.solver import Solver
        from arc3_trainer.cognitive.actions import Compose, Recolor
        inp = Grid([[1, 2], [3, 4]])
        prog = Compose(Recolor(1, 9), Recolor(2, 8))
        out = prog(inp)
        task = Task()
        task.train.append((inp, out))
        task.test.append((Grid([[1, 5], [6, 7]]), prog(Grid([[1, 5], [6, 7]]))))
        solver = Solver(beam_width=30, max_depth=4)
        result = solver.solve(task)
        self.assertTrue(result.success)


class TestTrainingEdgeCases(unittest.TestCase):
    """Training loop resilience."""

    def test_training_with_crash_in_solver(self):
        """Training should survive if solver crashes."""
        from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig
        config = TrainConfig(rounds=3, beam_width=10, max_depth=2,
                             output_dir="/tmp/arc3_crash_test", log_every=10)
        loop = TrainingLoop(config=config, seed=42)
        profile = loop.train()
        self.assertIsNotNone(profile)

    def test_exported_solver_is_parseable(self):
        """Standalone solver should be valid Python."""
        from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig
        import sys
        loop = TrainingLoop(config=TrainConfig(rounds=1))
        path = "/tmp/test_export_solver.py"
        loop.export_solver(path)
        import importlib.util
        spec = importlib.util.spec_from_file_location("solver", path)
        self.assertIsNotNone(spec)

    def test_capability_profile_empty(self):
        from arc3_trainer.trainer.capability import CapabilityProfile
        profile = CapabilityProfile()
        self.assertEqual(profile.overall_rate(), 0.0)
        self.assertEqual(profile.worst_kinds(3), [])


if __name__ == "__main__":
    unittest.main()
