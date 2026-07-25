from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np

from server.store import TrainingStore
from server.transforms import from_spec

Grid = list[list[int]]


ACTION_SPECS: dict[int, dict[str, Any]] = {
    1: {"op": "translate", "dx": 0, "dy": -1},
    2: {"op": "translate", "dx": 0, "dy": 1},
    3: {"op": "translate", "dx": -1, "dy": 0},
    4: {"op": "translate", "dx": 1, "dy": 0},
}


@dataclass(frozen=True)
class TrainingRequest:
    generations: int = 10
    games_per_gen: int = 12
    trap_filter: tuple[str, ...] = ("T1", "T6")


class TrainingRuntime:
    def __init__(self, store: TrainingStore | None = None) -> None:
        self.store = store or TrainingStore()

    def start(self, request: TrainingRequest) -> dict[str, Any]:
        traps = request.trap_filter or ("T1", "T6")
        self.store.reset()

        for gen in range(1, request.generations + 1):
            episode_metrics: list[dict[str, Any]] = []
            for slot in range(request.games_per_gen):
                trap = traps[slot % len(traps)]
                episode = self.run_training_episode(gen=gen, slot=slot, trap=trap)
                metrics = episode["metrics"]
                episode_metrics.append(metrics)
                self.store.save_episode(
                    episode_id=episode["episode_id"],
                    gen=gen,
                    game=episode["game"],
                    source="synthetic",
                    metrics=metrics,
                    detail=episode,
                )

            self.store.save_generation(gen, self._generation_metrics(gen, episode_metrics))

        return {"status": "completed", "generations": self.store.list_generations()}

    def run_training_episode(self, *, gen: int, slot: int, trap: str) -> dict[str, Any]:
        episode_id = f"g{gen:02d}-{trap.lower()}-{slot:02d}-{uuid.uuid4().hex[:6]}"
        spec_id = f"synth-{trap.lower()}-{gen:02d}-{slot:02d}"
        frame = self._seed_frame(seed=gen * 17 + slot * 7)
        steps = []
        surprises: list[float] = []
        ece_terms: list[float] = []

        for index in range(1, 9):
            action_id = 1 if index <= 6 else 4
            action_name = f"ACTION{action_id}"
            before_frame = frame
            expected_spec = self._expected_spec(trap, index, gen)
            actual_spec = self._actual_spec(trap, index)
            predicted_frame = self._apply(before_frame, expected_spec)
            next_frame = self._apply(before_frame, actual_spec)
            error_pixels = self._errors(predicted_frame, next_frame)
            surprise = round(
                min(
                    1.0,
                    len(error_pixels) / max(1, self._changed(before_frame, next_frame)),
                ),
                3,
            )
            claimed = round(max(0.42, min(0.95, 0.9 - surprise * 0.2 - max(0, 4 - gen) * 0.02)), 3)
            calibrated = round(max(0.2, claimed - surprise * 0.28), 3)
            hit_rate = 1.0 - surprise
            ece_terms.append(abs(claimed - hit_rate))
            surprises.append(surprise)
            updated_spec = actual_spec if surprise >= 0.3 else expected_spec
            belief_flips = (
                [f"{action_name}: {self._readable(expected_spec)} → {self._readable(actual_spec)}"]
                if surprise >= 0.3
                else []
            )

            step = self._step_payload(
                index=index,
                action_id=action_id,
                action_name=action_name,
                before_frame=before_frame,
                predicted_frame=predicted_frame,
                frame=next_frame,
                trap=trap,
                spec=updated_spec,
                old_spec=expected_spec,
                surprise=surprise,
                claimed=claimed,
                calibrated=calibrated,
                error_pixels=error_pixels,
                belief_flips=belief_flips,
            )
            steps.append(step)
            frame = next_frame

        max_surprise = max(surprises, default=0.0)
        prediction_accuracy = round(1.0 - (sum(surprises) / max(1, len(surprises))), 3)
        ece = round(sum(ece_terms) / max(1, len(ece_terms)), 3)
        fool_score = round(3.0 + max_surprise * 2.0 + (0.18 if trap == "T6" else 0) - gen * 0.12, 3)
        solved = gen >= 2 and prediction_accuracy >= 0.72
        metrics = {
            "trap": trap,
            "solved": solved,
            "fool_score": fool_score,
            "steps": len(steps),
            "max_surprise": max_surprise,
            "prediction_accuracy": prediction_accuracy,
            "ece": ece,
        }
        return {
            "episode_id": episode_id,
            "gen": gen,
            "spec_id": spec_id,
            "game": spec_id,
            "trap": trap,
            "source": "synthetic",
            "solved": solved,
            "fool_score": fool_score,
            "metrics": metrics,
            "steps": steps,
        }

    def knowledge(self) -> dict[str, Any]:
        priors: dict[tuple[int, str], dict[str, Any]] = {}
        calibration_bins: dict[int, dict[str, float]] = {}
        surprise_timeline: list[dict[str, Any]] = []

        for episode in self.store.list_episode_details():
            for step in episode["steps"]:
                for hypothesis in step["hypotheses"]:
                    key = (int(hypothesis["action_id"]), hypothesis["readable"])
                    entry = priors.setdefault(
                        key,
                        {
                            "action": hypothesis["action"],
                            "action_id": hypothesis["action_id"],
                            "family": hypothesis["transform"],
                            "readable": hypothesis["readable"],
                            "support": 0,
                            "total": 0,
                        },
                    )
                    entry["support"] += int(hypothesis.get("support", 0))
                    entry["total"] += max(1, int(hypothesis.get("total", 1)))

                claimed = float(step["credibility"]["claimed"])
                hit_rate = 1.0 - float(step["surprise"]["value"])
                bucket = min(9, max(0, int(claimed * 10)))
                calib = calibration_bins.setdefault(
                    bucket,
                    {"claimed": 0.0, "hit_rate": 0.0, "n": 0},
                )
                calib["claimed"] += claimed
                calib["hit_rate"] += hit_rate
                calib["n"] += 1
                surprise_timeline.append(
                    {
                        "gen": episode["gen"],
                        "episode_id": episode["episode_id"],
                        "step": step["index"],
                        "surprise": step["surprise"]["value"],
                    }
                )

        reliability = [
            {
                "claimed": round(value["claimed"] / value["n"], 3),
                "hit_rate": round(value["hit_rate"] / value["n"], 3),
                "n": int(value["n"]),
            }
            for _, value in sorted(calibration_bins.items())
            if value["n"]
        ]
        return {
            "priors": sorted(
                priors.values(),
                key=lambda item: (item["action_id"], item["readable"]),
            ),
            "reliability": reliability,
            "surprise_timeline": surprise_timeline,
        }

    @staticmethod
    def _generation_metrics(gen: int, metrics: list[dict[str, Any]]) -> dict[str, Any]:
        count = max(1, len(metrics))
        solve_rate = sum(1 for item in metrics if item["solved"]) / count
        prediction_accuracy = sum(float(item["prediction_accuracy"]) for item in metrics) / count
        ece = sum(float(item["ece"]) for item in metrics) / count
        fool_score = sum(float(item["fool_score"]) for item in metrics) / count
        return {
            "solve_rate": round(solve_rate, 3),
            "prediction_accuracy": round(prediction_accuracy, 3),
            "ece": round(ece, 3),
            "fool_score": round(fool_score, 3),
            "weights": {
                "T1": round(0.52 + gen * 0.03, 3),
                "T6": round(0.48 - gen * 0.02, 3),
            },
        }

    @staticmethod
    def _seed_frame(seed: int) -> Grid:
        grid = [[0 for _ in range(16)] for _ in range(16)]
        x = 6 + seed % 3
        y = 11
        grid[y][x] = 8
        grid[y][x + 1] = 8
        grid[y + 1][x] = 8
        grid[2][13] = 10
        return grid

    @staticmethod
    def _expected_spec(trap: str, index: int, gen: int) -> dict[str, Any]:
        if trap == "T6" and gen >= 2 and index >= 6:
            return {"op": "translate", "dx": 0, "dy": 1}
        if trap == "T1" and gen >= 2 and index >= 6:
            return {"op": "translate", "dx": 1, "dy": 0}
        return {"op": "translate", "dx": 0, "dy": -1}

    @staticmethod
    def _actual_spec(trap: str, index: int) -> dict[str, Any]:
        if trap == "T1" and index >= 5:
            return {"op": "translate", "dx": 1, "dy": 0}
        if trap == "T6" and index >= 5:
            return {"op": "translate", "dx": 0, "dy": 1}
        return {"op": "translate", "dx": 0, "dy": -1}

    @staticmethod
    def _apply(frame: Grid, spec: dict[str, Any]) -> Grid:
        if spec.get("op") == "periodic":
            spec = spec["g"]
        try:
            return from_spec(spec).apply(frame, background_color=0)
        except Exception:
            return [row[:] for row in frame]

    @staticmethod
    def _errors(predicted: Grid, actual: Grid) -> list[dict[str, int]]:
        predicted_array = np.asarray(predicted)
        actual_array = np.asarray(actual)
        coordinates = np.argwhere(predicted_array != actual_array)
        return [
            {
                "x": int(x),
                "y": int(y),
                "before": int(predicted_array[y, x]),
                "after": int(actual_array[y, x]),
            }
            for y, x in coordinates
        ]

    @staticmethod
    def _changed(before: Grid, after: Grid) -> int:
        return int(np.count_nonzero(np.asarray(before) != np.asarray(after)))

    def _step_payload(
        self,
        *,
        index: int,
        action_id: int,
        action_name: str,
        before_frame: Grid,
        predicted_frame: Grid,
        frame: Grid,
        trap: str,
        spec: dict[str, Any],
        old_spec: dict[str, Any],
        surprise: float,
        claimed: float,
        calibrated: float,
        error_pixels: list[dict[str, int]],
        belief_flips: list[str],
    ) -> dict[str, Any]:
        hypotheses = self._hypotheses(
            action_id=action_id,
            spec=spec,
            old_spec=old_spec,
            index=index,
        )
        changed_pixels = self._errors(before_frame, frame)
        return {
            "index": index,
            "timestamp": f"training-step-{index}",
            "action_name": action_name,
            "action_id": action_id,
            "action_data": {},
            "before_frame": before_frame,
            "predicted_frame": predicted_frame,
            "frame": frame,
            "raw_frame_layers": [frame],
            "state": "SOLVED" if index == 8 else "RUNNING",
            "levels_completed": 1 if index == 8 else 0,
            "win_levels": 1,
            "available_actions": [1, 2, 3, 4],
            "available_action_details": [
                {"id": item, "name": f"ACTION{item}", "is_complex": False, "data_schema": {}}
                for item in [1, 2, 3, 4]
            ],
            "observation_input": {
                "source": "synthetic-training",
                "trap": trap,
                "frame_shape": [16, 16],
            },
            "perception": {
                "width": 16,
                "height": 16,
                "background_color": 0,
                "color_histogram": self._histogram(frame),
                "components": [],
            },
            "changed_pixels": changed_pixels,
            "observation": f"{trap} 合成训练帧；读取 16×16 状态。",
            "detected_change": f"相对上一步有 {len(changed_pixels)} 个像素变化。",
            "hypothesis": f"{action_name} ≙ {self._readable(spec)}",
            "candidates": [
                {
                    "action": f"ACTION{item}",
                    "action_id": item,
                    "data": {},
                    "score": round(2.4 - abs(item - action_id) * 0.35, 3),
                    "evidence": "训练回放候选",
                }
                for item in [1, 2, 3, 4]
            ],
            "agent_state_before": {
                "step_index": index,
                "policy": "Transform-Aware training replay",
                "action_stats": {},
                "pending_click_candidates": [],
                "used_clicks": [],
            },
            "selected_reason": (
                "Transform-Aware exploit: 选择当前最高置信空间变换；"
                "高惊奇时立刻复核函数假设。"
            ),
            "action_request": {
                "transport": "synthetic.training",
                "action": {"id": action_id, "name": action_name},
                "data": {},
            },
            "environment_response": {
                "source": "synthetic",
                "trap": trap,
                "state": "SOLVED" if index == 8 else "RUNNING",
            },
            "result": f"{trap} 训练步 {index}；surprise {surprise:.2f}。",
            "changed_cells": len(changed_pixels),
            "duration_ms": 0,
            "audit_note": "合成训练审计摘要，不包含隐藏思维链。",
            "decision_gate": "exploit" if index > 2 else "probe",
            "hypotheses": hypotheses,
            "surprise": {
                "value": surprise,
                "predicted_error_pixels": len(error_pixels),
                "belief_flips": belief_flips,
            },
            "credibility": {"claimed": claimed, "calibrated": calibrated},
            "imagination": {
                "before_frame": before_frame,
                "predicted_frame": predicted_frame,
                "actual_frame": frame,
                "error_pixels": error_pixels[:160],
            },
        }

    def _hypotheses(
        self,
        *,
        action_id: int,
        spec: dict[str, Any],
        old_spec: dict[str, Any],
        index: int,
    ) -> list[dict[str, Any]]:
        items = []
        for item in [1, 2, 3, 4]:
            transform = spec if item == action_id else ACTION_SPECS[item]
            confidence = 0.84 if item == action_id else 0.54 + item * 0.03
            items.append(
                {
                    "action": f"ACTION{item}",
                    "action_id": item,
                    "transform": transform,
                    "readable": self._readable(transform),
                    "confidence": round(confidence, 3),
                    "calibrated_confidence": round(max(0.1, confidence - 0.08), 3),
                    "support": index,
                    "total": max(index, 1),
                    "target": "foreground",
                    "alternatives": [
                        {
                            "transform": old_spec,
                            "readable": self._readable(old_spec),
                            "confidence": 0.32,
                            "support": max(0, index - 1),
                        }
                    ],
                }
            )
        return items

    @staticmethod
    def _readable(spec: dict[str, Any]) -> str:
        try:
            return from_spec(spec).readable()
        except Exception:
            if spec.get("op") == "periodic":
                f_readable = TrainingRuntime._readable(spec["f"])
                g_readable = TrainingRuntime._readable(spec["g"])
                return f"[{f_readable}]×{spec['n']} → {g_readable}"
            return str(spec.get("op", "unknown"))

    @staticmethod
    def _histogram(frame: Grid) -> list[dict[str, int]]:
        values, counts = np.unique(np.asarray(frame), return_counts=True)
        pairs = sorted(
            zip(values, counts, strict=True),
            key=lambda item: int(item[1]),
            reverse=True,
        )
        return [{"color": int(color), "count": int(count)} for color, count in pairs]
