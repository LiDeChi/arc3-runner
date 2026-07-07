from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np

type Grid = list[list[int]]
type TransformSpec = dict[str, Any]


class Transform(ABC):
    """Serializable spatial transform that can be applied to an ARC-style grid."""

    @abstractmethod
    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        """Return a transformed copy of `grid`."""

    @property
    @abstractmethod
    def complexity(self) -> int:
        """Small MDL-style cost used to rank competing hypotheses."""

    @abstractmethod
    def readable(self) -> str:
        """Human-readable mathematical form."""

    @abstractmethod
    def to_spec(self) -> TransformSpec:
        """JSON-compatible representation."""

    def equals(self, other: object) -> bool:
        return isinstance(other, Transform) and self.to_spec() == other.to_spec()


@dataclass(frozen=True)
class Identity(Transform):
    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        return _to_grid(_as_array(grid).copy())

    @property
    def complexity(self) -> int:
        return 0

    def readable(self) -> str:
        return "I"

    def to_spec(self) -> TransformSpec:
        return {"op": "identity"}


@dataclass(frozen=True)
class Translate(Transform):
    dx: int
    dy: int

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        array = _as_array(grid)
        background = _background(array, background_color)
        out = np.full_like(array, background)
        height, width = array.shape
        for y, x in np.argwhere(array != background):
            ny = int(y) + self.dy
            nx = int(x) + self.dx
            if 0 <= ny < height and 0 <= nx < width:
                out[ny, nx] = array[y, x]
        return _to_grid(out)

    @property
    def complexity(self) -> int:
        return 1

    def readable(self) -> str:
        return f"T({self.dx},{self.dy})"

    def to_spec(self) -> TransformSpec:
        return {"op": "translate", "dx": self.dx, "dy": self.dy}


@dataclass(frozen=True)
class Rotate(Transform):
    k: int
    pivot: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "k", self.k % 4)
        if self.pivot not in (None, "grid", "object"):
            raise ValueError("pivot must be None, 'grid', or 'object'")

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        array = _as_array(grid)
        if self.k == 0:
            return _to_grid(array.copy())
        if self.pivot == "object":
            background = _background(array, background_color)
            return _to_grid(_rotate_object(array, self.k, background))
        return _to_grid(np.rot90(array, -self.k))

    @property
    def complexity(self) -> int:
        return 2

    def readable(self) -> str:
        base = f"R{90 * self.k}"
        return f"{base}@{self.pivot}" if self.pivot and self.pivot != "grid" else base

    def to_spec(self) -> TransformSpec:
        spec: TransformSpec = {"op": "rotate", "k": self.k}
        if self.pivot:
            spec["pivot"] = self.pivot
        return spec


@dataclass(frozen=True)
class Mirror(Transform):
    axis: str

    def __post_init__(self) -> None:
        if self.axis not in ("x", "y", "diag"):
            raise ValueError("axis must be 'x', 'y', or 'diag'")

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        array = _as_array(grid)
        if self.axis == "x":
            return _to_grid(np.flipud(array))
        if self.axis == "y":
            return _to_grid(np.fliplr(array))
        return _to_grid(array.T)

    @property
    def complexity(self) -> int:
        return 2

    def readable(self) -> str:
        return f"M({self.axis})"

    def to_spec(self) -> TransformSpec:
        return {"op": "mirror", "axis": self.axis}


@dataclass(frozen=True)
class Scale(Transform):
    factor: int

    def __post_init__(self) -> None:
        if self.factor < 1:
            raise ValueError("factor must be >= 1")

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        array = _as_array(grid)
        return _to_grid(np.repeat(np.repeat(array, self.factor, axis=0), self.factor, axis=1))

    @property
    def complexity(self) -> int:
        return 2

    def readable(self) -> str:
        return f"S({self.factor})"

    def to_spec(self) -> TransformSpec:
        return {"op": "scale", "factor": self.factor}


@dataclass(frozen=True)
class ColorMap(Transform):
    mapping: Mapping[int, int]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mapping",
            {int(key): int(value) for key, value in self.mapping.items()},
        )

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        out = _as_array(grid).copy()
        for source, target in self.mapping.items():
            out[out == source] = target
        return _to_grid(out)

    @property
    def complexity(self) -> int:
        return 1 + len(self.mapping)

    def readable(self) -> str:
        items = ",".join(f"{source}->{target}" for source, target in sorted(self.mapping.items()))
        return f"C{{{items}}}"

    def to_spec(self) -> TransformSpec:
        return {"op": "color_map", "mapping": dict(sorted(self.mapping.items()))}


