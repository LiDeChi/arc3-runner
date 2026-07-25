"""
ProgramSampler — sample transformation programs from the DSL.

Supports biased sampling by action type, depth control for compositions,
and parameter randomisation.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from arc3_trainer.cognitive.actions import (
    Action, ActionDSL,
    RotateCW, RotateCCW, Rotate180, FlipH, FlipV, Translate,
    Recolor, FillRect, FloodFill, Crop, Expand, CopyRegion, Overlay,
    Compose, Repeat, Conditional,
)
from arc3_trainer.cognitive.grid import Grid


# Default action type weights (higher = more likely to be sampled)
DEFAULT_WEIGHTS: Dict[str, float] = {
    "rotate_cw": 3.0, "rotate_ccw": 3.0, "rotate_180": 1.0,
    "flip_h": 2.0, "flip_v": 2.0,
    "translate": 2.0,
    "recolor": 3.0,
    "fill_rect": 1.0,
    "flood_fill": 1.0,
    "crop": 1.5,
    "expand": 1.0,
    "copy_region": 1.0,
    "overlay": 1.0,
}


@dataclass
class SamplerConfig:
    """Configuration for program sampling."""
    atomic_weights: Dict[str, float] = field(default_factory=lambda: DEFAULT_WEIGHTS.copy())
    compose_prob: float = 0.4        # probability of composing 2 actions
    repeat_prob: float = 0.2         # probability of repeating an action
    conditional_prob: float = 0.05   # probability of conditional
    max_depth: int = 4               # max composition depth
    max_repeat_n: int = 4            # max repeat count
    min_repeat_n: int = 2            # min repeat count


class ProgramSampler:
    """Sample transformation programs from the DSL."""

    def __init__(self, config: Optional[SamplerConfig] = None, seed: Optional[int] = None):
        self._rng = random.Random(seed)
        self.config = config or SamplerConfig()

    def sample(self, difficulty: int = 1) -> Action:
        """Sample a program at a given difficulty level (1-10)."""
        depth = min(difficulty // 2 + 1, self.config.max_depth)

        if difficulty <= 2:
            # Single atomic action
            return self._sample_atomic()
        elif difficulty <= 4:
            # Atomic or simple compose
            if self._rng.random() < 0.5:
                return self._sample_atomic()
            return self._sample_compose(depth)
        elif difficulty <= 6:
            # Compose or repeat
            if self._rng.random() < 0.3:
                return Repeat(self._sample_atomic(), self._rng.randint(2, 4))
            return self._sample_compose(depth)
        else:
            # Deep compose with potential repeat/conditional
            return self._sample_compose(depth)

    def sample_with_grid(
        self, grid: Grid, difficulty: int = 1,
    ) -> Tuple[Action, Grid]:
        """Sample a program and apply it to grid to produce output."""
        program = self.sample(difficulty)
        try:
            output = program.apply(grid)
        except Exception:
            # Fall back to identity
            output = grid.copy()
            program = ActionDSL.all_atomic()[0]
            output = program.apply(grid)
        return program, output

    def _sample_atomic(self) -> Action:
        """Sample a single atomic action with randomised parameters."""
        kind = self._weighted_choice(self.config.atomic_weights)

        if kind == "rotate_cw":
            return RotateCW()
        elif kind == "rotate_ccw":
            return RotateCCW()
        elif kind == "rotate_180":
            return Rotate180()
        elif kind == "flip_h":
            return FlipH()
        elif kind == "flip_v":
            return FlipV()
        elif kind == "translate":
            dx = self._rng.randint(-3, 3)
            dy = self._rng.randint(-3, 3)
            if dx == 0 and dy == 0:
                dx = 1
            return Translate(dx, dy)
        elif kind == "recolor":
            old = self._rng.randint(0, 9)
            new = self._rng.randint(0, 9)
            while new == old:
                new = self._rng.randint(0, 9)
            return Recolor(old, new)
        elif kind == "fill_rect":
            return FillRect(0, 0, 2, 2, self._rng.randint(0, 9))
        elif kind == "flood_fill":
            return FloodFill(0, 0, self._rng.randint(0, 9))
        elif kind == "crop":
            return Crop(0, 0, 2, 2)
        elif kind == "expand":
            return Expand(4, 4)
        elif kind == "copy_region":
            return CopyRegion(0, 0, 2, 2, 2, 2)
        elif kind == "overlay":
            # overlay a small checker pattern at origin
            from arc3_trainer.cognitive.grid import Grid as _Grid
            other = _Grid([[1, 2], [3, 4]])
            return Overlay(other, x=0, y=0, mask_color=0)
        else:
            return RotateCW()

    def _sample_compose(self, max_depth: int) -> Action:
        """Sample a possibly composite program."""
        if max_depth <= 1:
            return self._sample_atomic()

        # Decide structure
        r = self._rng.random()

        if r < self.config.compose_prob:
            left = self._sample_compose(max_depth - 1)
            right = self._sample_compose(max_depth - 1)
            return Compose(left, right)

        elif r < self.config.compose_prob + self.config.repeat_prob:
            inner = self._sample_atomic()
            n = self._rng.randint(self.config.min_repeat_n, self.config.max_repeat_n)
            return Repeat(inner, n)

        elif r < (self.config.compose_prob + self.config.repeat_prob
                  + self.config.conditional_prob):
            then_a = self._sample_atomic()
            else_a = self._sample_atomic()
            cond = self._rng.choice([
                "has_color_1", "has_color_2", "width_gt_height", "height_gt_width",
            ])
            return Conditional(cond, then_a, else_a)

        else:
            return self._sample_atomic()

    def _weighted_choice(self, weights: Dict[str, float]) -> str:
        """Pick a key from weights dict proportionally."""
        items = list(weights.items())
        total = sum(w for _, w in items)
        r = self._rng.uniform(0, total)
        upto = 0.0
        for k, w in items:
            upto += w
            if r <= upto:
                return k
        return items[-1][0]

    def sample_biased(self, weights: Dict[str, float]) -> Action:
        """Sample with explicit weight override (for adversarial sampling)."""
        old_weights = dict(self.config.atomic_weights)
        self.config.atomic_weights.update(weights)
        action = self._sample_atomic()
        self.config.atomic_weights = old_weights  # restore
        return action
