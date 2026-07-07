from __future__ import annotations

from typing import Any

import numpy as np

from server.hypothesis import HypothesisTracker, TransformHypothesis


def imagine_action(
    frame: list[list[int]],
    action_id: int,
    tracker: HypothesisTracker,
    *,
    step_index: int,
    goal_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    top = tracker.top(action_id)
    predicted = tracker.predict(action_id, frame, step_index=step_index)
    changed = _changed_cells(frame, predicted)
    confidence = top.confidence if top else 0.0
    readable = top.transform.readable() if top else "unfit"
    goal_progress = _goal_progress(top, goal_hint, step_index)
    return {
        "action_id": action_id,
        "readable": readable,
        "confidence": round(confidence, 4),
        "predicted_changed_cells": changed,
        "goal_progress": round(goal_progress, 4),
        "utility": round(_utility(top, changed, goal_progress), 4),
        "children": [],
    }


def plan_one_step(
    actions: list[Any],
    frame: list[list[int]],
    tracker: HypothesisTracker,
    *,
    step_index: int,
    confidence_threshold: float = 0.5,
    goal_hint: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = [
        imagine_action(
            frame,
            int(action.value),
            tracker,
            step_index=step_index,
            goal_hint=goal_hint,
        )
        for action in actions
    ]
    ranked = sorted(nodes, key=lambda node: (node["utility"], node["confidence"]), reverse=True)
    best = ranked[0] if ranked else None
    mode = "exploit" if best and float(best["confidence"]) >= confidence_threshold else "probe"
    return {
        "mode": mode,
        "threshold": confidence_threshold,
        "selected_action_id": best["action_id"] if best and mode == "exploit" else None,
        "nodes": ranked,
    }


def _utility(
    hypothesis: TransformHypothesis | None,
    predicted_changed_cells: int,
    goal_progress: float,
) -> float:
    if hypothesis is None:
        return 0.0
    movement_bonus = min(1.0, predicted_changed_cells / 64)
    progress_bonus = max(-0.5, min(1.0, goal_progress))
    return (
        hypothesis.confidence * (1.0 + movement_bonus + 2.0 * progress_bonus)
        - 0.05 * hypothesis.transform.complexity
    )


def _changed_cells(before: list[list[int]], after: list[list[int]]) -> int:
    before_array = np.asarray(before, dtype=np.int16)
    after_array = np.asarray(after, dtype=np.int16)
    if before_array.shape != after_array.shape:
        return int(after_array.size)
    return int(np.count_nonzero(before_array != after_array))


def _goal_progress(
    hypothesis: TransformHypothesis | None,
    goal_hint: dict[str, Any] | None,
    step_index: int,
) -> float:
    if hypothesis is None or not goal_hint:
        return 0.0
    try:
        avatar = tuple(int(value) for value in goal_hint["avatar"])
        goal = tuple(int(value) for value in goal_hint["goal"])
        grid = int(goal_hint.get("grid", 64))
    except (KeyError, TypeError, ValueError):
        return 0.0

    before_distance = _manhattan(avatar, goal)
    if before_distance <= 0:
        return 0.0

    layer = [[0 for _ in range(grid)] for _ in range(grid)]
    ax, ay = avatar
    if not (0 <= ax < grid and 0 <= ay < grid):
        return 0.0
    layer[ay][ax] = 1
    try:
        predicted = hypothesis.transform.apply(layer, background_color=0, step_index=step_index)
    except ValueError:
        return 0.0
    after = _find_cell(predicted, 1)
    if after is None:
        return -1.0
    return (before_distance - _manhattan(after, goal)) / before_distance


def _find_cell(frame: list[list[int]], color: int) -> tuple[int, int] | None:
    for y, row in enumerate(frame):
        for x, value in enumerate(row):
            if int(value) == color:
                return x, y
    return None


def _manhattan(left: tuple[int, int], right: tuple[int, int]) -> int:
    return abs(left[0] - right[0]) + abs(left[1] - right[1])
