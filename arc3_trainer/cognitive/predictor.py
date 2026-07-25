"""
Predictor — forward execution and inverse hypothesis generation.

Forward:  state × action → output state
Inverse:  state × target → candidate actions that could transform state into target

The inverse mode is the core mechanism for the agent's "imagination" —
given a starting state and a desired end state, what actions might account
for the change?
"""
from __future__ import annotations

import numpy as np

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import (
    Action, ActionDSL, RotateCW, RotateCCW, Rotate180, FlipH, FlipV,
    Translate, Recolor, FillRect, FloodFill, Crop, Expand,
    CopyRegion, Overlay, Compose, Repeat, Conditional,
)
from arc3_trainer.cognitive.diff import DiffPerception, SemanticDiff


@dataclass
class InverseHypothesis:
    """A candidate action + its associated grid that explains before→after."""
    action: Action
    output: Grid
    score: float  # 0..1 how well this explains the transition

    kind: str = ""
    params: Dict = field(default_factory=dict)


class Predictor:
    """Connects actions and grids via forward/inverse reasoning."""

    def __init__(self):
        self._perception = DiffPerception()

    # ------------------------------------------------------------------
    # Forward: deterministic execution
    # ------------------------------------------------------------------

    def forward(self, grid: Grid, action: Action) -> Grid:
        """Apply action to grid and return the result."""
        return action.apply(grid)

    def forward_chain(self, grid: Grid, actions: List[Action]) -> Grid:
        """Apply multiple actions in sequence."""
        g = grid
        for a in actions:
            g = a.apply(g)
        return g

    # ------------------------------------------------------------------
    # Inverse: generate candidate actions that explain before→after
    # ------------------------------------------------------------------

    def inverse(
        self,
        before: Grid,
        after: Grid,
        max_candidates: int = 50,
    ) -> List[InverseHypothesis]:
        """Given before and after, hypothesise actions that might explain the change.

        Uses the semantic diff as a fast path, then brute-force searches
        simple atomic actions.
        """
        candidates: List[InverseHypothesis] = []

        # --- fast path: leverage DiffPerception ---
        diff_result = self._perception.compare(before, after)
        for sem in diff_result.semantics:
            action = self._semantic_to_action(sem, before, after)
            if action is not None:
                output = action.apply(before)
                exact = 1.0 if output.equals(after) else 0.0
                candidates.append(InverseHypothesis(
                    action=action, output=output, score=exact,
                    kind=sem.operation, params=sem.params,
                ))

        # --- search all atomic actions ---
        if len(candidates) == 0 or all(c.score < 0.5 for c in candidates):
            # Collect colours for dynamic action generation
            before_colours = {int(v) for _, _, v in before.cells()}
            after_colours = {int(v) for _, _, v in after.cells()}

            # Build a richer set of actions: all atomics + dynamic recolor pairs
            search_actions: List[Action] = list(ActionDSL.all_atomic())
            for old in before_colours:
                for new in after_colours:
                    if old != new and not any(
                        isinstance(a, Recolor) and a.old == old and a.new == new
                        for a in search_actions
                    ):
                        search_actions.append(Recolor(old, new))

            for action in search_actions:
                try:
                    output = action.apply(before)
                    if output.shape == after.shape:
                        if output.equals(after):
                            score = 1.0
                        else:
                            # Same shape, not exact — use partial match
                            score = self._partial_match_score(output, after)
                    else:
                        # Different shapes — use partial match
                        score = self._partial_match_score(output, after)
                except Exception:
                    continue
                if score > 0:
                    candidates.append(InverseHypothesis(
                        action=action, output=output, score=score,
                        kind=action.kind(), params=action.params(),
                    ))

        # --- deduplicate and sort ---
        seen: set[str] = set()
        unique: List[InverseHypothesis] = []
        for c in sorted(candidates, key=lambda x: -x.score):
            key = f"{c.kind}:{c.params}"
            if key not in seen:
                seen.add(key)
                unique.append(c)
                if len(unique) >= max_candidates:
                    break

        return unique

    def _semantic_to_action(
        self, sem: SemanticDiff, before: Grid, after: Grid
    ) -> Optional[Action]:
        """Convert a SemanticDiff back into an Action if possible."""
        from arc3_trainer.cognitive.actions import ActionDSL as DSL
        try:
            return DSL.from_params(sem.operation, dict(sem.params))  # type: ignore
        except (ValueError, NotImplementedError):
            return None

    def _partial_match_score(self, candidate: Grid, target: Grid) -> float:
        """Fraction of equal cells, resizing to the larger grid."""
        max_h = max(candidate.height, target.height)
        max_w = max(candidate.width, target.width)
        c = candidate._expand_to(max_h, max_w)
        t = target._expand_to(max_h, max_w)
        equal = int(np.sum(c == t))
        total = max_h * max_w
        return equal / max(total, 1)

    # ------------------------------------------------------------------
    # Imagination: what-if exploration
    # ------------------------------------------------------------------

    def imagine(
        self,
        grid: Grid,
        action_filters: Optional[List[Callable[[Action], bool]]] = None,
        max_actions: int = 100,
    ) -> List[Tuple[Action, Grid]]:
        """Generate possible next states from *grid* by applying every atomic
        action.  Optionally filter actions."""
        results: List[Tuple[Action, Grid]] = []
        for action in ActionDSL.all_atomic():
            try:
                if action_filters and not any(f(action) for f in action_filters):
                    continue
                output = action.apply(grid)
                results.append((action, output))
                if len(results) >= max_actions:
                    break
            except Exception:
                continue
        return results

    def imagine_toward(
        self,
        grid: Grid,
        target: Grid,
        max_combinations: int = 200,
    ) -> List[List[InverseHypothesis]]:
        """Try to explain before→after by searching 2-step action chains.

        Returns a list per chain depth.
        """
        # Single-step
        single = self.inverse(grid, target, max_candidates=max_combinations)
        if any(h.score == 1.0 for h in single):
            return [single]

        # Two-step: for each atomic action, see what additional action
        # would turn the intermediate into target
        two_step: List[List[InverseHypothesis]] = []
        for action in ActionDSL.all_atomic():
            try:
                mid = action.apply(grid)
                second_steps = self.inverse(mid, target, max_candidates=5)
                for s in second_steps:
                    chain = [
                        InverseHypothesis(action, mid, 0.5, action.kind(), action.params()),
                        s,
                    ]
                    combined = Compose(action, s.action)
                    final = combined.apply(grid)
                    overall_score = 1.0 if final.equals(target) else 0.0
                    chain[0].score = overall_score
                    chain[1].score = overall_score
                    two_step.append(chain)
                    if len(two_step) >= max_combinations // 2:
                        break
            except Exception:
                continue

        two_step.sort(key=lambda chain: -chain[0].score)
        return [single] + two_step[:max_combinations]
