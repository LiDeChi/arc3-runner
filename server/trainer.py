from __future__ import annotations

import json
import threading
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import numpy as np

from server.hypothesis import HypothesisTracker
from server.policy import choose_transform_aware_action
from server.store import TrainingStore
from server.synth_env import SyntheticEnv
from server.traps import make_trap_spec


@dataclass(frozen=True)
class TrainingConfig:
    generations: int
    games_per_gen: int
    trap_filter: list[str] | None = None
    official_eval_interval: int = 5
    official_eval_game_limit: int = 2


class AdversarialTrainer:
    def __init__(
        self,
        store: TrainingStore | None = None,
        official_evaluator: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.store = store or TrainingStore()
        self.official_evaluator = official_evaluator
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._worker: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "status": "idle",
            "current_generation": 0,
            "total_generations": 0,
            "current_game": None,
            "games_completed": 0,
            "games_per_generation": 0,
            "metrics": {},
        }

    def start(self, config: TrainingConfig) -> dict[str, Any]:
        with self._lock:
            if self._status["status"] == "running":
                return self.status()
            self._stop.clear()
            self._status = {
                "status": "running",
                "current_generation": 0,
                "total_generations": config.generations,
                "current_game": None,
                "games_completed": 0,
                "games_per_generation": config.games_per_gen,
                "metrics": {},
            }
            self._worker = threading.Thread(
                target=self._run,
                args=(config,),
                name="arc3-adversarial-trainer",
                daemon=True,
            )
            self._worker.start()
            return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        with self._lock:
            if self._status["status"] == "running":
                self._status["status"] = "stopping"
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _run(self, config: TrainingConfig) -> None:
        traps = [trap.upper() for trap in (config.trap_filter or ["T1", "T6"])]
        weights = {trap: 1.0 / len(traps) for trap in traps}
        try:
            for gen in range(1, config.generations + 1):
                if self._stop.is_set():
                    break
                self._set_status(current_generation=gen, games_completed=0)
                episodes = []
                for game_index in range(config.games_per_gen):
                    if self._stop.is_set():
                        break
                    trap = traps[game_index % len(traps)]
                    spec = make_trap_spec(
                        trap,
                        params={
                            "k": 2 + ((gen + game_index) % 5),
                            "grid": 16,
                            "max_steps": 28,
                        },
                    )
                    self._set_status(current_game=spec["spec_id"], games_completed=game_index)
                    episode = run_training_episode(
                        spec,
                        max_steps=28,
                        knowledge=self.store.knowledge(),
                    )
                    episodes.append(episode)
                    self._record_episode(gen, spec, episode)

                if not episodes:
                    continue
                metrics = summarize_generation(episodes)
                official_eval = None
                if (
                    self.official_evaluator is not None
                    and config.official_eval_interval > 0
                    and gen % config.official_eval_interval == 0
                ):
                    official_eval = self.official_evaluator(
                        config.official_eval_game_limit,
                        training_knowledge=self.store.knowledge(),
                    )
                fool_by_trap = _fool_by_trap(episodes)
                if fool_by_trap:
                    total = sum(fool_by_trap.values())
                    weights = {trap: score / total for trap, score in fool_by_trap.items()}
                gen_metrics: dict[str, Any] = {"fool_score": metrics["fool_score"]}
                if official_eval is not None:
                    gen_metrics["official_eval"] = official_eval
                self.store.record_generation(
                    gen=gen,
                    created_at=datetime.now(UTC).isoformat(),
                    agent_metrics={
                        "solve_rate": metrics["solve_rate"],
                        "prediction_accuracy": metrics["prediction_accuracy"],
                        "ece": metrics["ece"],
                    },
                    gen_metrics=gen_metrics,
                    weights=weights,
                )
                status_metrics = dict(metrics)
                if official_eval is not None:
                    status_metrics["official_eval"] = official_eval
                self._set_status(
                    metrics=status_metrics,
                    games_completed=len(episodes),
                    current_game=None,
                )

            final_status = "completed" if not self._stop.is_set() else "idle"
            self._set_status(status=final_status, current_game=None)
        except Exception as exc:  # pragma: no cover - defensive background guard
            self._set_status(status="error", error=str(exc), current_game=None)

    def _record_episode(self, gen: int, spec: dict[str, Any], episode: dict[str, Any]) -> None:
        trap = spec["traps"][0]["template"]
        metrics = {**episode["metrics"], "trap": trap}
        self.store.record_synth_game(
            spec_id=spec["spec_id"],
            gen=gen,
            spec=spec,
            fool_score=metrics["fool_score"],
            solved=metrics["solved"],
        )
        self.store.record_episode(
            episode_id=episode["episode_id"],
            gen=gen,
            game=spec["spec_id"],
            source="synth-local",
            metrics=metrics,
            steps=episode["steps"],
        )
        if metrics["max_surprise"] >= 0.3:
            self.store.record_trap_signal(trap, "surprise>=0.3")
        for hypothesis in episode["final_hypotheses"]:
            if hypothesis["transform"].get("op") == "identity":
                continue
            family = _transform_prior_key(hypothesis["transform"])
            self.store.record_prior(f"ACTION{hypothesis['action_id']}", family)
        for point in episode["calibration_points"]:
            self.store.record_calibration(
                float(point.get("raw_claimed", point["claimed"])),
                float(point["hit"]),
            )

    def _set_status(self, **updates: Any) -> None:
        with self._lock:
            self._status.update(updates)


