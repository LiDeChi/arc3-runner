"""
Action DSL — a typed vocabulary of atomic transformations on Grids.

Each action is callable:  action(grid) -> Grid

Actions are grouped into four categories:
  - Geometric:    rotate, flip, translate
  - Coloring:     recolor, fill_rect, flood_fill
  - Structural:   crop, expand, copy_region, overlay
  - Control:      compose, repeat, conditional

The ActionDSL class provides factory methods and serialisation.
"""
from __future__ import annotations

import abc
import itertools
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from arc3_trainer.cognitive.grid import Grid


# ---------------------------------------------------------------------------
# Action base
# ---------------------------------------------------------------------------

class Action(abc.ABC):
    """Abstract atomic or composite transformation."""

    @abc.abstractmethod
    def apply(self, grid: Grid) -> Grid:
        ...

    @abc.abstractmethod
    def params(self) -> Dict[str, Any]:
        """Return the action's parameters as a dict, for serialisation."""
        ...

    @abc.abstractmethod
    def kind(self) -> str:
        """Short string identifier, e.g. 'rotate_cw'."""
        ...

    def __call__(self, grid: Grid) -> Grid:
        return self.apply(grid)


# ---------------------------------------------------------------------------
# Geometric actions
# ---------------------------------------------------------------------------

class RotateCW(Action):
    kind_ = "rotate_cw"
    def kind(self) -> str: return self.kind_
    def apply(self, grid: Grid) -> Grid: return grid.rotate_cw()
    def params(self) -> Dict[str, Any]: return {}
    def __repr__(self) -> str: return "rotate_cw()"


class RotateCCW(Action):
    kind_ = "rotate_ccw"
    def kind(self) -> str: return self.kind_
    def apply(self, grid: Grid) -> Grid: return grid.rotate_ccw()
    def params(self) -> Dict[str, Any]: return {}
    def __repr__(self) -> str: return "rotate_ccw()"


class Rotate180(Action):
    kind_ = "rotate_180"
    def kind(self) -> str: return self.kind_
    def apply(self, grid: Grid) -> Grid: return grid.rotate_180()
    def params(self) -> Dict[str, Any]: return {}
    def __repr__(self) -> str: return "rotate_180()"


class FlipH(Action):
    kind_ = "flip_h"
    def kind(self) -> str: return self.kind_
    def apply(self, grid: Grid) -> Grid: return grid.flip_h()
    def params(self) -> Dict[str, Any]: return {}
    def __repr__(self) -> str: return "flip_h()"


class FlipV(Action):
    kind_ = "flip_v"
    def kind(self) -> str: return self.kind_
    def apply(self, grid: Grid) -> Grid: return grid.flip_v()
    def params(self) -> Dict[str, Any]: return {}
    def __repr__(self) -> str: return "flip_v()"


@dataclass(frozen=True)
class Translate(Action):
    dx: int
    dy: int
    fill: int = 0

    def kind(self) -> str: return "translate"
    def apply(self, grid: Grid) -> Grid: return grid.translate(self.dx, self.dy, self.fill)
    def params(self) -> Dict[str, Any]:
        return {"dx": self.dx, "dy": self.dy, "fill": self.fill}
    def __repr__(self) -> str:
        return f"translate(dx={self.dx}, dy={self.dy}, fill={self.fill})"


# ---------------------------------------------------------------------------
# Coloring actions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Recolor(Action):
    old: int
    new: int

    def kind(self) -> str: return "recolor"
    def apply(self, grid: Grid) -> Grid: return grid.recolor(self.old, self.new)
    def params(self) -> Dict[str, Any]:
        return {"old": self.old, "new": self.new}
    def __repr__(self) -> str:
        return f"recolor(old={self.old}, new={self.new})"


@dataclass(frozen=True)
class FillRect(Action):
    x: int
    y: int
    w: int
    h: int
    color: int

    def kind(self) -> str: return "fill_rect"
    def apply(self, grid: Grid) -> Grid: return grid.fill_rect(self.x, self.y, self.w, self.h, self.color)
    def params(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h, "color": self.color}
    def __repr__(self) -> str:
        return f"fill_rect(x={self.x}, y={self.y}, w={self.w}, h={self.h}, color={self.color})"


@dataclass(frozen=True)
class FloodFill(Action):
    x: int
    y: int
    color: int

    def kind(self) -> str: return "flood_fill"
    def apply(self, grid: Grid) -> Grid: return grid.flood_fill(self.x, self.y, self.color)
    def params(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "color": self.color}
    def __repr__(self) -> str:
        return f"flood_fill(x={self.x}, y={self.y}, color={self.color})"


