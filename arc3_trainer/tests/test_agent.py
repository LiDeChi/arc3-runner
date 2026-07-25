"""Tests for the agent module."""
import unittest
import numpy as np
from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import RotateCW, Recolor, FlipH, Compose
from arc3_trainer.agent.perceiver import Perceiver
from arc3_trainer.agent.hypothesizer import Hypothesizer
from arc3_trainer.agent.searcher import Searcher, program_cost
from arc3_trainer.agent.solver import Solver


class TestPerceiver(unittest.TestCase):

    def setUp(self):
        self.perceiver = Perceiver()

    def test_perceive_rotate_cw(self):
        inp = Grid([[1, 2], [3, 4]])
        out = RotateCW()(inp)  # [[3,1],[4,2]]
        constraints = self.perceiver.perceive([(inp, out)])
        self.assertEqual(len(constraints.pairs), 1)
        self.assertFalse(constraints.shape_changed)
        self.assertIsNotNone(constraints.consensus_operation)
        self.assertEqual(constraints.consensus_operation.operation, "rotate_cw")

    def test_perceive_recolor(self):
        inp = Grid([[1, 2], [3, 4]])
        out = Recolor(1, 9)(inp)
        constraints = self.perceiver.perceive([(inp, out)])
        self.assertEqual(constraints.colours_in_output_only, {9})
        self.assertEqual(constraints.colours_in_input_only, {1})

    def test_perceive_multi_pair(self):
        inp = Grid([[1, 2], [3, 4]])
        action = RotateCW()
        pairs = [(inp, action(inp))]
        inp2 = Grid([[5, 6], [7, 8]])
        pairs.append((inp2, action(inp2)))
        constraints = self.perceiver.perceive(pairs)
        self.assertEqual(constraints.consensus_operation.operation, "rotate_cw")


class TestHypothesizer(unittest.TestCase):

    def setUp(self):
        self.perceiver = Perceiver()
        self.hypothesizer = Hypothesizer(max_hypotheses_per_pair=50)

    def test_hypothesize_rotate_cw(self):
        inp = Grid([[1, 2], [3, 4]])
        out = RotateCW()(inp)
        constraints = self.perceiver.perceive([(inp, out)])
        hypos = self.hypothesizer.hypothesize(constraints)
        self.assertEqual(len(hypos), 1)
        kinds = [h.kind for h in hypos[0][:10]]
        self.assertIn("rotate_cw", kinds)


class TestSearcher(unittest.TestCase):

    def test_search_rotate_cw(self):
        inp = Grid([[1, 2], [3, 4]])
        out = RotateCW()(inp)
        searcher = Searcher(beam_width=20, max_depth=3)
        program = searcher.search([(inp, out)])
        self.assertIsNotNone(program)
        self.assertTrue(program.apply(inp).equals(out))

    def test_search_compose(self):
        inp = Grid([[1, 2], [3, 4]])
        action = Compose(RotateCW(), FlipH())
        out = action(inp)
        searcher = Searcher(beam_width=30, max_depth=4)
        program = searcher.search([(inp, out)])
        self.assertIsNotNone(program)
        self.assertTrue(program.apply(inp).equals(out))

    def test_search_recolor(self):
        inp = Grid([[1, 2], [3, 4]])
        out = Recolor(1, 9)(inp)
        searcher = Searcher(beam_width=20, max_depth=3)
        program = searcher.search([(inp, out)])
        self.assertIsNotNone(program)
        self.assertTrue(program.apply(inp).equals(out))

    def test_search_multi_pair(self):
        inp = Grid([[1, 2], [3, 4]])
        action = RotateCW()
        pairs = [(inp, action(inp))]
        inp2 = Grid([[5, 6], [7, 8]])
        pairs.append((inp2, action(inp2)))
        searcher = Searcher(beam_width=20, max_depth=3)
        program = searcher.search(pairs)
        self.assertIsNotNone(program)
        for i, o in pairs:
            self.assertTrue(program.apply(i).equals(o))


class TestSolver(unittest.TestCase):

    def test_solve_rotate_cw(self):
        inp = Grid([[1, 2], [3, 4]])
        out = RotateCW()(inp)
        from arc3_trainer.cognitive.task_io import Task
        task = Task()
        task.train.append((inp, out))
        task.test.append((Grid([[5, 6], [7, 8]]), Grid([[7, 5], [8, 6]])))

        solver = Solver(beam_width=30, max_depth=4)
        result = solver.solve(task)
        self.assertTrue(result.success, f"Expected success, got error_rate={result.error_rate}")
        self.assertIsNotNone(result.predicted_grid)

    def test_solve_recolor(self):
        inp = Grid([[1, 2], [3, 4]])
        out = Recolor(1, 9)(inp)
        from arc3_trainer.cognitive.task_io import Task
        task = Task()
        task.train.append((inp, out))
        task.test.append((Grid([[1, 5], [6, 7]]), Grid([[9, 5], [6, 7]])))

        solver = Solver(beam_width=30, max_depth=4)
        result = solver.solve(task)
        self.assertTrue(result.success, f"Expected success, got error_rate={result.error_rate}")


if __name__ == "__main__":
    unittest.main()
