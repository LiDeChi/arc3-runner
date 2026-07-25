"""
Searcher — beam search over DSL program space to find the minimal program
that is consistent with all train pairs.

Minimal Description Length (MDL) cost:
  cost(program) = program_complexity + error_on_train_pairs

Program complexity = sum of base costs for each action.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Set, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import (
    Action, ActionDSL,
    RotateCW, RotateCCW, Rotate180, FlipH, FlipV, Translate,
    Recolor, FillRect, FloodFill, Crop, Expand, CopyRegion,
    Compose, Repeat, Conditional,
)
from arc3_trainer.cognitive.diff import DiffPerception


# Base complexity cost per action type (simpler = lower)
ACTION_COST: dict = {
    "rotate_cw": 1, "rotate_ccw": 1, "rotate_180": 1,
    "flip_h": 1, "flip_v": 1,
    "translate": 2,
    "recolor": 2,
    "fill_rect": 4,
    "flood_fill": 3,
    "crop": 3,
    "expand": 3,
    "copy_region": 4,
    "overlay": 5,
    "compose": 0,  # passthrough (cost = sum of children)
    "repeat": 0,   # passthrough
    "conditional": 0,  # passthrough
}


def program_cost(program: Action) -> int:
    """Compute MDL cost of a program (action tree)."""
    if isinstance(program, Compose):
        return program_cost(program.first) + program_cost(program.second)
    elif isinstance(program, Repeat):
        return program_cost(program.action) * program.n
    elif isinstance(program, Conditional):
        return 1 + program_cost(program.then_action) + program_cost(program.else_action)
    else:
        return ACTION_COST.get(program.kind(), 5)


@dataclass
class SearchNode:
    """A node in the beam search."""
    program: Action
    cost: int = 0
    error: float = 0.0  # fraction of train cells wrong
    verified_on: int = 0  # how many train pairs this passes

    @property
    def total_cost(self) -> float:
        return self.cost + self.error * 100  # error penalty weight


class Searcher:
    """Beam-search for the minimal program consistent with train pairs."""

    def __init__(self, beam_width: int = 50, max_depth: int = 6):
        self.beam_width = beam_width
        self.max_depth = max_depth
        self._perception = DiffPerception()

    def search(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        seed_actions: Optional[List[Action]] = None,
    ) -> Optional[Action]:
        program, _ = self._search_impl(train_pairs, seed_actions)
        return program

    def search_traced(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        seed_actions: Optional[List[Action]] = None,
    ) -> Tuple[Optional[Action], List[Dict]]:
        """Like search() but also returns a trace of beam states per depth."""
        return self._search_impl(train_pairs, seed_actions, trace=True)

    def _search_impl(
        self,
        train_pairs: List[Tuple[Grid, Grid]],
        seed_actions: Optional[List[Action]] = None,
        trace: bool = False,
    ) -> Tuple[Optional[Action], List[Dict]]:
        """Search for a program consistent with all train pairs.

        Returns (best_program, trace_list).
        """
        trace_list: List[Dict] = []

        # Beam: list of SearchNode
        beam: List[SearchNode] = []

        # Seed with atomic actions that work on at least one pair
        if seed_actions:
            for action in seed_actions:
                node = self._evaluate(action, train_pairs)
                # Keep actions that either partially work or fully work on at
                # least one pair (has some correct cells).  Only filter out
                # actions that crash on every pair (error_rate == 1.0).
                if node.error < 1.0 or node.verified_on >= 1:
                    beam.append(node)
        else:
            for action in ActionDSL.all_atomic():
                node = self._evaluate(action, train_pairs)
                if node.verified_on >= 1:
                    beam.append(node)

        # If beam is empty, generate dynamic actions from colour analysis
        if not beam:
            dynamic = self._generate_dynamic_actions(train_pairs)
            for action in dynamic:
                node = self._evaluate(action, train_pairs)
                if node.verified_on >= 1:
                    beam.append(node)

        # If STILL empty, seed with ALL atomic actions
        if not beam:
            for action in ActionDSL.all_atomic():
                node = self._evaluate(action, train_pairs)
                beam.append(node)

        if not beam:
            return None, trace_list

        # Sort and trim
        beam.sort(key=lambda n: n.total_cost)
        beam = beam[:self.beam_width]

        if trace:
            trace_list.append({
                "depth": 1, "beam_size": len(beam),
                "best_cost": beam[0].cost, "best_error": beam[0].error,
            })

        best_perfect = [n for n in beam if n.error == 0.0]
        if best_perfect:
            best = min(best_perfect, key=lambda n: n.cost)
            return best.program, trace_list

        # Iterative deepening: extend programs
        for depth in range(2, self.max_depth + 1):
            new_beam: List[SearchNode] = []

            # Build composition candidates
            compose_atomics: List[Action] = list(ActionDSL.all_atomic())
            seen_signatures: set = set()
            for a in compose_atomics:
                seen_signatures.add((a.kind(), str(sorted(a.params().items()))))
            for a in self._generate_dynamic_actions(train_pairs):
                sig = (a.kind(), str(sorted(a.params().items())))
                if sig not in seen_signatures:
                    compose_atomics.append(a)
                    seen_signatures.add(sig)

            for parent in beam:
                for action in compose_atomics:
                    extended = Compose(parent.program, action)
                    node = self._evaluate(extended, train_pairs)
                    new_beam.append(node)

                    if depth >= 2 and depth % 2 == 0:
                        for n in [2, 3, 4]:
                            repeated = Repeat(parent.program, n)
                            rep_node = self._evaluate(repeated, train_pairs)
                            new_beam.append(rep_node)

            combined = beam + new_beam
            combined.sort(key=lambda n: n.total_cost)
            beam = combined[:self.beam_width]

            if trace:
                trace_list.append({
                    "depth": depth, "beam_size": len(beam),
                    "best_cost": beam[0].cost if beam else 0,
                    "best_error": beam[0].error if beam else 1.0,
                })

            best_perfect = [n for n in beam if n.error == 0.0]
            if best_perfect:
                best = min(best_perfect, key=lambda n: n.cost)
                return best.program, trace_list

            if not beam:
                break

        return (beam[0].program if beam else None), trace_list

    def _evaluate(
        self, program: Action, train_pairs: List[Tuple[Grid, Grid]]
    ) -> SearchNode:
        """Evaluate a program on all train pairs and compute cost/error."""
        total_cells = 0
        wrong_cells = 0
        verified = 0

        for inp, out in train_pairs:
            try:
                predicted = program.apply(inp)
                diff = self._perception.compare(predicted, out)
                wrong_cells += diff.pixel.changed_cells
                total_cells += diff.pixel.total_cells
                if diff.pixel.changed_cells == 0:
                    verified += 1
            except Exception:
                wrong_cells += 1
                total_cells += 1

        error_rate = wrong_cells / max(total_cells, 1)
        cost = program_cost(program)

        return SearchNode(
            program=program,
            cost=cost,
            error=error_rate,
            verified_on=verified,
        )

    def _generate_dynamic_actions(
        self, train_pairs: List[Tuple[Grid, Grid]]
    ) -> List[Action]:
        """Generate targeted atomic actions based on colour analysis."""
        actions: List[Action] = []

        # Collect all colour pairs from train data
        all_in_colors: Set[int] = set()
        all_out_colors: Set[int] = set()
        for inp, out in train_pairs:
            for _, _, v in inp.cells():
                all_in_colors.add(v)
            for _, _, v in out.cells():
                all_out_colors.add(v)

        # Recolor: any colour present in input but not output → new colour
        # Try all input→output colour mappings
        for old in all_in_colors:
            for new in all_out_colors:
                if old != new:
                    actions.append(Recolor(old, new))

        # FillRect: small rects in common colours
        for c in all_out_colors:
            for w in range(1, 4):
                for h in range(1, 4):
                    actions.append(FillRect(0, 0, w, h, c))

        # FloodFill: in common colours
        for c in all_out_colors:
            actions.append(FloodFill(0, 0, c))

        # Translate: small shifts
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx != 0 or dy != 0:
                    actions.append(Translate(dx, dy))

        return actions