# ---------------------------------------------------------------------------
# Structural actions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Crop(Action):
    x: int
    y: int
    w: int
    h: int

    def kind(self) -> str: return "crop"
    def apply(self, grid: Grid) -> Grid: return grid.crop(self.x, self.y, self.w, self.h)
    def params(self) -> Dict[str, Any]:
        return {"x": self.x, "y": self.y, "w": self.w, "h": self.h}
    def __repr__(self) -> str:
        return f"crop(x={self.x}, y={self.y}, w={self.w}, h={self.h})"


@dataclass(frozen=True)
class Expand(Action):
    new_h: int
    new_w: int
    fill: int = 0

    def kind(self) -> str: return "expand"
    def apply(self, grid: Grid) -> Grid: return grid.expand(self.new_h, self.new_w, self.fill)
    def params(self) -> Dict[str, Any]:
        return {"new_h": self.new_h, "new_w": self.new_w, "fill": self.fill}
    def __repr__(self) -> str:
        return f"expand(h={self.new_h}, w={self.new_w}, fill={self.fill})"


@dataclass(frozen=True)
class CopyRegion(Action):
    src_x: int
    src_y: int
    w: int
    h: int
    dst_x: int
    dst_y: int

    def kind(self) -> str: return "copy_region"
    def apply(self, grid: Grid) -> Grid:
        return grid.copy_region(self.src_x, self.src_y, self.w, self.h, self.dst_x, self.dst_y)
    def params(self) -> Dict[str, Any]:
        return {"src_x": self.src_x, "src_y": self.src_y, "w": self.w, "h": self.h,
                "dst_x": self.dst_x, "dst_y": self.dst_y}
    def __repr__(self) -> str:
        return f"copy_region({self.src_x},{self.src_y}→{self.dst_x},{self.dst_y} size={self.w}×{self.h})"


@dataclass(frozen=True)
class Overlay(Action):
    other: Grid  # the grid to overlay (same size required at apply-time)
    x: int = 0
    y: int = 0
    mask_color: Optional[int] = None

    def kind(self) -> str: return "overlay"
    def apply(self, grid: Grid) -> Grid:
        # We need overlay to happen at (x,y); we use crop+overlay+paste
        h = min(self.other.height, grid.height - self.y)
        w = min(self.other.width, grid.width - self.x)
        if h <= 0 or w <= 0:
            return grid.copy()
        # Overlay is tricky since overlay() overlays at (0,0). We use a different approach:
        # crop the relevant region, overlay, then fill_rect
        arr = grid.data
        sub = Grid(arr[self.y:self.y+h, self.x:self.x+w].copy())
        overlaid = sub.overlay(self.other, mask_color=self.mask_color)
        arr[self.y:self.y+h, self.x:self.x+w] = overlaid.data
        return Grid(arr)

    def params(self) -> Dict[str, Any]:
        return {"other_shape": list(self.other.shape), "x": self.x, "y": self.y,
                "mask_color": self.mask_color}
    def __repr__(self) -> str:
        return f"overlay({self.other.height}×{self.other.width} at ({self.x},{self.y}), mask={self.mask_color})"


# ---------------------------------------------------------------------------
# Control-flow composite actions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Compose(Action):
    """Sequential composition: apply *first*, then *second*."""
    first: Action
    second: Action

    def kind(self) -> str: return "compose"
    def apply(self, grid: Grid) -> Grid:
        return self.second.apply(self.first.apply(grid))

    def params(self) -> Dict[str, Any]:
        return {"first": self.first.params(), "second": self.second.params(),
                "first_kind": self.first.kind(), "second_kind": self.second.kind()}

    def __repr__(self) -> str:
        return f"compose({self.first!r} ; {self.second!r})"


@dataclass(frozen=True)
class Repeat(Action):
    """Apply *action* *n* times consecutively."""
    action: Action
    n: int

    def kind(self) -> str: return "repeat"
    def apply(self, grid: Grid) -> Grid:
        g = grid
        for _ in range(self.n):
            g = self.action.apply(g)
        return g

    def params(self) -> Dict[str, Any]:
        return {"action_kind": self.action.kind(), "action_params": self.action.params(),
                "n": self.n}

    def __repr__(self) -> str:
        return f"repeat({self.action!r} ; {self.n}x)"