@dataclass(frozen=True)
class Toggle(Transform):
    cells: Sequence[tuple[int, int]]
    color: int = 1

    def __post_init__(self) -> None:
        object.__setattr__(self, "cells", tuple(sorted((int(x), int(y)) for x, y in self.cells)))
        object.__setattr__(self, "color", int(self.color))

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        out = _as_array(grid).copy()
        background = _background(out, background_color)
        height, width = out.shape
        for x, y in self.cells:
            if 0 <= x < width and 0 <= y < height:
                out[y, x] = self.color if out[y, x] == background else background
        return _to_grid(out)

    @property
    def complexity(self) -> int:
        return 3

    def readable(self) -> str:
        return f"G{{{len(self.cells)} cells}}"

    def to_spec(self) -> TransformSpec:
        return {
            "op": "toggle",
            "cells": [[x, y] for x, y in self.cells],
            "color": self.color,
        }


@dataclass(frozen=True)
class Compose(Transform):
    fs: Sequence[Transform]

    def __init__(self, *fs: Transform | Sequence[Transform]) -> None:
        transforms = tuple(fs[0]) if len(fs) == 1 and isinstance(fs[0], Sequence) else tuple(fs)
        if not transforms:
            raise ValueError("Compose requires at least one transform")
        if not all(isinstance(item, Transform) for item in transforms):
            raise TypeError("Compose only accepts Transform instances")
        object.__setattr__(self, "fs", transforms)

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        result: Sequence[Sequence[int]] = grid
        for transform in reversed(self.fs):
            result = transform.apply(
                result,
                background_color=background_color,
                step_index=step_index,
            )
        return _to_grid(_as_array(result))

    @property
    def complexity(self) -> int:
        return sum(transform.complexity for transform in self.fs) + max(0, len(self.fs) - 1)

    def readable(self) -> str:
        return " ∘ ".join(transform.readable() for transform in self.fs)

    def to_spec(self) -> TransformSpec:
        return {"op": "compose", "fs": [transform.to_spec() for transform in self.fs]}


@dataclass(frozen=True)
class Conditional(Transform):
    pred: Mapping[str, Any]
    if_true: Transform
    if_false: Transform

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        true_array = _as_array(
            self.if_true.apply(grid, background_color=background_color, step_index=step_index)
        )
        false_array = _as_array(
            self.if_false.apply(grid, background_color=background_color, step_index=step_index)
        )
        if true_array.shape != false_array.shape:
            raise ValueError("Conditional branches must produce grids with the same shape")
        out = false_array.copy()
        height, width = out.shape
        for y in range(height):
            for x in range(width):
                if _predicate_matches(self.pred, x, y):
                    out[y, x] = true_array[y, x]
        return _to_grid(out)

    @property
    def complexity(self) -> int:
        return 3 + self.if_true.complexity + self.if_false.complexity

    def readable(self) -> str:
        predicate = _predicate_readable(self.pred)
        return (
            f"if {predicate}: {self.if_true.readable()} "
            f"else {self.if_false.readable()}"
        )

    def to_spec(self) -> TransformSpec:
        return {
            "op": "conditional",
            "pred": dict(self.pred),
            "if_true": self.if_true.to_spec(),
            "if_false": self.if_false.to_spec(),
        }


@dataclass(frozen=True)
class Periodic(Transform):
    n: int
    f: Transform
    g: Transform

    def __post_init__(self) -> None:
        if self.n < 0:
            raise ValueError("n must be >= 0")

    def apply(
        self,
        grid: Sequence[Sequence[int]],
        *,
        background_color: int | None = None,
        step_index: int = 0,
    ) -> Grid:
        transform = self.f if step_index < self.n else self.g
        return transform.apply(grid, background_color=background_color, step_index=step_index)

    @property
    def complexity(self) -> int:
        return 3 + self.f.complexity + self.g.complexity

    def readable(self) -> str:
        return f"[{self.f.readable()}]*{self.n} then {self.g.readable()}"

    def to_spec(self) -> TransformSpec:
        return {
            "op": "periodic",
            "n": self.n,
            "f": self.f.to_spec(),
            "g": self.g.to_spec(),
        }