def run_training_episode(
    spec: dict[str, Any],
    max_steps: int = 28,
    knowledge: dict[str, Any] | None = None,
) -> dict[str, Any]:
    env = SyntheticEnv(spec)
    tracker = HypothesisTracker(knowledge=knowledge)
    action_stats: dict[int, dict[str, float]] = {}
    click_queue: deque[tuple[int, int]] = deque()
    used_clicks: set[tuple[int, int]] = set()
    frame = _compose_frame(env.observation_space.frame)
    steps: list[dict[str, Any]] = []
    calibration_points: list[dict[str, Any]] = []
    fool_score = 0.0
    surprises: list[float] = []

    for step_index in range(1, max_steps + 1):
        action, data, candidates, reason, decision_trace = choose_transform_aware_action(
            env=env,
            action_stats=action_stats,
            click_queue=click_queue,
            used_clicks=used_clicks,
            analysis={"component_count": 0},
            frame=frame,
            step_index=step_index,
            tracker=tracker,
        )
        agent_state_before = _agent_state_snapshot(
            action_stats,
            click_queue,
            used_clicks,
            step_index,
        )
        response = env.step(action, data=data, reasoning={"selected": reason})
        next_frame = _compose_frame(response.frame)
        audit = tracker.observe(
            action_id=action.value,
            before_frame=frame,
            after_frame=next_frame,
            step_index=step_index,
            decision_trace=decision_trace,
        )
        surprise = float(audit["surprise"]["value"])
        raw_claimed = float(audit["credibility"]["claimed"])
        claimed = float(audit["credibility"]["calibrated"])
        hit = max(0.0, 1.0 - surprise)
        calibration_points.append(
            {"claimed": claimed, "raw_claimed": raw_claimed, "hit": hit}
        )
        surprises.append(surprise)
        fool_score += claimed * surprise
        stat = action_stats.setdefault(action.value, {"count": 0.0, "reward": 0.0})
        stat["count"] += 1
        stat["reward"] += 1.0 - surprise + 5.0 * int(response.levels_completed)
        changed_pixels = _changed_pixels(frame, next_frame)
        selected_hypothesis = next(
            (
                hypothesis
                for hypothesis in audit["hypotheses"]
                if int(hypothesis["action_id"]) == int(action.value)
            ),
            audit["hypotheses"][0] if audit["hypotheses"] else None,
        )
        steps.append(
            {
                "schema": audit["schema"],
                "index": step_index,
                "timestamp": datetime.now(UTC).isoformat(),
                "action_name": action.name,
                "action_id": int(action.value),
                "action_data": data,
                "frame": next_frame,
                "before_frame": frame,
                "raw_frame_layers": response.frame,
                "state": response.state.name,
                "levels_completed": int(response.levels_completed),
                "win_levels": int(response.win_levels),
                "available_actions": [int(value) for value in response.available_actions],
                "available_action_details": _action_catalog(env),
                "observation_input": {
                    "game_id": response.game_id,
                    "guid": response.guid,
                    "state": response.state.name,
                    "levels_completed": int(response.levels_completed),
                    "win_levels": int(response.win_levels),
                    "full_reset": bool(response.full_reset),
                    "available_actions": [int(value) for value in response.available_actions],
                    "frame_layer_count": len(response.frame),
                    "frame_shapes": [
                        [len(layer), len(layer[0]) if layer else 0]
                        for layer in response.frame
                    ],
                    "frame_layers_ref": "raw_frame_layers",
                },
                "perception": {
                    "width": len(next_frame[0]) if next_frame else 0,
                    "height": len(next_frame),
                    "background_color": 0,
                    "color_histogram": _histogram(next_frame),
                    "components": [],
                },
                "changed_pixels": changed_pixels,
                "observation": (
                    f"读取 {len(next_frame[0]) if next_frame else 0}×{len(next_frame)} "
                    f"合成训练帧；{len(_histogram(next_frame))} 种颜色。"
                ),
                "detected_change": f"相对上一步有 {len(changed_pixels)} 个像素变化。",
                "hypothesis": (
                    str(selected_hypothesis["readable"])
                    if selected_hypothesis
                    else f"{action.name} 尚未拟合变换"
                ),
                "candidates": candidates,
                "agent_state_before": agent_state_before,
                "selected_reason": reason,
                "action_request": {
                    "transport": "synthetic.training",
                    "action": {"id": int(action.value), "name": action.name},
                    "data": data,
                    "reasoning": {"selected": reason},
                },
                "environment_response": {
                    "game_id": response.game_id,
                    "guid": response.guid,
                    "state": response.state.name,
                    "levels_completed": int(response.levels_completed),
                    "win_levels": int(response.win_levels),
                    "available_actions": [int(value) for value in response.available_actions],
                },
                "result": (
                    f"环境返回 {response.state.name}；"
                    f"关卡 {response.levels_completed}/{response.win_levels}；"
                    f"变化 {len(changed_pixels)} 格。"
                ),
                "changed_cells": len(changed_pixels),
                "duration_ms": 0,
                "audit_note": "结构化训练审计摘要，不包含模型隐藏思维链。",
                **{key: value for key, value in audit.items() if key != "schema"},
            }
        )
        frame = next_frame
        if response.state.name in {"WIN", "GAME_OVER"}:
            break

    solved = env.state.name == "WIN"
    if not solved:
        fool_score += 5.0
    avg_surprise = sum(surprises) / max(len(surprises), 1)
    return {
        "episode_id": f"ep-{uuid.uuid4().hex[:12]}",
        "spec_id": spec["spec_id"],
        "trap": spec["traps"][0]["template"],
        "metrics": {
            "solved": solved,
            "steps": len(steps),
            "fool_score": round(fool_score, 4),
            "prediction_accuracy": round(1.0 - avg_surprise, 4),
            "max_surprise": round(max(surprises or [0.0]), 4),
        },
        "steps": steps,
        "final_hypotheses": tracker.snapshot(),
        "calibration_points": calibration_points,
    }


