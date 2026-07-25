"""
DiffPerception — compare two Grid states and produce structured descriptions
of what changed, at both pixel-level and semantic-level.

pixel_diff:  binary mask + count of differing cells
semantic_diff: classifies the transformation into a structured description
               (geometric, coloring, structural change categories)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import (
    Action,
    RotateCW, RotateCCW, Rotate180, FlipH, FlipV, Translate,
    Recolor,
    Crop, Expand,
)


@dataclass
class PixelDiff:
    """Pixel-level differences between two grids."""
    total_cells: int
    changed_cells: int
    change_ratio: float
    diff_grid: Grid  # binary: 1 where diff, 0 same

    # Per-colour statistics
    colours_added: Dict[int, int] = field(default_factory=dict)   # colour → count of new cells
    colours_removed: Dict[int, int] = field(default_factory=dict)  # colour → count of removed cells


@dataclass
class SemanticDiff:
    """High-level description of the transformation.

    A task may involve multiple operations; this captures the most
    likely single operation for rapid hypothesis pruning.
    """
    category: str  # "geometric" | "coloring" | "structural" | "composite" | "unknown"
    operation: str  # "rotate_cw" | "recolor" | "crop" | etc.
    confidence: float  # 0..1

    # Specific parameters inferred where possible
    params: Dict[str, int | str] = field(default_factory=dict)


@dataclass
class DiffResult:
    """Complete diff between two grids."""
    pixel: PixelDiff
    semantics: List[SemanticDiff]  # sorted by confidence descending


class DiffPerception:
    """Stateless comparator between two Grid states."""

    def compare(self, before: Grid, after: Grid) -> DiffResult:
        """Full structured comparison."""
        pixel = self._pixel_diff(before, after)
        semantics = self._semantic_diffs(before, after)
        return DiffResult(pixel=pixel, semantics=semantics)

    # ------------------------------------------------------------------
    # Pixel-level
    # ------------------------------------------------------------------

    def _pixel_diff(self, before: Grid, after: Grid) -> PixelDiff:
        max_h = max(before.height, after.height)
        max_w = max(before.width, after.width)
        b = before._expand_to(max_h, max_w)
        a = after._expand_to(max_h, max_w)

        diff_arr = (b != a).astype(np.int8)
        diff_grid = Grid(diff_arr)
        changed = int(np.sum(diff_arr))
        total = max_h * max_w

        # colour statistics: what colours appeared/disappeared
        b_flat = b.flatten()
        a_flat = a.flatten()
        added: Dict[int, int] = {}
        removed: Dict[int, int] = {}
        for i in range(len(b_flat)):
            if b_flat[i] != a_flat[i]:
                if a_flat[i] != -1:
                    added[int(a_flat[i])] = added.get(int(a_flat[i]), 0) + 1
                if b_flat[i] != -1:
                    removed[int(b_flat[i])] = removed.get(int(b_flat[i]), 0) + 1

        return PixelDiff(
            total_cells=total,
            changed_cells=changed,
            change_ratio=changed / max(total, 1),
            diff_grid=diff_grid,
            colours_added=added,
            colours_removed=removed,
        )

    # ------------------------------------------------------------------
    # Semantic-level — try several hypotheses and rank
    # ------------------------------------------------------------------

    def _semantic_diffs(self, before: Grid, after: Grid) -> List[SemanticDiff]:
        candidates: List[SemanticDiff] = []

        # 1) Try geometric transformations
        candidates.extend(self._check_geometric(before, after))
        # 2) Try colour-only changes
        candidates.extend(self._check_recolor(before, after))
        # 3) Try crop / expand
        candidates.extend(self._check_crop_expand(before, after))
        # 4) Translation
        candidates.extend(self._check_translation(before, after))

        candidates.sort(key=lambda x: x.confidence, reverse=True)
        return candidates

    def _matches(self, before: Grid, after: Grid, action: Action) -> float:
        """Return 1.0 if action(before) == after, else 0.0."""
        try:
            result = action.apply(before)
            return 1.0 if result.equals(after) else 0.0
        except Exception:
            return 0.0

    def _check_geometric(self, before: Grid, after: Grid) -> List[SemanticDiff]:
        results: List[SemanticDiff] = []
        checks = [
            ("rotate_cw", RotateCW()),
            ("rotate_ccw", RotateCCW()),
            ("rotate_180", Rotate180()),
            ("flip_h", FlipH()),
            ("flip_v", FlipV()),
        ]
        for name, action in checks:
            c = self._matches(before, after, action)
            if c > 0:
                results.append(SemanticDiff("geometric", name, c))
        return results

    def _check_recolor(self, before: Grid, after: Grid) -> List[SemanticDiff]:
        """If only colours changed (possibly at same positions)."""
        if before.shape != after.shape:
            return []

        # Check if it's a simple global recolour
        results: List[SemanticDiff] = []
        for old in range(10):
            for new in range(10):
                if old == new:
                    continue
                c = self._matches(before, after, Recolor(old, new))
                if c > 0:
                    results.append(SemanticDiff("coloring", "recolor", c,
                                                {"old": old, "new": new}))
        return results

    def _check_crop_expand(self, before: Grid, after: Grid) -> List[SemanticDiff]:
        """Check if after is a crop of before, or after is an expansion of before."""
        results: List[SemanticDiff] = []

        # Crop: after smaller, top-left corner check
        if before.height > after.height or before.width > after.width:
            # check if after appears as a sub-region of before
            for x in range(before.width - after.width + 1):
                for y in range(before.height - after.height + 1):
                    region = before.crop(x, y, after.width, after.height)
                    if region.equals(after):
                        results.append(SemanticDiff("structural", "crop", 1.0,
                                                    {"x": x, "y": y, "w": after.width, "h": after.height}))
                        return results  # exact match

        # Expand: after larger, top-left content matches
        if before.height <= after.height and before.width <= after.width:
            region = after.crop(0, 0, before.width, before.height)
            if region.equals(before):
                results.append(SemanticDiff("structural", "expand", 1.0,
                                            {"new_h": after.height, "new_w": after.width}))
        return results

    def _check_translation(self, before: Grid, after: Grid) -> List[SemanticDiff]:
        """Check if after = translate(before, dx, dy) for some dx, dy in [-5..5]."""
        results: List[SemanticDiff] = []
        for dx in range(-5, 6):
            for dy in range(-5, 6):
                if dx == 0 and dy == 0:
                    continue
                c = self._matches(before, after, Translate(dx, dy))
                if c > 0:
                    results.append(SemanticDiff("geometric", "translate", 1.0,
                                                {"dx": dx, "dy": dy}))
                    return results
        return results

    # ------------------------------------------------------------------
    # Convenience for multiple pairs
    # ------------------------------------------------------------------

    def compare_pairs(
        self, pairs: List[Tuple[Grid, Grid]]
    ) -> List[DiffResult]:
        return [self.compare(b, a) for b, a in pairs]

    def consensus_operation(
        self, results: List[DiffResult]
    ) -> Optional[SemanticDiff]:
        """If all pairs have the same top semantic diff, return it."""
        if not results:
            return None
        top = [r.semantics[0] if r.semantics else None for r in results]
        if any(t is None for t in top):
            return None
        # Check they all describe the same operation
        op = top[0].operation  # type: ignore[index]
        if all(t.operation == op for t in top):  # type: ignore[union-attr]
            return top[0]
        return None
