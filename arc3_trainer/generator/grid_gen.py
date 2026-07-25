"""
GridGen — parameterised random grid generation for ARC tasks.

Generates grids of varying size, colour complexity, and structural patterns.
"""
from __future__ import annotations

import random
from typing import List, Optional, Tuple

import numpy as np

from arc3_trainer.cognitive.grid import Grid

# Pattern types
PATTERN_SOLID = "solid"
PATTERN_STRIPED = "striped"
PATTERN_CHECKERBOARD = "checkerboard"
PATTERN_BORDER = "border"
PATTERN_NOISE = "noise"
PATTERN_SYMMETRIC_H = "symmetric_h"
PATTERN_SYMMETRIC_V = "symmetric_v"
PATTERN_DIAGONAL = "diagonal"
PATTERN_CONCENTRIC = "concentric"


class GridGen:
    """Random grid generator with configurable parameters."""

    def __init__(self, seed: Optional[int] = None):
        self._rng = random.Random(seed)

    def generate(
        self,
        min_h: int = 2,
        max_h: int = 8,
        min_w: int = 2,
        max_w: int = 8,
        min_colors: int = 1,
        max_colors: int = 5,
        pattern: Optional[str] = None,
    ) -> Grid:
        """Generate a random grid."""
        h = self._rng.randint(min_h, min_h + (max_h - min_h) // 2)
        w = self._rng.randint(min_w, min_w + (max_w - min_w) // 2)
        h = min(h, 30)
        w = min(w, 30)
        n_colors = self._rng.randint(min_colors, min(max_colors, 9))

        if pattern is None:
            pattern = self._rng.choice([
                PATTERN_SOLID, PATTERN_STRIPED, PATTERN_CHECKERBOARD,
                PATTERN_BORDER, PATTERN_NOISE, PATTERN_SYMMETRIC_H,
                PATTERN_SYMMETRIC_V, PATTERN_DIAGONAL,
            ])

        return self._make_pattern(h, w, n_colors, pattern)

    def _make_pattern(self, h: int, w: int, n_colors: int, pattern: str) -> Grid:
        colors = self._rng.sample(range(10), min(n_colors, 10))

        if pattern == PATTERN_SOLID:
            c = self._rng.choice(colors)
            return Grid.full(h, w, c)

        elif pattern == PATTERN_STRIPED:
            arr = np.zeros((h, w), dtype=np.int8)
            for i in range(h):
                arr[i, :] = colors[i % len(colors)]
            return Grid(arr)

        elif pattern == PATTERN_CHECKERBOARD:
            arr = np.zeros((h, w), dtype=np.int8)
            for y in range(h):
                for x in range(w):
                    arr[y, x] = colors[(x + y) % len(colors)]
            return Grid(arr)

        elif pattern == PATTERN_BORDER:
            arr = np.full((h, w), colors[0] if len(colors) > 1 else 0, dtype=np.int8)
            border_c = self._rng.choice(colors)
            arr[0, :] = border_c
            arr[-1, :] = border_c
            arr[:, 0] = border_c
            arr[:, -1] = border_c
            return Grid(arr)

        elif pattern == PATTERN_NOISE:
            arr = np.zeros((h, w), dtype=np.int8)
            for y in range(h):
                for x in range(w):
                    arr[y, x] = self._rng.choice(colors)
            return Grid(arr)

        elif pattern == PATTERN_SYMMETRIC_H:
            arr = np.zeros((h, w), dtype=np.int8)
            for y in range(h):
                for x in range((w + 1) // 2):
                    c = self._rng.choice(colors)
                    arr[y, x] = c
                    arr[y, w - 1 - x] = c
            return Grid(arr)

        elif pattern == PATTERN_SYMMETRIC_V:
            arr = np.zeros((h, w), dtype=np.int8)
            for x in range(w):
                for y in range((h + 1) // 2):
                    c = self._rng.choice(colors)
                    arr[y, x] = c
                    arr[h - 1 - y, x] = c
            return Grid(arr)

        elif pattern == PATTERN_DIAGONAL:
            arr = np.zeros((h, w), dtype=np.int8)
            for i in range(min(h, w)):
                diag_c = self._rng.choice(colors)
                arr[i, i] = diag_c
            return Grid(arr)

        elif pattern == PATTERN_CONCENTRIC:
            arr = np.full((h, w), colors[-1], dtype=np.int8)
            for layer in range(min(h, w) // 2):
                c = colors[layer % len(colors)]
                x0, y0 = layer, layer
                x1, y1 = w - 1 - layer, h - 1 - layer
                arr[y0, x0:x1+1] = c
                arr[y1, x0:x1+1] = c
                arr[y0:y1+1, x0] = c
                arr[y0:y1+1, x1] = c
            return Grid(arr)

        return Grid.zeros(h, w)

    def generate_multiple(self, n: int = 5, **kwargs) -> List[Grid]:
        return [self.generate(**kwargs) for _ in range(n)]
