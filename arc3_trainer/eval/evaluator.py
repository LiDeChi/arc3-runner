"""
Evaluator — run the solver against standard ARC tasks and compute metrics.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.task_io import load_task, load_tasks_from_dir, Task
from arc3_trainer.agent.solver import Solver, SolveResult

logger = logging.getLogger(__name__)


@dataclass
class TaskScore:
    """Score for a single evaluated task."""
    task_path: str
    success: bool
    program_cost: int = 0
    error_rate: float = 1.0
    trials_used: int = 0
    predicted: Optional[Grid] = None
    expected: Optional[Grid] = None


@dataclass
class EvalResult:
    """Aggregated evaluation results."""
    total: int
    successes: int
    accuracy: float
    total_cost: int
    avg_cost: float
    task_scores: List[TaskScore] = field(default_factory=list)

    @property
    def summary(self) -> str:
        return (
            f"Evaluated {self.total} tasks: "
            f"{self.successes} correct ({self.accuracy:.1%}), "
            f"avg program cost {self.avg_cost:.1f}"
        )


class Evaluator:
    """Evaluate solver against ARC tasks."""

    def __init__(self, solver: Optional[Solver] = None):
        self.solver = solver or Solver(beam_width=50, max_depth=5)

    def evaluate(self, task_paths: List[str | Path]) -> EvalResult:
        """Evaluate solver against a list of task files."""
        scores: List[TaskScore] = []
        successes = 0
        total_cost = 0

        for path in task_paths:
            try:
                task = load_task(path)
            except Exception as e:
                logger.warning(f"Failed to load {path}: {e}")
                continue

            result = self.solver.solve(task)
            expected = task.test[0][1] if task.test else None
            success = result.success

            ts = TaskScore(
                task_path=str(path),
                success=success,
                program_cost=result.program_cost,
                error_rate=result.error_rate,
                trials_used=result.trials_used,
                predicted=result.predicted_grid,
                expected=expected,
            )
            scores.append(ts)

            if success:
                successes += 1
            total_cost += result.program_cost

        total = len(scores)
        return EvalResult(
            total=total,
            successes=successes,
            accuracy=successes / max(total, 1),
            total_cost=total_cost,
            avg_cost=total_cost / max(total, 1),
            task_scores=scores,
        )

    def evaluate_dir(self, dir_path: str | Path) -> EvalResult:
        """Evaluate all JSON tasks in a directory."""
        p = Path(dir_path)
        paths = sorted(f for f in p.iterdir() if f.suffix == ".json")
        return self.evaluate(paths)

    def evaluate_json(self, task_json: dict) -> TaskScore:
        """Evaluate a single JSON task dict."""
        solver = self.solver
        result = solver.solve_json(task_json)
        expected_grid = None
        if task_json.get("test"):
            expected_grid = Grid(task_json["test"][0].get("output", [[0]]))

        return TaskScore(
            task_path="(inline)",
            success=result.success,
            program_cost=result.program_cost,
            error_rate=result.error_rate,
            trials_used=result.trials_used,
            predicted=result.predicted_grid,
            expected=expected_grid,
        )

    @staticmethod
    def print_report(result: EvalResult) -> None:
        """Print a human-readable evaluation report."""
        print("=" * 60)
        print("EVALUATION REPORT")
        print("=" * 60)
        print(result.summary)
        print()
        if result.task_scores:
            for ts in result.task_scores[:20]:  # show first 20
                status = "✓" if ts.success else "✗"
                print(f"  {status} {Path(ts.task_path).name} "
                      f"(cost={ts.program_cost})")
            if len(result.task_scores) > 20:
                print(f"  ... and {len(result.task_scores) - 20} more")
