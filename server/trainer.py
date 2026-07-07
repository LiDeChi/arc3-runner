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
        metrics = episode["metrics"]
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
        steps.append(
            {
                "index": step_index,
                "action": action.name,
                "reason": reason,
                "state": response.state.name,
                "surprise": audit["surprise"],
                "credibility": audit["credibility"],
                "hypotheses": audit["hypotheses"],
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


def _compose_frame(layers: Any) -> list[list[int]]:
    arrays = [np.asarray(layer, dtype=np.int16) for layer in layers]
    if not arrays:
        return [[0]]
    composed = arrays[0].copy()
    for layer in arrays[1:]:
        mask = layer != 0
        composed[mask] = layer[mask]
    return composed.astype(int).tolist()
