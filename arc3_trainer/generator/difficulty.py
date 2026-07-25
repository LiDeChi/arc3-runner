"""
DifficultyControl — map program complexity and grid size to a 1-10
difficulty score.

Factors:
  - Program depth (number of compose layers)
  - Action count (total atomic actions in program)
  - Use of control flow (repeat/conditional) = more difficult
  - Grid size (larger = harder to reason about)
  - Number of colours used
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from arc3_trainer.cognitive.actions import (
    Action, Compose, Repeat, Conditional,
)
from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.agent.searcher import program_cost


@dataclass
class DifficultyFactors:
    """Breakdown of factors contributing to difficulty."""
    program_depth: int = 1
    action_count: int = 1
    has_control_flow: bool = False
    grid_area: int = 4
    num_colours: int = 2
    score: float = 1.0


class DifficultyControl:
    """Compute and manage difficulty levels for task generation."""

    LEVELS = list(range(1, 11))  # 1-10

    @staticmethod
    def evaluate(program: Action, input_grid: Optional[Grid] = None) -> DifficultyFactors:
        """Compute difficulty factors for a program and optional grid."""
        depth = 0
        action_count = 0
        has_control = False

        def walk(a: Action, d: int = 1):
            nonlocal depth, action_count, has_control
            depth = max(depth, d)
            if isinstance(a, Compose):
                walk(a.first, d + 1)
                walk(a.second, d + 1)
            elif isinstance(a, Repeat):
                has_control = True
                walk(a.action, d + 1)
            elif isinstance(a, Conditional):
                has_control = True
                walk(a.then_action, d + 1)
                walk(a.else_action, d + 1)
            else:
                action_count += 1

        walk(program)

        area = (input_grid.height * input_grid.width) if input_grid else 4
        colours = len({v for _, _, v in input_grid.cells()}) if input_grid else 2

        return DifficultyFactors(
            program_depth=depth,
            action_count=action_count,
            has_control_flow=has_control,
            grid_area=area,
            num_colours=max(colours, 1),
        )

    @staticmethod
    def score(program: Action, input_grid: Optional[Grid] = None) -> float:
        """Compute a single 1-10 difficulty score."""
        factors = DifficultyControl.evaluate(program, input_grid)

        # Base from program cost
        cost = program_cost(program)
        base = min(cost / 3.0, 5.0)

        # Bonus for control flow
        control_bonus = 2.0 if factors.has_control_flow else 0.0

        # Bonus for grid size
        size_bonus = min(factors.grid_area / 30.0, 1.5)

        # Bonus for colour diversity
        colour_bonus = min(factors.num_colours / 5.0, 1.0)

        raw = base + control_bonus + size_bonus + colour_bonus
        return max(1.0, min(10.0, raw))

    @staticmethod
    def level(program: Action, input_grid: Optional[Grid] = None) -> int:
        """Map to discrete 1-10 level."""
        return min(10, max(1, round(DifficultyControl.score(program, input_grid))))
