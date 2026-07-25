"""Tests for the generator module."""
import unittest
from arc3_trainer.generator.grid_gen import GridGen
from arc3_trainer.generator.program_sampler import ProgramSampler, SamplerConfig
from arc3_trainer.generator.task_packer import TaskPacker, PackConfig
from arc3_trainer.generator.difficulty import DifficultyControl
from arc3_trainer.cognitive.actions import RotateCW, Recolor, Compose


class TestGridGen(unittest.TestCase):

    def setUp(self):
        self.gen = GridGen(seed=42)

    def test_generate_solid(self):
        grid = self.gen.generate(pattern="solid")
        self.assertIsNotNone(grid)
        self.assertGreaterEqual(grid.height, 1)
        self.assertGreaterEqual(grid.width, 1)

    def test_generate_various_patterns(self):
        for pattern in ["solid", "striped", "checkerboard", "border", "noise"]:
            grid = self.gen.generate(pattern=pattern)
            self.assertIsNotNone(grid)

    def test_generate_multiple(self):
        grids = self.gen.generate_multiple(5)
        self.assertEqual(len(grids), 5)


class TestProgramSampler(unittest.TestCase):

    def setUp(self):
        self.sampler = ProgramSampler(seed=42)

    def test_sample_atomic(self):
        program = self.sampler.sample(difficulty=1)
        self.assertIsNotNone(program)
        self.assertTrue(callable(program))

    def test_sample_with_grid(self):
        from arc3_trainer.cognitive.grid import Grid
        grid = Grid([[1, 2], [3, 4]])
        program, output = self.sampler.sample_with_grid(grid, difficulty=1)
        self.assertIsInstance(output, Grid)

    def test_sample_various_difficulties(self):
        for diff in range(1, 11):
            program = self.sampler.sample(difficulty=diff)
            self.assertIsNotNone(program)


class TestTaskPacker(unittest.TestCase):

    def setUp(self):
        self.packer = TaskPacker(seed=42)

    def test_pack_rotate_cw(self):
        task = self.packer.pack(RotateCW(), difficulty=1)
        self.assertIsNotNone(task)
        self.assertGreaterEqual(len(task.train), 1)
        self.assertGreaterEqual(len(task.test), 1)

    def test_pack_recolor(self):
        task = self.packer.pack(Recolor(1, 9), difficulty=1)
        self.assertIsNotNone(task)
        self.assertGreaterEqual(len(task.train), 1)

    def test_pack_compose(self):
        task = self.packer.pack(Compose(RotateCW(), Recolor(1, 9)), difficulty=3)
        self.assertIsNotNone(task)
        self.assertGreaterEqual(len(task.train), 1)


class TestDifficultyControl(unittest.TestCase):

    def test_evaluate_rotate(self):
        from arc3_trainer.cognitive.grid import Grid
        grid = Grid([[1, 2], [3, 4]])
        factors = DifficultyControl.evaluate(RotateCW(), grid)
        self.assertEqual(factors.action_count, 1)
        self.assertEqual(factors.program_depth, 1)

    def test_score(self):
        score = DifficultyControl.score(RotateCW())
        self.assertGreaterEqual(score, 1.0)
        self.assertLessEqual(score, 10.0)

    def test_level(self):
        level = DifficultyControl.level(RotateCW())
        self.assertGreaterEqual(level, 1)
        self.assertLessEqual(level, 10)


if __name__ == "__main__":
    unittest.main()
