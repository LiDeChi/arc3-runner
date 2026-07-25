"""
Hypothesizer — generate candidate (action, param) hypotheses from constraints.

Given TaskConstraints from the Perceiver, the Hypothesizer produces
a list of candidate Actions that could explain the input→output mapping.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import (
    Action, ActionDSL,
    RotateCW, RotateCCW, Rotate180, FlipH, FlipV, Translate,
    Recolor, FillRect, FloodFill, Crop, Expand, CopyRegion, Overlay,
    Compose, Repeat, Conditional,
)
from arc3_trainer.cognitive.diff import SemanticDiff
from arc3_trainer.cognitive.predictor import Predictor, InverseHypothesis
from arc3_trainer.agent.perceiver import TaskConstraints


class Hypothesizer:
    """Generate candidate actions from perceived constraints."""

    def __init__(self, max_hypotheses_per_pair: int = 50):
        self._predictor = Predictor()
        self._max_hypo = max_hypotheses_per_pair

    def hypothesize(
        self, constraints: TaskConstraints
    ) -> List[List[InverseHypothesis]]:
        """For each train pair, generate inverse hypotheses.

        Returns a list parallel to train pairs: each element is the
        sorted list of candidate (action, score, output) for that pair.
        """
        all_hypotheses: List[List[InverseHypothesis]] = []
        for pc in constraints.pairs:
            hypos = self._predictor.inverse(
                pc.input_grid, pc.output_grid,
                max_candidates=self._max_hypo,
            )
            all_hypotheses.append(hypos)
        return all_hypotheses

    def hypothesize_consensus(
        self, constraints: TaskConstraints
    ) -> List[InverseHypothesis]:
        """If a consensus operation exists, return only those candidates
        that match it across all pairs."""
        if constraints.consensus_operation is None:
            return []

        op_name = constraints.consensus_operation.operation
        all_hypos = self.hypothesize(constraints)

        # Find the best hypothesis matching this operation for each pair
        results: List[InverseHypothesis] = []
        for hypos in all_hypos:
            matching = [h for h in hypos if h.kind == op_name]
            if matching:
                results.append(matching[0])
            else:
                return []  # consensus broken

        # All pairs have a matching hypothesis
        return results

    def hypothesize_cross_product(
        self, constraints: TaskConstraints,
        pair_index: int = 0,
    ) -> List[InverseHypothesis]:
        """Get hypotheses for a specific pair, for beam search."""
        pc = constraints.pairs[pair_index]
        return self._predictor.inverse(
            pc.input_grid, pc.output_grid,
            max_candidates=self._max_hypo,
        )
