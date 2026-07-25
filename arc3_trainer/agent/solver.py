"""
Solver — unified entry point: task in → output grid out.

Pipeline:
  1. Perceiver extracts constraints from train pairs
  2. Hypothesizer generates candidate actions
  3. Searcher beam-searches for best program
  4. Apply program to test input → output

Includes 3-trial retry (ARC standard).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import Action, ActionDSL
from arc3_trainer.cognitive.task_io import Task
from arc3_trainer.agent.perceiver import Perceiver, TaskConstraints
from arc3_trainer.agent.hypothesizer import Hypothesizer
from arc3_trainer.agent.searcher import Searcher, SearchNode, program_cost as pc_fn

logger = logging.getLogger(__name__)


@dataclass
class SolveResult:
    """Result of solving a task."""
    success: bool
    predicted_grid: Optional[Grid] = None
    program: Optional[Action] = None
    program_cost: int = 0
    error_rate: float = 1.0
    trials_used: int = 0
    constraints: Optional[TaskConstraints] = None
    # Detailed trace for dashboard
    seed_actions: Optional[List[Action]] = None
    search_trace: Optional[List[Dict]] = None  # list of {depth, beam_size, best_cost, best_error}


class Solver:
    """Main agent: solves an ARC task from its train/test pairs."""

    def __init__(self, beam_width: int = 80, max_depth: int = 6,
                 event_callback: Optional[Callable] = None):
        self._perceiver = Perceiver()
        self._hypothesizer = Hypothesizer(max_hypotheses_per_pair=beam_width * 2)
        self._searcher = Searcher(beam_width=beam_width, max_depth=max_depth)
        self._event_callback = event_callback or (lambda ev, data: None)

    def solve(self, task: Task, max_trials: int = 3) -> SolveResult:
        """Solve a full Task (multiple train pairs + test inputs).

        For the first test input, tries up to max_trials.
        """
        return self._solve_one(task.train, task.test, max_trials)

    def solve_json(self, task_json: Dict) -> SolveResult:
        """Solve from a raw ARC JSON dict."""
        task = Task()
        for pair in task_json.get("train", []):
            task.train.append((Grid(pair["input"]), Grid(pair["output"])))
        for pair in task_json.get("test", []):
            inp = Grid(pair["input"])
            out = Grid(pair.get("output", [[0]]))
            task.test.append((inp, out))
        return self._solve_one(task.train, task.test)

    def _solve_one(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        test_pairs: List[Tuple[Grid, Grid]],
        max_trials: int = 3,
    ) -> SolveResult:
        ec = self._event_callback

        # Step 1: Perceive
        ec("solver_stage", {"stage": "perceiver", "status": "start"})
        constraints = self._perceiver.perceive(train_pairs)

        # Build a human-readable summary of constraints
        perceive_summary = {
            "shape_changed": constraints.shape_changed,
            "colours_used": sorted(constraints.colours_used),
            "colours_in_output_only": sorted(constraints.colours_in_output_only),
            "colours_in_input_only": sorted(constraints.colours_in_input_only),
            "consensus_operation": constraints.consensus_operation.operation
                if constraints.consensus_operation else None,
            "all_operations": constraints.all_operations[:5],
            "num_pairs": len(constraints.pairs),
        }
        # Also attach grid previews for the first train pair
        if constraints.pairs:
            pc = constraints.pairs[0]
            perceive_summary["train_input"] = pc.input_grid.as_list()
            perceive_summary["train_output"] = pc.output_grid.as_list()
        ec("solver_stage", {"stage": "perceiver", "status": "done", "data": perceive_summary})

        # Step 2: Hypothesize
        ec("solver_stage", {"stage": "hypothesizer", "status": "start"})
        hypos = self._hypothesizer.hypothesize(constraints)

        # Collect seed actions from hypotheses
        seed_actions: List[Action] = []
        seen_kinds: set = set()
        for hlist in hypos:
            for h in hlist[:10]:  # top 10 per pair
                if h.kind not in seen_kinds:
                    seen_kinds.add(h.kind)
                    seed_actions.append(h.action)
                    if len(seed_actions) >= 20:
                        break
            if len(seed_actions) >= 20:
                break

        # Emit hypothesis summary
        hypo_data = {
            "total_hypotheses_per_pair": [len(h) for h in hypos],
            "seed_action_kinds": [a.kind() for a in seed_actions[:10]],
            "num_seed_actions": len(seed_actions),
        }
        ec("solver_stage", {"stage": "hypothesizer", "status": "done", "data": hypo_data})

        # Step 3: Search
        ec("solver_stage", {"stage": "searcher", "status": "start"})
        searcher = self._searcher
        program, search_trace = searcher.search_traced(
            train_pairs, seed_actions=seed_actions
        )

        search_data = {
            "total_depth": len(search_trace) if search_trace else 0,
            "trace": [
                {"depth": t["depth"], "beam_size": t["beam_size"],
                 "best_cost": t["best_cost"], "best_error": t["best_error"]}
                for t in (search_trace or [])
            ],
        }
        ec("solver_stage", {"stage": "searcher", "status": "done", "data": search_data})

        if program is None:
            ec("solver_stage", {"stage": "result", "status": "done",
                                "data": {"success": False, "reason": "no_program_found"}})
            return SolveResult(success=False, error_rate=1.0,
                               constraints=constraints, search_trace=search_trace)

        # Step 4: Apply to test input
        test_inp = test_pairs[0][0]
        for trial in range(1, max_trials + 1):  # 1..3
            try:
                predicted = program.apply(test_inp)
                # Check against expected if available
                expected = test_pairs[0][1]
                result = SolveResult(
                    success=predicted.equals(expected) if hasattr(expected, 'equals') else False,
                    predicted_grid=predicted,
                    program=program,
                    program_cost=pc_fn(program),
                    error_rate=0.0 if predicted.equals(expected) else 1.0,
                    trials_used=trial,
                    constraints=constraints,
                    seed_actions=seed_actions,
                    search_trace=search_trace,
                )
                result.success = predicted.equals(expected)
                result.error_rate = 0.0 if result.success else 1.0

                result_data = {
                    "success": result.success,
                    "error_rate": result.error_rate,
                    "program_kind": program.kind(),
                    "program_cost": pc_fn(program),
                    "trials_used": trial,
                }
                # Attach grids for visualization
                if constraints.pairs:
                    result_data["test_input"] = test_inp.as_list()
                    result_data["predicted"] = predicted.as_list()
                    try:
                        result_data["expected"] = expected.as_list()
                    except Exception:
                        pass
                ec("solver_stage", {"stage": "result", "status": "done", "data": result_data})
                return result

            except Exception as e:
                logger.warning(f"Trial {trial} failed: {e}")
                if trial == max_trials:
                    ec("solver_stage", {"stage": "result", "status": "done",
                                        "data": {"success": False, "reason": f"apply_failed: {e}"}})
                    return SolveResult(success=False, error_rate=1.0,
                                       constraints=constraints, search_trace=search_trace)

        ec("solver_stage", {"stage": "result", "status": "done",
                            "data": {"success": False, "reason": "max_trials_exhausted"}})
        return SolveResult(success=False, error_rate=1.0, constraints=constraints,
                           search_trace=search_trace)
