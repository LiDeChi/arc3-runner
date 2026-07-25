"""
TaskPacker — given a seed grid and a transformation program, produce
a complete ARC task with train/test pairs.

Splitting strategy: the same transformation applied to different 
seed grids — some become train pairs, some become test pairs.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import Action
from arc3_trainer.cognitive.task_io import Task
from arc3_trainer.generator.grid_gen import GridGen


@dataclass
class PackConfig:
    """Configuration for task packing."""
    n_train: int = 3       # number of train pairs
    n_test: int = 1        # number of test pairs
    same_seed_family: bool = True  # all grids from same family of patterns
    grid_size_range: Tuple[int, int] = (2, 8)


class TaskPacker:
    """Pack seed grids + program into a complete ARC Task."""

    def __init__(self, config: Optional[PackConfig] = None, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self._grid_gen = GridGen(seed=seed)
        self.config = config or PackConfig()
        self._last_pattern: Optional[str] = None

    @property
    def last_pattern(self) -> Optional[str]:
        """The pattern family used by the most recent pack() call."""
        return self._last_pattern

    def pack(self, program: Action, difficulty: int = 1) -> Optional[Task]:
        """Generate a complete Task from a program.

        Returns None if program application fails on all seed grids.
        """
        failures = 0
        total_needed = self.config.n_train + self.config.n_test

        # Choose a family of patterns for consistency
        family_pattern = self._rng.choice([
            "solid", "striped", "checkerboard", "border", "noise",
            "symmetric_h", "symmetric_v", "diagonal",
        ])
        self._last_pattern = family_pattern

        pairs: List[Tuple[Grid, Grid]] = []
        for _ in range(total_needed * 3):  # generous attempts
            if len(pairs) >= total_needed:
                break

            grid = self._grid_gen.generate(pattern=family_pattern)
            try:
                output = program.apply(grid)
            except Exception:
                failures += 1
                if failures > 20:
                    return None
                continue

            # Validate output is a valid ARC grid
            if output.height < 1 or output.height > 30:
                continue
            if output.width < 1 or output.width > 30:
                continue

            pairs.append((grid, output))

        if len(pairs) < total_needed:
            return None

        # Split into train and test
        self._rng.shuffle(pairs)
        train_pairs = pairs[:self.config.n_train]
        test_pairs = pairs[self.config.n_train:self.config.n_train + self.config.n_test]

        # Ensure test output differs from train outputs (at least one pair)
        task = Task()
        for inp, out in train_pairs:
            task.train.append((inp, out))
        for inp, out in test_pairs:
            task.test.append((inp, out))

        if not task.train or not task.test:
            return None

        return task

    def pack_with_ground_truth(
        self, program: Action, difficulty: int = 1
    ) -> Optional[Tuple[Task, Grid, Grid]]:
        """Like pack() but also returns the test input and expected output."""
        task = self.pack(program, difficulty)
        if task is None or not task.test:
            return None
        test_inp, test_out = task.test[0]
        return task, test_inp, test_out