def summarize_generation(episodes: list[dict[str, Any]]) -> dict[str, float]:
    solve_rate = sum(1 for episode in episodes if episode["metrics"]["solved"]) / len(episodes)
    prediction_accuracy = sum(
        float(episode["metrics"]["prediction_accuracy"]) for episode in episodes
    ) / len(episodes)
    fool_score = sum(
        float(episode["metrics"]["fool_score"]) for episode in episodes
    ) / len(episodes)
    points = [
        point
        for episode in episodes
        for point in episode.get("calibration_points", [])
    ]
    ece = _ece(points)
    return {
        "solve_rate": round(solve_rate, 4),
        "prediction_accuracy": round(prediction_accuracy, 4),
        "ece": round(ece, 4),
        "fool_score": round(fool_score, 4),
    }


def _ece(points: list[dict[str, Any]]) -> float:
    if not points:
        return 0.0
    buckets: dict[int, list[dict[str, Any]]] = {}
    for point in points:
        bucket = min(9, max(0, int(float(point["claimed"]) * 10)))
        buckets.setdefault(bucket, []).append(point)
    total = len(points)
    ece = 0.0
    for values in buckets.values():
        claimed = sum(float(point["claimed"]) for point in values) / len(values)
        hit_rate = sum(float(point["hit"]) for point in values) / len(values)
        ece += (len(values) / total) * abs(claimed - hit_rate)
    return ece


