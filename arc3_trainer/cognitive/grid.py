"""
Grid — the core world state representation for ARC tasks.

A Grid is a 2D rectangular matrix of integers 0..9, size 1x1 up to 30x30.
"""
from __future__ import annotations

import copy
from typing import Iterator, Sequence, Tuple

import numpy as np


class Grid:
    """Immutable-ish 2D grid of ints 0–9.  Immutability is enforced by returning
    new Grid instances from every transformation; internal storage is numpy."""

    __slots__ = ("_data",)

    # --- construction -------------------------------------------------

    def __init__(self, data: np.ndarray | Sequence[Sequence[int]]) -> None:
        arr = np.asarray(data, dtype=np.int8)
        if arr.ndim != 2:
            raise ValueError(f"Grid must be 2D, got shape {arr.shape}")
        h, w = arr.shape
        if h < 1 or h > 30 or w < 1 or w > 30:
            raise ValueError(f"Grid size {h}x{w} outside [1..30]×[1..30]")
        if not np.all((arr >= 0) & (arr <= 9)):
            raise ValueError("All cells must be 0–9")
        self._data = arr

    @classmethod
    def zeros(cls, height: int, width: int) -> "Grid":
        return cls(np.zeros((height, width), dtype=np.int8))

    @classmethod
    def full(cls, height: int, width: int, value: int) -> "Grid":
        return cls(np.full((height, width), value, dtype=np.int8))

    # --- properties ---------------------------------------------------

    @property
    def height(self) -> int:
        return self._data.shape[0]

    @property
    def width(self) -> int:
        return self._data.shape[1]

    @property
    def shape(self) -> Tuple[int, int]:
        return self._data.shape  # type: ignore[return-value]

    @property
    def data(self) -> np.ndarray:
        """Read-only view of underlying data (copy)."""
        return self._data.copy()

    # --- access -------------------------------------------------------

    def __getitem__(self, key) -> int | np.ndarray:
        return self._data[key]  # type: ignore[index]

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Grid):
            return NotImplemented
        return bool(np.array_equal(self._data, other._data))

    def __hash__(self) -> int:
        return hash(self._data.tobytes())

    def __repr__(self) -> str:
        return f"Grid(shape={self.height}x{self.width})"

    def as_text(self) -> str:
        """Human-readable text representation (digits)."""
        return "\n".join(
            "".join(str(int(c)) for c in row) for row in self._data
        )

    def as_list(self) -> list[list[int]]:
        """Nested-list representation for JSON serialisation."""
        return self._data.tolist()

    # --- transformations (all return new Grid) ------------------------

    def copy(self) -> "Grid":
        return Grid(self._data.copy())

    def crop(self, x: int, y: int, w: int, h: int) -> "Grid":
        """Crop a rectangular region.  (x,y) is top-left (col, row)."""
        if x < 0 or y < 0 or x + w > self.width or y + h > self.height:
            raise ValueError("Crop region out of bounds")
        return Grid(self._data[y : y + h, x : x + w].copy())

    def pad(
        self, top: int = 0, bottom: int = 0, left: int = 0, right: int = 0,
        fill: int = 0,
    ) -> "Grid":
        """Pad the grid symmetrically or asymmetrically with *fill* colour."""
        new_h = self.height + top + bottom
        new_w = self.width + left + right
        if new_h > 30 or new_w > 30:
            raise ValueError(f"Padded size {new_h}x{new_w} exceeds 30x30")
        out = np.full((new_h, new_w), fill, dtype=np.int8)
        out[top : top + self.height, left : left + self.width] = self._data
        return Grid(out)

    def expand(self, new_h: int, new_w: int, fill: int = 0) -> "Grid":
        """Expand to *new_h*×*new_w*, placing original content at top-left."""
        if new_h > 30 or new_w > 30:
            raise ValueError(f"Size {new_h}x{new_w} exceeds 30x30")
        if new_h < self.height or new_w < self.width:
            raise ValueError("expand only supports growing, not shrinking")
        out = np.full((new_h, new_w), fill, dtype=np.int8)
        out[: self.height, : self.width] = self._data
        return Grid(out)

    def rotate_cw(self) -> "Grid":
        """Rotate 90° clockwise."""
        return Grid(np.rot90(self._data, k=-1))

    def rotate_ccw(self) -> "Grid":
        """Rotate 90° counter-clockwise."""
        return Grid(np.rot90(self._data, k=1))

    def rotate_180(self) -> "Grid":
        return Grid(np.rot90(self._data, k=2))

    def flip_h(self) -> "Grid":
        """Horizontal flip (left-right)."""
        return Grid(np.fliplr(self._data))

    def flip_v(self) -> "Grid":
        """Vertical flip (up-down)."""
        return Grid(np.flipud(self._data))

    def translate(self, dx: int, dy: int, fill: int = 0) -> "Grid":
        """Shift by (dx, dy). dx=col, dy=row.  Vacated cells get *fill*."""
        out = np.full_like(self._data, fill)
        src_x1 = max(0, -dx)
        src_y1 = max(0, -dy)
        src_x2 = min(self.width, self.width - dx)
        src_y2 = min(self.height, self.height - dy)
        # Guard against negative ranges (dx > width or dy > height)
        if src_x1 < src_x2 and src_y1 < src_y2:
            dst_x1 = max(0, dx)
            dst_y1 = max(0, dy)
            dst_x2 = dst_x1 + (src_x2 - src_x1)
            dst_y2 = dst_y1 + (src_y2 - src_y1)
            out[dst_y1:dst_y2, dst_x1:dst_x2] = self._data[src_y1:src_y2, src_x1:src_x2]
        return Grid(out)

    # --- colour operations --------------------------------------------

    def recolor(self, old: int, new: int) -> "Grid":
        """Replace every cell == *old* with *new*."""
        arr = self._data.copy()
        arr[arr == old] = new
        return Grid(arr)

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> "Grid":
        """Fill a rectangle region with *color*."""
        if not (0 <= x and 0 <= y and x + w <= self.width and y + h <= self.height):
            raise ValueError("fill_rect out of bounds")
        arr = self._data.copy()
        arr[y : y + h, x : x + w] = color
        return Grid(arr)

    def flood_fill(self, x: int, y: int, color: int) -> "Grid":
        """Flood-fill the connected component at (x,y) with *color*."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise ValueError("flood_fill seed out of bounds")
        target = int(self._data[y, x])
        if target == color:
            return self.copy()
        arr = self._data.copy()
        stack = [(x, y)]
        visited = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            if 0 <= cx < self.width and 0 <= cy < self.height and arr[cy, cx] == target:
                arr[cy, cx] = color
                stack.extend([(cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)])
        return Grid(arr)

    # --- region ops ---------------------------------------------------

    def copy_region(
        self, src_x: int, src_y: int, w: int, h: int,
        dst_x: int, dst_y: int,
    ) -> "Grid":
        """Copy rectangle from src to dst within the same grid."""
        if not (0 <= src_x and src_y >= 0 and src_x + w <= self.width and src_y + h <= self.height):
            raise ValueError("copy_region source out of bounds")
        if not (0 <= dst_x and dst_y >= 0 and dst_x + w <= self.width and dst_y + h <= self.height):
            raise ValueError("copy_region destination out of bounds")
        arr = self._data.copy()
        arr[dst_y : dst_y + h, dst_x : dst_x + w] = arr[src_y : src_y + h, src_x : src_x + w]
        return Grid(arr)

    def overlay(self, other: "Grid", mask_color: int | None = None) -> "Grid":
        """Overlay *other* on top of self at (0,0).  If *mask_color* is given,
        only those cells of *other* matching *mask_color* are transparent."""
        h = min(self.height, other.height)
        w = min(self.width, other.width)
        arr = self._data.copy()
        if mask_color is None:
            arr[:h, :w] = other._data[:h, :w]
        else:
            mask = other._data[:h, :w] != mask_color
            arr[:h, :w][mask] = other._data[:h, :w][mask]
        return Grid(arr)

    # --- comparison helpers -------------------------------------------

    def equals(self, other: "Grid") -> bool:
        return self == other

    def diff_mask(self, other: "Grid") -> "Grid":
        """Binary grid: 1 where self and other differ, 0 elsewhere.
        Resized to max of both dims."""
        h = max(self.height, other.height)
        w = max(self.width, other.width)
        a = self._expand_to(h, w)
        b = other._expand_to(h, w)
        return Grid((a != b).astype(np.int8))

    def count_diff(self, other: "Grid") -> int:
        """Number of differing cells."""
        dm = self.diff_mask(other)
        return int(np.sum(dm._data))

    def _expand_to(self, h: int, w: int) -> np.ndarray:
        """Expand internal data to h×w, padding with -1 on right/bottom."""
        out = np.full((h, w), -1, dtype=np.int16)
        out[: self.height, : self.width] = self._data
        return out

    # --- iteration ----------------------------------------------------

    def cells(self) -> Iterator[Tuple[int, int, int]]:
        """Yield (x, y, value) for every cell."""
        for y in range(self.height):
            for x in range(self.width):
                yield x, y, int(self._data[y, x])
