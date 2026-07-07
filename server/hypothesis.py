from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import numpy as np

from server.transforms import Identity, Toggle, Transform, Translate, from_spec


@dataclass
class TransformHypothesis:
    action_id: int
    transform: Transform
    support: int
    violations: int
    first_seen_step: int
    last_seen_step: int
    source: str

    @property
    def confidence(self) -> float:
        return (self.support + 1) / (self.support + self.violations + 2)

    @property
    def score(self) -> float:
        return self.confidence - 0.05 * self.transform.complexity

    @property
    def hypothesis_id(self) -> str:
        return f"h-a{self.action_id}-{abs(hash(str(self.transform.to_spec()))) % 100000}"

    def to_event(self, alternatives: list[str] | None = None) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "action_id": self.action_id,
            "scope": {"object_selector": "foreground", "region": None},
            "transform": self.transform.to_spec(),
            "readable": f"ACTION{self.action_id} ≙ {self.transform.readable()} on foreground",
            "support": self.support,
            "violations": self.violations,
            "confidence": round(self.confidence, 4),
            "complexity": self.transform.complexity,
            "source": self.source,
            "alternatives": alternatives or [],
        }


class HypothesisTracker:
    """Shadow-mode transform hypothesis tracker for audit.v3 events."""

    def __init__(self, knowledge: dict[str, Any] | None = None) -> None:
        self._hypotheses: dict[int, list[TransformHypothesis]] = {}
        self._calibration: list[dict[str, Any]] = []
        self._online_hits: list[float] = []
        if knowledge:
            self._seed_from_knowledge(knowledge)

    def initial_audit(self, frame: list[list[int]]) -> dict[str, Any]:
        return {
            "schema": "arc3-runner.audit.v3",
            "hypotheses": self.snapshot(),
            "imagination": {
                "predicted_frame": frame,
                "plan_tree": {"mode": "reset", "nodes": []},
                "mode": "probe",
            },
            "surprise": {
                "value": 0.0,
                "pixel_error": 0,
                "pixel_error_rate": 0.0,
                "object_error": 0.0,
                "belief_flips": [],
            },
            "credibility": {"claimed": 0.0, "calibrated": 0.0, "gate": "probe"},
        }

    def observe(
        self,
        *,
        action_id: int,
        before_frame: list[list[int]],
        after_frame: list[list[int]],
        step_index: int,
        decision_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        previous_top = self.top(action_id)
        predicted_frame = self.predict(action_id, before_frame, step_index=step_index)
        surprise = compare_prediction(predicted_frame, after_frame, previous_top)

        fitted = infer_transform(before_frame, after_frame)
        previous_readable = previous_top.transform.readable() if previous_top else None
        self._update(action_id, fitted, step_index)
        current_top = self.top(action_id)
        current_readable = current_top.transform.readable() if current_top else None

        belief_flips = []
        if previous_readable and current_readable and previous_readable != current_readable:
            belief_flips.append({"from": previous_readable, "to": current_readable})

        claimed = current_top.confidence if current_top else 0.0
        calibrated = self.calibrate(claimed)
        mode = str(decision_trace.get("mode")) if decision_trace else (
            "exploit" if calibrated >= 0.5 else "probe"
        )
        surprise["belief_flips"] = belief_flips
        plan_tree = decision_trace or {
            "mode": mode,
            "nodes": [
                {
                    "action_id": action_id,
                    "readable": previous_readable or "unfit",
                    "confidence": round(previous_top.confidence, 4)
                    if previous_top
                    else 0.0,
                    "children": [],
                }
            ],
        }

        audit = {
            "schema": "arc3-runner.audit.v3",
            "hypotheses": self.snapshot(),
            "imagination": {
                "predicted_frame": predicted_frame,
                "plan_tree": plan_tree,
                "mode": mode,
            },
            "surprise": surprise,
            "credibility": {
                "claimed": round(claimed, 4),
                "calibrated": round(calibrated, 4),
                "gate": mode,
            },
        }
        self._online_hits.append(max(0.0, 1.0 - float(surprise["value"])))
        self._online_hits = self._online_hits[-50:]
        return audit

    def predict(
        self,
        action_id: int,
        frame: list[list[int]],
        *,
        step_index: int,
    ) -> list[list[int]]:
        top = self.top(action_id)
        if top is None:
            return [row[:] for row in frame]
        try:
            return top.transform.apply(frame, step_index=step_index)
        except ValueError:
            return [row[:] for row in frame]

    def top(self, action_id: int) -> TransformHypothesis | None:
        entries = self._hypotheses.get(action_id, [])
        if not entries:
            return None
        return max(entries, key=lambda item: (item.score, item.support, -item.transform.complexity))

    def snapshot(self) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for _action_id, entries in sorted(self._hypotheses.items()):
            ranked = sorted(
                entries,
                key=lambda item: (item.score, item.support, -item.transform.complexity),
                reverse=True,
            )
            if not ranked:
                continue
            alternatives = [
                f"{item.transform.readable()}: {item.confidence:.2f}" for item in ranked[1:4]
            ]
            events.append(ranked[0].to_event(alternatives=alternatives))
        return events

    def calibrate(self, confidence: float) -> float:
        if not self._calibration:
            return confidence
        if len(self._online_hits) >= 3:
            online_hit_rate = sum(self._online_hits) / len(self._online_hits)
            return (
                (online_hit_rate * len(self._online_hits))
                + (confidence * 2.0)
            ) / (len(self._online_hits) + 2.0)
        bucket = round(min(0.9, max(0.0, confidence // 0.1 * 0.1)), 1)
        selected = min(
            self._calibration,
            key=lambda row: abs(float(row.get("bucket", 0.0)) - bucket),
        )
        n = max(0, int(selected.get("n", 0)))
        if n <= 0:
            return confidence
        hit_rate = float(selected.get("hit_rate", confidence))
        # Keep transferred calibration conservative until in-game evidence is available.
        return (hit_rate + confidence) / 2.0

    def _update(self, action_id: int, fitted: Transform, step_index: int) -> None:
        entries = self._hypotheses.setdefault(action_id, [])
        matched = False
        for item in entries:
            if item.transform.equals(fitted):
                item.support += 1
                item.last_seen_step = step_index
                matched = True
            else:
                item.violations += 1

        if not matched:
            entries.append(
                TransformHypothesis(
                    action_id=action_id,
                    transform=fitted,
                    support=1,
                    violations=0,
                    first_seen_step=step_index,
                    last_seen_step=step_index,
                    source=f"fit@step{step_index}",
                )
            )

    def _seed_from_knowledge(self, knowledge: dict[str, Any]) -> None:
        self._calibration = [
            dict(row)
            for row in knowledge.get("calibration", [])
            if "bucket" in row and "hit_rate" in row
        ]
        for row in knowledge.get("priors", []):
            action_id = _parse_action_key(str(row.get("action_key", "")))
            if action_id is None:
                continue
            transform = _transform_from_prior_key(str(row.get("family", "")))
            if transform is None:
                continue
            support = max(1, int(row.get("support", 1)))
            total = max(support, int(row.get("total", support)))
            self._hypotheses.setdefault(action_id, []).append(
                TransformHypothesis(
                    action_id=action_id,
                    transform=transform,
                    support=support,
                    violations=max(0, total - support),
                    first_seen_step=0,
                    last_seen_step=0,
                    source="prior",
                )
            )


def infer_transform(before_frame: list[list[int]], after_frame: list[list[int]]) -> Transform:
    before = _as_array(before_frame)
    after = _as_array(after_frame)
    if before.shape != after.shape:
        return Identity()
    if np.array_equal(before, after):
        return Identity()

    translation = _infer_largest_color_translation(before, after)
    if translation is not None:
        return translation

    changed = np.argwhere(before != after)
    cells = [(int(x), int(y)) for y, x in changed[:256]]
    target_color = int(after[changed[0][0], changed[0][1]]) if len(changed) else 1
    return Toggle(cells=cells, color=target_color)


def compare_prediction(
    predicted_frame: list[list[int]],
    actual_frame: list[list[int]],
    hypothesis: TransformHypothesis | None,
) -> dict[str, Any]:
    predicted = _as_array(predicted_frame)
    actual = _as_array(actual_frame)
    if predicted.shape != actual.shape:
        pixel_error = int(actual.size)
        rate = 1.0
    else:
        pixel_error = int(np.count_nonzero(predicted != actual))
        rate = pixel_error / max(int(actual.size), 1)

    object_error = 0.0 if hypothesis is not None and pixel_error == 0 else round(min(1.0, rate), 4)
    return {
        "value": round(min(1.0, rate * 4), 4),
        "pixel_error": pixel_error,
        "pixel_error_rate": round(rate, 4),
        "object_error": object_error,
        "belief_flips": [],
    }


def _infer_largest_color_translation(before: np.ndarray, after: np.ndarray) -> Translate | None:
    before_objects = _largest_component_by_color(before)
    after_objects = _largest_component_by_color(after)
    best: tuple[int, int, int] | None = None
    for color, before_cells in before_objects.items():
        after_cells = after_objects.get(color)
        if not after_cells:
            continue
        before_center = _centroid(before_cells)
        after_center = _centroid(after_cells)
        dx = round(after_center[0] - before_center[0])
        dy = round(after_center[1] - before_center[1])
        if dx == 0 and dy == 0:
            continue
        score = min(len(before_cells), len(after_cells))
        if best is None or score > best[0]:
            best = (score, dx, dy)

    if best is None:
        return None
    return Translate(dx=best[1], dy=best[2])


def _largest_component_by_color(array: np.ndarray) -> dict[int, list[tuple[int, int]]]:
    background = _background(array)
    height, width = array.shape
    visited = np.zeros_like(array, dtype=bool)
    largest: dict[int, list[tuple[int, int]]] = {}

    for y in range(height):
        for x in range(width):
            color = int(array[y, x])
            if visited[y, x] or color == background:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            cells: list[tuple[int, int]] = []
            while stack:
                cx, cy = stack.pop()
                cells.append((cx, cy))
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if (
                        0 <= nx < width
                        and 0 <= ny < height
                        and not visited[ny, nx]
                        and int(array[ny, nx]) == color
                    ):
                        visited[ny, nx] = True
                        stack.append((nx, ny))
            if len(cells) > len(largest.get(color, [])):
                largest[color] = cells
    return largest


def _centroid(cells: list[tuple[int, int]]) -> tuple[float, float]:
    return (
        sum(x for x, _ in cells) / max(len(cells), 1),
        sum(y for _, y in cells) / max(len(cells), 1),
    )


def _as_array(frame: list[list[int]]) -> np.ndarray:
    if not frame:
        return np.zeros((1, 1), dtype=np.int16)
    return np.asarray(frame, dtype=np.int16)


def _background(array: np.ndarray) -> int:
    values, counts = np.unique(array, return_counts=True)
    return int(values[int(np.argmax(counts))])


def _parse_action_key(action_key: str) -> int | None:
    if not action_key.upper().startswith("ACTION"):
        return None
    try:
        return int(action_key[6:])
    except ValueError:
        return None


def _transform_from_prior_key(value: str) -> Transform | None:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(decoded, dict):
        return None
    try:
        return from_spec(decoded)
    except (KeyError, TypeError, ValueError):
        return None