@dataclass(frozen=True)
class Conditional(Action):
    """If *condition(grid)* is truthy, apply *then_action*, else *else_action*."""
    condition: str  # symbolic name of a condition (e.g. "has_blue", "width_gt_height")
    then_action: Action
    else_action: Action

    def kind(self) -> str: return "conditional"
    def apply(self, grid: Grid) -> Grid:
        cond = self._evaluate_condition(grid)
        return self.then_action.apply(grid) if cond else self.else_action.apply(grid)

    def _evaluate_condition(self, grid: Grid) -> bool:
        if self.condition == "has_color_1":
            return any(v == 1 for _, _, v in grid.cells())
        elif self.condition == "has_color_2":
            return any(v == 2 for _, _, v in grid.cells())
        elif self.condition == "has_color_3":
            return any(v == 3 for _, _, v in grid.cells())
        elif self.condition == "has_color_4":
            return any(v == 4 for _, _, v in grid.cells())
        elif self.condition == "has_color_5":
            return any(v == 5 for _, _, v in grid.cells())
        elif self.condition == "width_gt_height":
            return grid.width > grid.height
        elif self.condition == "height_gt_width":
            return grid.height > grid.width
        elif self.condition == "width_eq_height":
            return grid.width == grid.height
        elif self.condition == "is_symmetric_h":
            return bool(np.array_equal(grid._data, np.fliplr(grid._data)))
        elif self.condition == "is_symmetric_v":
            return bool(np.array_equal(grid._data, np.flipud(grid._data)))
        return False

    def params(self) -> Dict[str, Any]:
        return {"condition": self.condition,
                "then": self.then_action.params(), "else": self.else_action.params(),
                "then_kind": self.then_action.kind(), "else_kind": self.else_action.kind()}

    def __repr__(self) -> str:
        return f"if {self.condition} then {self.then_action!r} else {self.else_action!r}"


# ---------------------------------------------------------------------------
# DSL factory
# ---------------------------------------------------------------------------

import numpy as np  # noqa: E402 (needed inside Conditional)


_ACTION_KINDS: Dict[str, type] = {
    "rotate_cw": RotateCW,
    "rotate_ccw": RotateCCW,
    "rotate_180": Rotate180,
    "flip_h": FlipH,
    "flip_v": FlipV,
    "translate": Translate,
    "recolor": Recolor,
    "fill_rect": FillRect,
    "flood_fill": FloodFill,
    "crop": Crop,
    "expand": Expand,
    "copy_region": CopyRegion,
    "overlay": Overlay,
    "compose": Compose,
    "repeat": Repeat,
    "conditional": Conditional,
}


class ActionDSL:
    """Factory for building Action instances."""

    @staticmethod
    def all_atomic() -> List[Action]:
        """Return one instance of every atomic action (with default params)."""
        return [
            RotateCW(), RotateCCW(), Rotate180(),
            FlipH(), FlipV(),
            Translate(1, 0), Translate(0, 1), Translate(-1, 0), Translate(0, -1),
            Recolor(1, 2), Recolor(2, 3), Recolor(3, 4), Recolor(4, 5),
            Recolor(5, 6), Recolor(6, 7), Recolor(7, 8), Recolor(8, 9),
            FillRect(0, 0, 1, 1, 0),
            FloodFill(0, 0, 0),
            Crop(0, 0, 1, 1),
            Expand(3, 3),
            CopyRegion(0, 0, 1, 1, 0, 0),
        ]

    @staticmethod
    def action_count() -> int:
        return len(_ACTION_KINDS)

    @staticmethod
    def from_params(kind: str, params: Dict[str, Any]) -> Action:
        """Reconstruct an action from a (kind, params) pair."""
        cls = _ACTION_KINDS.get(kind)
        if cls is None:
            raise ValueError(f"Unknown action kind: {kind}")
        if kind == "compose":
            return Compose(
                first=ActionDSL.from_params(params["first_kind"], params["first"]),
                second=ActionDSL.from_params(params["second_kind"], params["second"]),
            )
        if kind == "repeat":
            return Repeat(
                action=ActionDSL.from_params(params["action_kind"], params["action_params"]),
                n=params["n"],
            )
        if kind == "conditional":
            return Conditional(
                condition=params["condition"],
                then_action=ActionDSL.from_params(params["then_kind"], params["then"]),
                else_action=ActionDSL.from_params(params["else_kind"], params["else"]),
            )
        if kind == "overlay":
            # overlay's 'other' grid is reconstructed from shape — the actual
            # grid content needs special handling
            raise NotImplementedError("overlay serialisation requires grid content")
        # Atomic actions: construct from params
        # All frozen dataclass constructors use the field names
        try:
            return cls(**params)  # type: ignore[operator]
        except TypeError:
            # Some ctors take no args
            return cls()  # type: ignore[operator]