def from_spec(spec: Mapping[str, Any]) -> Transform:
    op = str(spec.get("op", "")).lower().replace("-", "_")
    if op in ("identity", "i"):
        return Identity()
    if op in ("translate", "t"):
        return Translate(dx=int(spec["dx"]), dy=int(spec["dy"]))
    if op in ("rotate", "r"):
        return Rotate(k=int(spec["k"]), pivot=spec.get("pivot"))
    if op in ("mirror", "m"):
        return Mirror(axis=str(spec["axis"]))
    if op in ("scale", "s"):
        return Scale(factor=int(spec.get("factor", spec.get("f"))))
    if op in ("color_map", "colormap", "c"):
        return ColorMap({int(key): int(value) for key, value in spec["mapping"].items()})
    if op in ("toggle", "g"):
        return Toggle(
            cells=[(int(cell[0]), int(cell[1])) for cell in spec["cells"]],
            color=int(spec.get("color", 1)),
        )
    if op == "compose":
        return Compose([from_spec(item) for item in spec["fs"]])
    if op == "conditional":
        true_spec = spec.get("if_true", spec.get("f"))
        false_spec = spec.get("if_false", spec.get("g"))
        if true_spec is None or false_spec is None:
            raise ValueError("Conditional spec requires if_true/if_false or f/g")
        return Conditional(
            pred=spec["pred"],
            if_true=from_spec(true_spec),
            if_false=from_spec(false_spec),
        )
    if op == "periodic":
        return Periodic(n=int(spec["n"]), f=from_spec(spec["f"]), g=from_spec(spec["g"]))
    raise ValueError(f"Unknown transform op: {spec.get('op')!r}")


def _as_array(grid: Sequence[Sequence[int]]) -> np.ndarray:
    if not grid:
        raise ValueError("grid must not be empty")
    width = len(grid[0])
    if width == 0:
        raise ValueError("grid rows must not be empty")
    if any(len(row) != width for row in grid):
        raise ValueError("grid must be rectangular")
    return np.asarray(grid, dtype=np.int16)


def _to_grid(array: np.ndarray) -> Grid:
    return array.astype(int).tolist()


def _background(array: np.ndarray, background_color: int | None) -> int:
    if background_color is not None:
        return int(background_color)
    values, counts = np.unique(array, return_counts=True)
    return int(values[int(np.argmax(counts))])


def _rotate_object(array: np.ndarray, k: int, background: int) -> np.ndarray:
    mask = array != background
    if not bool(mask.any()):
        return array.copy()

    ys, xs = np.where(mask)
    y_min, y_max = int(ys.min()), int(ys.max())
    x_min, x_max = int(xs.min()), int(xs.max())
    crop = array[y_min : y_max + 1, x_min : x_max + 1]
    rotated = np.rot90(crop, -k)

    out = array.copy()
    out[mask] = background
    target_y = round(((y_min + y_max + 1) - rotated.shape[0]) / 2)
    target_x = round(((x_min + x_max + 1) - rotated.shape[1]) / 2)
    _paste_non_background(out, rotated, target_x, target_y, background)
    return out


def _paste_non_background(
    out: np.ndarray,
    patch: np.ndarray,
    x_min: int,
    y_min: int,
    background: int,
) -> None:
    height, width = out.shape
    for py, px in np.argwhere(patch != background):
        y = y_min + int(py)
        x = x_min + int(px)
        if 0 <= y < height and 0 <= x < width:
            out[y, x] = patch[py, px]


def _predicate_matches(pred: Mapping[str, Any], x: int, y: int) -> bool:
    if "region" in pred:
        region = pred["region"]
        return (
            int(region.get("x_min", -10**9)) <= x <= int(region.get("x_max", 10**9))
            and int(region.get("y_min", -10**9)) <= y <= int(region.get("y_max", 10**9))
        )

    axis = str(pred.get("axis", "x"))
    value = x if axis == "x" else y
    threshold = int(pred["value"])
    op = str(pred.get("op", ">"))
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<":
        return value < threshold
    if op == "<=":
        return value <= threshold
    if op == "==":
        return value == threshold
    if op == "!=":
        return value != threshold
    raise ValueError(f"Unsupported predicate op: {op!r}")


def _predicate_readable(pred: Mapping[str, Any]) -> str:
    if "region" in pred:
        region = pred["region"]
        return (
            f"x in [{region.get('x_min', '-inf')},{region.get('x_max', 'inf')}] "
            f"and y in [{region.get('y_min', '-inf')},{region.get('y_max', 'inf')}]"
        )
    return f"{pred.get('axis', 'x')}{pred.get('op', '>')}{pred.get('value')}"