def _fool_by_trap(episodes: list[dict[str, Any]]) -> dict[str, float]:
    scores: dict[str, float] = {}
    for episode in episodes:
        trap = str(episode["trap"])
        scores[trap] = scores.get(trap, 0.0) + float(episode["metrics"]["fool_score"])
    return scores


def _transform_prior_key(transform: dict[str, Any]) -> str:
    return json.dumps(transform, sort_keys=True, separators=(",", ":"))


def _action_catalog(env: SyntheticEnv) -> list[dict[str, Any]]:
    return [
        {
            "id": int(action.value),
            "name": action.name,
            "is_complex": bool(action.is_complex()),
            "data_schema": action.action_type.model_json_schema(),
        }
        for action in env.action_space
    ]


def _agent_state_snapshot(
    action_stats: dict[int, dict[str, float]],
    click_queue: deque[tuple[int, int]],
    used_clicks: set[tuple[int, int]],
    step_index: int,
) -> dict[str, Any]:
    return {
        "step_index": step_index,
        "policy": "Transform-Aware",
        "agent": "transform-aware",
        "action_stats": {
            f"ACTION{action_id}": {
                "trials": int(values["count"]),
                "cumulative_information_reward": round(float(values["reward"]), 4),
                "mean_information_reward": round(
                    float(values["reward"]) / max(float(values["count"]), 1.0),
                    4,
                ),
            }
            for action_id, values in sorted(action_stats.items())
        },
        "pending_click_candidates": [
            {"x": int(x), "y": int(y)} for x, y in click_queue
        ],
        "used_clicks": [
            {"x": int(x), "y": int(y)} for x, y in sorted(used_clicks)
        ],
    }


def _changed_pixels(
    before: list[list[int]],
    after: list[list[int]],
) -> list[dict[str, int]]:
    before_array = np.asarray(before)
    after_array = np.asarray(after)
    coordinates = np.argwhere(before_array != after_array)
    return [
        {
            "x": int(x),
            "y": int(y),
            "before": int(before_array[y, x]),
            "after": int(after_array[y, x]),
        }
        for y, x in coordinates
    ]


def _histogram(frame: list[list[int]]) -> list[dict[str, int]]:
    values, counts = np.unique(np.asarray(frame), return_counts=True)
    pairs = sorted(
        zip(values, counts, strict=True),
        key=lambda item: int(item[1]),
        reverse=True,
    )
    return [
        {"color": int(color), "count": int(count)}
        for color, count in pairs
    ]


def _compose_frame(layers: Any) -> list[list[int]]:
    arrays = [np.asarray(layer, dtype=np.int16) for layer in layers]
    if not arrays:
        return [[0]]
    composed = arrays[0].copy()
    for layer in arrays[1:]:
        mask = layer != 0
        composed[mask] = layer[mask]
    return composed.astype(int).tolist()
