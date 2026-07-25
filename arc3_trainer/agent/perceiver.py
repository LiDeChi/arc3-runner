"""
Perceiver — observe train pairs and extract constraints.

For each train pair (input → output), the Perceiver uses DiffPerception
to derive what changed. The output is a set of constraints that any
candidate program must satisfy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.diff import DiffPerception, DiffResult, SemanticDiff
from arc3_trainer.cognitive.actions import Action


@dataclass
class PairConstraint:
    """Constraints extracted from a single (input → output) pair."""
    pair_index: int
    input_grid: Grid
    output_grid: Grid
    diff_result: DiffResult
    shape_changed: bool
    colours_present_in: Set[int]
    colours_present_out: Set[int]
    colours_added: Set[int]
    colours_removed: Set[int]

    # If all semantic diffs point to the same operation, this is non-None
    top_operation: Optional[SemanticDiff] = None


@dataclass
class TaskConstraints:
    """Consolidated constraints across all train pairs."""
    pairs: List[PairConstraint]
    shape_changed: bool  # True if any pair changed grid shape
    colours_used: Set[int]  # all colours appearing anywhere
    colours_in_output_only: Set[int]
    colours_in_input_only: Set[int]

    # Consensus operation across all pairs (if one exists)
    consensus_operation: Optional[SemanticDiff] = None

    # All unique operations seen across all pairs
    all_operations: List[str] = field(default_factory=list)


class Perceiver:
    """Analyse train pairs and produce structured constraints."""

    def __init__(self):
        self._diff = DiffPerception()

    def perceive(self, train_pairs: List[Tuple[Grid, Grid]]) -> TaskConstraints:
        """Full constraint extraction from all train pairs."""
        constraints: List[PairConstraint] = []
        all_colours: Set[int] = set()

        for i, (inp, out) in enumerate(train_pairs):
            diff_r = self._diff.compare(inp, out)

            in_colours = {v for _, _, v in inp.cells()}
            out_colours = {v for _, _, v in out.cells()}
            all_colours |= in_colours | out_colours

            pc = PairConstraint(
                pair_index=i,
                input_grid=inp,
                output_grid=out,
                diff_result=diff_r,
                shape_changed=(inp.shape != out.shape),
                colours_present_in=in_colours,
                colours_present_out=out_colours,
                colours_added=set(diff_r.pixel.colours_added.keys()),
                colours_removed=set(diff_r.pixel.colours_removed.keys()),
                top_operation=diff_r.semantics[0] if diff_r.semantics else None,
            )
            constraints.append(pc)

        # Compute cross-pair consensus
        shape_changed_any = any(pc.shape_changed for pc in constraints)

        all_in = set()
        all_out = set()
        for pc in constraints:
            all_in |= pc.colours_present_in
            all_out |= pc.colours_present_out

        consensus = self._diff.consensus_operation([pc.diff_result for pc in constraints])

        all_ops: List[str] = []
        for pc in constraints:
            for sem in pc.diff_result.semantics[:3]:  # top 3 per pair
                all_ops.append(sem.operation)

        return TaskConstraints(
            pairs=constraints,
            shape_changed=shape_changed_any,
            colours_used=all_colours,
            colours_in_output_only=all_out - all_in,
            colours_in_input_only=all_in - all_out,
            consensus_operation=consensus,
            all_operations=all_ops,
        )
