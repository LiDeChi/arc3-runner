"""Tests for the cognitive module."""
import unittest
import numpy as np
from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import (
    RotateCW, FlipH, Recolor, FillRect, Compose, Repeat, Crop, Expand, Translate
)
from arc3_trainer.cognitive.diff import DiffPerception
from arc3_trainer.cognitive.predictor import Predictor
from arc3_trainer.cognitive.task_io import Task, load_task, save_task


class TestGrid(unittest.TestCase):

    def setUp(self):
        self.small = Grid([[1, 2], [3, 4]])
        self.rect = Grid.zeros(3, 4)

    def test_basics(self):
        self.assertEqual(self.small.height, 2)
        self.assertEqual(self.small.width, 2)
        self.assertEqual(self.small.shape, (2, 2))
        self.assertEqual(int(self.small[0, 0]), 1)

    def test_equality(self):
        g1 = Grid([[1, 2], [3, 4]])
        g2 = Grid([[1, 2], [3, 4]])
        self.assertEqual(g1, g2)

    def test_rotate_cw(self):
        r = self.small.rotate_cw()
        self.assertEqual(r, Grid([[3, 1], [4, 2]]))

    def test_flip_h(self):
        f = self.small.flip_h()
        self.assertEqual(f, Grid([[2, 1], [4, 3]]))

    def test_recolor(self):
        r = self.small.recolor(1, 9)
        self.assertEqual(int(r[0, 0]), 9)
        self.assertEqual(int(r[0, 1]), 2)

    def test_fill_rect(self):
        g = Grid.zeros(4, 4)
        g = g.fill_rect(1, 1, 2, 2, 5)
        self.assertEqual(int(g[1, 1]), 5)
        self.assertEqual(int(g[0, 0]), 0)

    def test_flood_fill(self):
        g = Grid([
            [1, 1, 0],
            [1, 0, 0],
            [0, 0, 0],
        ])
        g = g.flood_fill(0, 0, 7)
        self.assertEqual(int(g[0, 0]), 7)
        self.assertEqual(int(g[1, 0]), 7)
        self.assertEqual(int(g[0, 2]), 0)

    def test_crop(self):
        g = self.small.crop(0, 0, 1, 1)
        self.assertEqual(g, Grid([[1]]))

    def test_expand(self):
        g = self.small.expand(3, 3)
        self.assertEqual(g.height, 3)
        self.assertEqual(g.width, 3)

    def test_translate(self):
        g = self.small.translate(1, 1)
        self.assertEqual(int(g[0, 0]), 0)
        self.assertEqual(int(g[1, 1]), 1)  # original (0,0) value moves to (1,1)

    def test_diff_mask(self):
        g1 = Grid([[1, 2], [3, 4]])
        g2 = Grid([[1, 9], [3, 4]])
        dm = g1.diff_mask(g2)
        self.assertEqual(int(dm[0, 0]), 0)
        self.assertEqual(int(dm[0, 1]), 1)


class TestActions(unittest.TestCase):

    def test_rotate_cw_action(self):
        g = Grid([[1, 2], [3, 4]])
        r = RotateCW()(g)
        self.assertEqual(r, Grid([[3, 1], [4, 2]]))

    def test_compose(self):
        g = Grid([[1, 2], [3, 4]])
        c = Compose(RotateCW(), FlipH())
        r = c(g)
        # rotate_cw: [[3,1],[4,2]] → flip_h: [[1,3],[2,4]]
        self.assertEqual(r, Grid([[1, 3], [2, 4]]))

    def test_repeat(self):
        g = Grid([[1, 2], [3, 4]])
        r = Repeat(RotateCW(), 4)(g)
        self.assertEqual(r, g)  # full cycle

    def test_recolor_action(self):
        g = Grid([[1, 2], [3, 4]])
        r = Recolor(1, 9)(g)
        self.assertEqual(int(r[0, 0]), 9)


class TestDiffPerception(unittest.TestCase):

    def setUp(self):
        self.dp = DiffPerception()

    def test_pixel_diff_same(self):
        before = Grid([[1, 2], [3, 4]])
        after = Grid([[1, 2], [3, 4]])
        result = self.dp.compare(before, after)
        self.assertEqual(result.pixel.changed_cells, 0)
        self.assertEqual(result.pixel.change_ratio, 0.0)

    def test_pixel_diff_changed(self):
        before = Grid([[1, 2], [3, 4]])
        after = Grid([[1, 9], [3, 4]])
        result = self.dp.compare(before, after)
        self.assertEqual(result.pixel.changed_cells, 1)

    def test_semantic_rotate_cw(self):
        before = Grid([[1, 2], [3, 4]])
        after = RotateCW()(before)
        result = self.dp.compare(before, after)
        self.assertEqual(result.semantics[0].operation, "rotate_cw")
        self.assertEqual(result.semantics[0].confidence, 1.0)

    def test_semantic_recolor(self):
        before = Grid([[1, 2], [3, 4]])
        after = Recolor(1, 9)(before)
        result = self.dp.compare(before, after)
        self.assertEqual(result.semantics[0].category, "coloring")

    def test_consensus_operation(self):
        before = Grid([[1, 2], [3, 4]])
        r1 = self.dp.compare(before, RotateCW()(before))
        r2 = self.dp.compare(before, RotateCW()(RotateCW()(before)))  # rotate_180
        # two pairs with rotate_cw
        before2 = Grid([[5, 6], [7, 8]])
        r3 = self.dp.compare(before2, RotateCW()(before2))
        r4 = self.dp.compare(before2, RotateCW()(RotateCW()(before2)))
        cons = self.dp.consensus_operation([r1, r3])
        self.assertIsNotNone(cons)
        self.assertEqual(cons.operation, "rotate_cw")


class TestPredictor(unittest.TestCase):

    def setUp(self):
        self.pred = Predictor()

    def test_forward(self):
        g = Grid([[1, 2], [3, 4]])
        r = self.pred.forward(g, RotateCW())
        self.assertEqual(r, Grid([[3, 1], [4, 2]]))

    def test_forward_chain(self):
        g = Grid([[1, 2], [3, 4]])
        r = self.pred.forward_chain(g, [RotateCW(), FlipH()])
        self.assertEqual(r, Grid([[1, 3], [2, 4]]))

    def test_inverse_rotate_cw(self):
        before = Grid([[1, 2], [3, 4]])
        after = RotateCW()(before)
        hypos = self.pred.inverse(before, after)
        self.assertTrue(any(h.kind == "rotate_cw" and h.score == 1.0 for h in hypos))

    def test_inverse_recolor(self):
        before = Grid([[1, 2], [3, 4]])
        after = Recolor(1, 9)(before)
        hypos = self.pred.inverse(before, after)
        self.assertTrue(any(h.kind == "recolor" and h.score == 1.0 for h in hypos))


class TestTaskIO(unittest.TestCase):

    def test_save_and_load(self):
        import tempfile, os
        task = Task()
        task.train.append((Grid([[1, 2], [3, 4]]), Grid([[3, 1], [4, 2]])))
        task.test.append((Grid([[5, 6], [7, 8]]), Grid([[7, 5], [8, 6]])))

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            save_task(task, path)

        loaded = load_task(path)
        self.assertEqual(len(loaded.train), 1)
        self.assertEqual(loaded.train[0][0], Grid([[1, 2], [3, 4]]))
        self.assertEqual(loaded.train[0][1], Grid([[3, 1], [4, 2]]))
        self.assertEqual(len(loaded.test), 1)
        os.unlink(path)


if __name__ == "__main__":
    unittest.main()
