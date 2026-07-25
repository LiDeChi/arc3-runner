from __future__ import annotations

import copy
import logging
import math
import threading
import time
import uuid
from collections import deque
from datetime import UTC, datetime
from typing import Any

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from server.hypothesis import HypothesisTracker
from server.policy import (
    agent_label,
    choose_action_sweep,
    choose_transform_aware_action,
    choose_visual_click_probe,
    normalize_agent_id,
)
from server.synth_env import SyntheticEnv
from server.trainer import AdversarialTrainer, TrainingConfig
from server.traps import default_synth_specs, make_trap_spec, synth_game_info

logger = logging.getLogger("arc3-runner")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def short_game_id(game_id: str) -> str:
    return game_id.split("-", 1)[0]


class RunRequest(BaseModel):
    game_ids: list[str] = Field(min_length=1, max_length=25)
    max_actions: int = Field(default=40, ge=1, le=80)
    agent: str = "Heuristic Explorer"


class SynthSpecRequest(BaseModel):
    template: str = "T6"
    params: dict[str, Any] = Field(default_factory=dict)


class TrainingStartRequest(BaseModel):
    generations: int = Field(default=2, ge=1, le=50)
    games_per_gen: int = Field(default=4, ge=1, le=100)
    trap_filter: list[str] | None = None
    official_eval_interval: int = Field(default=5, ge=0, le=50)
    official_eval_game_limit: int = Field(default=2, ge=1, le=10)


class RunnerRuntime:
    """Owns the official Arcade client and mutable run snapshots."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._arcade: Any | None = None
        self._games: list[dict[str, Any]] = []
        self._runs: dict[str, dict[str, Any]] = {}
        self._discovery_error: str | None = None
        self._synth_specs: dict[str, dict[str, Any]] = {
            spec["spec_id"]: spec for spec in default_synth_specs()
        }

    def _get_arcade(self) -> Any:
        if self._arcade is None:
            import arc_agi

            self._arcade = arc_agi.Arcade(operation_mode=arc_agi.OperationMode.ONLINE)
        return self._arcade

    def discover_games(self, force: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            if self._games and not force:
                return copy.deepcopy(self._games)

        try:
            arcade = self._get_arcade()
            games = []
            for item in arcade.get_environments():
                games.append(
                    {
                        "game_id": short_game_id(item.game_id),
                        "official_game_id": item.game_id,
                        "title": item.title or short_game_id(item.game_id).upper(),
                        "tags": item.tags or [],
                        "baseline_actions": item.baseline_actions or [],
                        "default_fps": item.default_fps or 5,
                        "source": "official",
                    }
                )
            games.extend(self._synth_game_infos())
            games.sort(key=lambda game: game["game_id"])
            with self._lock:
                self._games = games
                self._discovery_error = None
            return copy.deepcopy(games)
        except Exception as exc:  # pragma: no cover - network-dependent
            logger.exception("Official game discovery failed")
            with self._lock:
                self._discovery_error = str(exc)
                if self._games:
                    return copy.deepcopy(self._games)
            return self._synth_game_infos()

    def list_synth_specs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(spec) for spec in self._synth_specs.values()]

    def get_synth_spec(self, spec_id: str) -> dict[str, Any]:
        with self._lock:
            spec = self._synth_specs.get(spec_id)
            if spec is None:
                raise KeyError(spec_id)
            return copy.deepcopy(spec)

    def create_synth_spec(self, request: SynthSpecRequest) -> dict[str, Any]:
        spec = make_trap_spec(request.template, params=request.params)
        with self._lock:
            self._synth_specs[spec["spec_id"]] = spec
            self._games = []
        return copy.deepcopy(spec)

    def _synth_game_infos(self) -> list[dict[str, Any]]:
        with self._lock:
            return [synth_game_info(spec) for spec in self._synth_specs.values()]

    def start_run(self, request: RunRequest) -> dict[str, Any]:
        known = {game["game_id"]: game for game in self.discover_games()}
        requested: list[str] = []
        for raw_id in request.game_ids:
            game_id = short_game_id(raw_id)
            if game_id not in known:
                raise ValueError(f"Unknown or inaccessible official game: {raw_id}")
            if game_id not in requested:
                requested.append(game_id)

        agent_id = normalize_agent_id(request.agent)
        run_mode = (
            "synth-local"
            if all(known[game_id].get("source") == "synth-local" for game_id in requested)
            else "official-live"
        )
        run_id = uuid.uuid4().hex[:12]
        run = {
            "run_id": run_id,
            "status": "queued",
            "agent": agent_id,
            "mode": run_mode,
            "max_actions": request.max_actions,
            "created_at": utc_now(),
            "started_at": None,
            "finished_at": None,
            "current_game_id": requested[0],
            "game_order": requested,
            "games": {
                game_id: {
                    "game_id": game_id,
                    "official_game_id": known[game_id]["official_game_id"],
                    "title": known[game_id]["title"],
                    "tags": known[game_id]["tags"],
                    "baseline_actions": known[game_id]["baseline_actions"],
                    "default_fps": known[game_id]["default_fps"],
                    "status": "queued",
                    "state": "NOT_STARTED",
                    "levels_completed": 0,
                    "win_levels": 0,
                    "action_count": 0,
                    "started_at": None,
                    "finished_at": None,
                    "error": None,
                    "steps": [],
                }
                for game_id in requested
            },
        }
        with self._lock:
            self._runs[run_id] = run

        worker = threading.Thread(
            target=self._execute_suite,
            args=(run_id,),
            name=f"arc3-run-{run_id}",
            daemon=True,
        )
        worker.start()
        return self.get_run(run_id)

    def list_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            runs = list(self._runs.values())
            return [self._run_summary(run) for run in reversed(runs)]

    def evaluate_official_agents(
        self,
        max_games: int = 2,
        max_actions: int = 20,
        training_knowledge: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        games = [
            game
            for game in self.discover_games()
            if game.get("source") == "official"
        ][:max_games]
        agents = ["heuristic-explorer", "transform-aware"]
        has_training_knowledge = bool(
            training_knowledge
            and (
                training_knowledge.get("priors")
                or training_knowledge.get("calibration")
            )
        )
        if has_training_knowledge:
            agents.append("transform-aware-trained")
        rows: list[dict[str, Any]] = []
        for game in games:
            row: dict[str, Any] = {"game_id": game["game_id"]}
            for agent in agents:
                try:
                    env = self._make_official_env(game["game_id"])
                    policy_agent = (
                        "transform-aware"
                        if agent == "transform-aware-trained"
                        else agent
                    )
                    row[agent] = self._evaluate_env_agent(
                        env,
                        policy_agent,
                        max_actions,
                        knowledge=_official_training_knowledge(training_knowledge)
                        if agent == "transform-aware-trained"
                        else None,
                    )
                except Exception as exc:  # pragma: no cover - network/runtime dependent
                    row[agent] = {"error": str(exc), "solved": False}
            rows.append(row)

        summary = {
            agent: _summarize_eval_rows(
                [
                    row[agent]
                    for row in rows
                    if agent in row and "error" not in row[agent]
                ]
            )
            for agent in agents
        }
        report = {
            "game_count": len(rows),
            "max_actions": max_actions,
            "games": rows,
            "summary": summary,
            "delta": {
                "solve_rate": round(
                    summary["transform-aware"]["solve_rate"]
                    - summary["heuristic-explorer"]["solve_rate"],
                    4,
                ),
                "prediction_accuracy": round(
                    summary["transform-aware"]["prediction_accuracy"]
                    - summary["heuristic-explorer"]["prediction_accuracy"],
                    4,
                ),
                "ece": round(
                    summary["transform-aware"]["ece"]
                    - summary["heuristic-explorer"]["ece"],
                    4,
                ),
            },
        }
        if "transform-aware-trained" in summary:
            report["trained_delta"] = {
                "solve_rate": round(
                    summary["transform-aware-trained"]["solve_rate"]
                    - summary["transform-aware"]["solve_rate"],
                    4,
                ),
                "prediction_accuracy": round(
                    summary["transform-aware-trained"]["prediction_accuracy"]
                    - summary["transform-aware"]["prediction_accuracy"],
                    4,
                ),
                "ece": round(
                    summary["transform-aware-trained"]["ece"]
                    - summary["transform-aware"]["ece"],
                    4,
                ),
            }
        return report

    def _make_official_env(self, game_id: str, attempts: int = 2) -> Any:
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                env = self._get_arcade().make(game_id)
                if env is not None and getattr(env, "observation_space", None) is not None:
                    return env
            except Exception as exc:  # pragma: no cover - official API dependent
                last_error = exc
        if last_error is not None:
            raise last_error
        raise RuntimeError(f"Official environment could not be created: {game_id}")

    def _evaluate_env_agent(
        self,
        env: Any,
        agent_name: str,
        max_actions: int,
        knowledge: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        current = env.observation_space
        frame = self._compose_frame(current.frame)
        action_stats: dict[int, dict[str, float]] = {}
        click_queue: deque[tuple[int, int]] = deque(self._candidate_clicks(frame))
        used_clicks: set[tuple[int, int]] = set()
        tracker = HypothesisTracker(knowledge=knowledge)
        surprises: list[float] = []
        calibration_points: list[dict[str, Any]] = []
        steps = 0
        solved = False
        state_name = getattr(current.state, "name", str(current.state))

        for index in range(1, max_actions + 1):
            analysis = self._analyze_frame(frame, None)
            action, data, _candidates, _reason, decision_trace = self._choose_action(
                env,
                action_stats,
                click_queue,
                used_clicks,
                analysis,
                frame,
                tracker,
                index,
                agent_name,
            )
            response = env.step(action, data=data, reasoning={"mode": "official-eval"})
            if response is None:
                break
            next_frame = self._compose_frame(response.frame)
            audit = tracker.observe(
                action_id=action.value,
                before_frame=frame,
                after_frame=next_frame,
                step_index=index,
                decision_trace=decision_trace,
            )
            surprise = float(audit["surprise"]["value"])
            claimed = float(audit["credibility"]["calibrated"])
            surprises.append(surprise)
            calibration_points.append({"claimed": claimed, "hit": max(0.0, 1.0 - surprise)})
            next_analysis = self._analyze_frame(next_frame, frame)
            level_gain = max(0, int(response.levels_completed) - int(current.levels_completed))
            stat = action_stats.setdefault(action.value, {"count": 0.0, "reward": 0.0})
            stat["count"] += 1
            stat["reward"] += math.log1p(float(next_analysis["changed_cells"])) + 20.0 * level_gain
            frame = next_frame
            current = response
            steps = index
            state_name = response.state.name
            if state_name == "WIN":
                solved = True
                break
            if state_name == "GAME_OVER":
                break

        prediction_accuracy = 1.0 - (sum(surprises) / max(len(surprises), 1))
        return {
            "solved": solved,
            "steps": steps,
            "state": state_name,
            "prediction_accuracy": round(prediction_accuracy, 4),
            "ece": round(_eval_ece(calibration_points), 4),
        }

    def get_run(self, run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._runs.get(run_id)
            if run is None:
                raise KeyError(run_id)
            return copy.deepcopy(run)

    def _run_summary(self, run: dict[str, Any]) -> dict[str, Any]:
        return {
            key: copy.deepcopy(run[key])
            for key in (
                "run_id",
                "status",
                "agent",
                "mode",
                "max_actions",
                "created_at",
                "started_at",
                "finished_at",
                "current_game_id",
                "game_order",
            )
        }

    def _update_run(self, run_id: str, **updates: Any) -> None:
        with self._lock:
            self._runs[run_id].update(updates)

    def _update_game(self, run_id: str, game_id: str, **updates: Any) -> None:
        with self._lock:
            self._runs[run_id]["games"][game_id].update(updates)

    def _append_step(self, run_id: str, game_id: str, step: dict[str, Any]) -> None:
        with self._lock:
            game = self._runs[run_id]["games"][game_id]
            game["steps"].append(step)
            game["state"] = step["state"]
            game["levels_completed"] = step["levels_completed"]
            game["win_levels"] = step["win_levels"]
            game["action_count"] = max(0, len(game["steps"]) - 1)

    def _execute_suite(self, run_id: str) -> None:
        run = self.get_run(run_id)
        self._update_run(run_id, status="running", started_at=utc_now())
        try:
            for game_id in run["game_order"]:
                self._update_run(run_id, current_game_id=game_id)
                self._execute_game(run_id, game_id, run["max_actions"], run["agent"])
            final = self.get_run(run_id)
            statuses = [game["status"] for game in final["games"].values()]
            status = "completed" if any(value == "solved" for value in statuses) else "stopped"
            self._update_run(run_id, status=status, finished_at=utc_now())
        except Exception as exc:  # pragma: no cover - defensive worker guard
            logger.exception("Run %s failed", run_id)
            self._update_run(run_id, status="error", finished_at=utc_now(), error=str(exc))

    def _execute_game(self, run_id: str, game_id: str, max_actions: int, agent_name: str) -> None:
        self._update_game(run_id, game_id, status="starting", started_at=utc_now())
        try:
            if game_id in self._synth_specs:
                env = SyntheticEnv(self.get_synth_spec(game_id))
            else:
                env = self._make_official_env(game_id)
            if env is None or env.observation_space is None:
                raise RuntimeError("Environment could not be created")
            current = env.observation_space
            initial_frame = self._compose_frame(current.frame)
            initial_analysis = self._analyze_frame(initial_frame, None)
            action_stats: dict[int, dict[str, float]] = {}
            click_queue: deque[tuple[int, int]] = deque(
                self._candidate_clicks(initial_frame)
            )
            used_clicks: set[tuple[int, int]] = set()
            hypothesis_tracker = HypothesisTracker()
            initial_reasoning = {
                "schema": "arc3-runner.audit.v3",
                "observation": initial_analysis["summary"],
                "hypothesis": initial_analysis["hypothesis"],
                "candidates": [],
                "selected": {
                    "action": "RESET",
                    "data": {},
                    "reason": "初始化官方环境并读取首帧。",
                },
            }
            self._append_step(
                run_id,
                game_id,
                self._build_step(
                    index=0,
                    action_name="RESET",
                    action_id=0,
                    action_data={},
                    before=None,
                    current=current,
                    analysis=initial_analysis,
                    candidates=[],
                    selected_reason="初始化官方环境并读取首帧。",
                    duration_ms=0,
                    reasoning=initial_reasoning,
                    agent_state=self._agent_state(
                        action_stats, click_queue, used_clicks, 0, agent_name
                    ),
                    action_catalog=self._action_catalog(env),
                    transport="arcade.make",
                    audit_bundle=hypothesis_tracker.initial_audit(initial_frame),
                ),
            )
            self._update_game(run_id, game_id, status="running")

            previous_frame = initial_frame

            for index in range(1, max_actions + 1):
                analysis = self._analyze_frame(previous_frame, None)
                agent_state_before = self._agent_state(
                    action_stats, click_queue, used_clicks, index, agent_name
                )
                action, data, candidates, reason, decision_trace = self._choose_action(
                    env,
                    action_stats,
                    click_queue,
                    used_clicks,
                    analysis,
                    previous_frame,
                    hypothesis_tracker,
                    index,
                    agent_name,
                )
                reasoning = {
                    "schema": "arc3-runner.audit.v3",
                    "observation": analysis["summary"],
                    "hypothesis": analysis["hypothesis"],
                    "candidates": candidates,
                    "selected": {"action": action.name, "data": data, "reason": reason},
                }
                started = time.perf_counter()
                response = env.step(action, data=data, reasoning=reasoning)
                duration_ms = int((time.perf_counter() - started) * 1000)
                if response is None:
                    raise RuntimeError(f"Official API returned no frame for {action.name}")

                next_frame = self._compose_frame(response.frame)
                next_analysis = self._analyze_frame(next_frame, previous_frame)
                novelty = float(next_analysis["changed_cells"])
                level_gain = max(
                    0,
                    int(response.levels_completed)
                    - int(self.get_run(run_id)["games"][game_id]["levels_completed"]),
                )
                stat = action_stats.setdefault(action.value, {"count": 0.0, "reward": 0.0})
                stat["count"] += 1
                stat["reward"] += math.log1p(novelty) + 20.0 * level_gain

                if action.is_complex():
                    click_queue.extend(
                        point
                        for point in self._candidate_clicks(next_frame)
                        if point not in used_clicks and point not in click_queue
                    )

                audit_bundle = hypothesis_tracker.observe(
                    action_id=action.value,
                    before_frame=previous_frame,
                    after_frame=next_frame,
                    step_index=index,
                    decision_trace=decision_trace,
                )
                self._append_step(
                    run_id,
                    game_id,
                    self._build_step(
                        index=index,
                        action_name=action.name,
                        action_id=action.value,
                        action_data=data,
                        before=previous_frame,
                        current=response,
                        analysis=next_analysis,
                        candidates=candidates,
                        selected_reason=reason,
                        duration_ms=duration_ms,
                        reasoning=reasoning,
                        agent_state=agent_state_before,
                        action_catalog=self._action_catalog(env),
                        transport="EnvironmentWrapper.step",
                        audit_bundle=audit_bundle,
                    ),
                )
                previous_frame = next_frame

                state_name = response.state.name
                if state_name == "WIN":
                    self._update_game(run_id, game_id, status="solved", finished_at=utc_now())
                    return
                if state_name == "GAME_OVER":
                    self._update_game(run_id, game_id, status="failed", finished_at=utc_now())
                    return
                time.sleep(0.08)

            self._update_game(run_id, game_id, status="limit", finished_at=utc_now())
        except Exception as exc:
            logger.exception("Game %s failed", game_id)
            self._update_game(
                run_id,
                game_id,
                status="error",
                error=str(exc),
                finished_at=utc_now(),
            )

    def _choose_action(
        self,
        env: Any,
        action_stats: dict[int, dict[str, float]],
        click_queue: deque[tuple[int, int]],
        used_clicks: set[tuple[int, int]],
        analysis: dict[str, Any],
        frame: list[list[int]],
        hypothesis_tracker: HypothesisTracker,
        index: int,
        agent_name: str,
    ) -> tuple[Any, dict[str, int], list[dict[str, Any]], str, dict[str, Any] | None]:
        actions = list(env.action_space)
        if not actions:
            raise RuntimeError("Environment exposed no available actions")

        agent_id = normalize_agent_id(agent_name)
        if agent_id == "transform-aware":
            return choose_transform_aware_action(
                env=env,
                action_stats=action_stats,
                click_queue=click_queue,
                used_clicks=used_clicks,
                analysis=analysis,
                frame=frame,
                step_index=index,
                tracker=hypothesis_tracker,
            )

        if agent_id == "action-sweep":
            action, data, candidates, reason = choose_action_sweep(env, action_stats)
            return action, data, candidates, reason, None

        complex_actions = [action for action in actions if action.is_complex()]
        if complex_actions:
            prefix = (
                "Visual Click Scan"
                if agent_id == "visual-click-scan"
                else "Heuristic Explorer visual probe"
            )
            action, data, candidates, reason = choose_visual_click_probe(
                complex_actions=complex_actions,
                click_queue=click_queue,
                used_clicks=used_clicks,
                analysis=analysis,
                step_index=index,
                evidence_prefix=prefix,
            )
            return action, data, candidates, reason, None

        candidates: list[dict[str, Any]] = []
        for action in actions:
            stat = action_stats.get(action.value, {"count": 0.0, "reward": 0.0})
            mean_reward = stat["reward"] / max(stat["count"], 1.0)
            exploration = 2.2 / math.sqrt(stat["count"] + 1.0)
            score = (
                10.0 - action.value * 0.001
                if stat["count"] == 0
                else mean_reward + exploration
            )
            candidates.append(
                {
                    "action": action.name,
                    "action_id": action.value,
                    "data": {},
                    "score": round(score, 3),
                    "evidence": (
                        "未尝试"
                        if stat["count"] == 0
                        else f"平均信息增益 {mean_reward:.2f}"
                    ),
                }
            )

        ranked = sorted(
            actions,
            key=lambda item: next(
                candidate["score"]
                for candidate in candidates
                if candidate["action_id"] == item.value
            ),
            reverse=True,
        )
        action = ranked[0]
        reason = "优先执行未充分探索或历史信息增益更高的动作。"
        return action, {}, candidates, reason, None

    def _build_step(
        self,
        *,
        index: int,
        action_name: str,
        action_id: int,
        action_data: dict[str, int],
        before: list[list[int]] | None,
        current: Any,
        analysis: dict[str, Any],
        candidates: list[dict[str, Any]],
        selected_reason: str,
        duration_ms: int,
        reasoning: dict[str, Any],
        agent_state: dict[str, Any],
        action_catalog: list[dict[str, Any]],
        transport: str,
        audit_bundle: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        frame = self._compose_frame(current.frame)
        raw_layers = self._serialize_layers(current.frame)
        audit = audit_bundle or {"schema": "arc3-runner.audit.v2"}
        result = (
            f"环境返回 {current.state.name}；关卡进度 "
            f"{int(current.levels_completed)}/{int(current.win_levels)}；"
            f"变化 {analysis['changed_cells']} 格。"
        )
        step = {
            "schema": audit.get("schema", "arc3-runner.audit.v2"),
            "index": index,
            "timestamp": utc_now(),
            "action_name": action_name,
            "action_id": action_id,
            "action_data": action_data,
            "frame": frame,
            "before_frame": before,
            "raw_frame_layers": raw_layers,
            "state": current.state.name,
            "levels_completed": int(current.levels_completed),
            "win_levels": int(current.win_levels),
            "available_actions": list(current.available_actions or []),
            "available_action_details": action_catalog,
            "observation_input": {
                "game_id": current.game_id,
                "guid": current.guid,
                "state": current.state.name,
                "levels_completed": int(current.levels_completed),
                "win_levels": int(current.win_levels),
                "full_reset": bool(getattr(current, "full_reset", False)),
                "available_actions": list(current.available_actions or []),
                "frame_layer_count": len(raw_layers),
                "frame_shapes": [
                    [len(layer), len(layer[0]) if layer else 0]
                    for layer in raw_layers
                ],
                "frame_layers_ref": "raw_frame_layers",
            },
            "perception": {
                "width": analysis["width"],
                "height": analysis["height"],
                "background_color": analysis["background_color"],
                "color_histogram": analysis["color_histogram"],
                "components": analysis["components"],
            },
            "changed_pixels": analysis["changed_pixels"],
            "observation": analysis["summary"],
            "detected_change": analysis["change_summary"],
            "hypothesis": analysis["hypothesis"],
            "candidates": candidates,
            "agent_state_before": agent_state,
            "selected_reason": selected_reason,
            "action_request": {
                "transport": transport,
                "action": {"id": action_id, "name": action_name},
                "data": action_data,
                "reasoning": reasoning,
            },
            "environment_response": self._response_payload(current, raw_layers),
            "result": result,
            "changed_cells": analysis["changed_cells"],
            "duration_ms": duration_ms,
            "audit_note": "结构化审计摘要，不包含模型隐藏思维链。",
        }
        step.update({key: value for key, value in audit.items() if key != "schema"})
        return step

    @staticmethod
    def _serialize_layers(layers: Any) -> list[list[list[int]]]:
        return [np.asarray(layer, dtype=np.int16).astype(int).tolist() for layer in layers]

    @staticmethod
    def _action_catalog(env: Any) -> list[dict[str, Any]]:
        catalog = []
        for action in env.action_space:
            try:
                schema = action.action_type.model_json_schema()
            except (AttributeError, TypeError):
                schema = {}
            catalog.append(
                {
                    "id": action.value,
                    "name": action.name,
                    "is_complex": bool(action.is_complex()),
                    "data_schema": schema,
                }
            )
        return catalog

    @staticmethod
    def _agent_state(
        action_stats: dict[int, dict[str, float]],
        click_queue: deque[tuple[int, int]],
        used_clicks: set[tuple[int, int]],
        step_index: int,
        agent_name: str,
    ) -> dict[str, Any]:
        agent_id = normalize_agent_id(agent_name)
        policy_map = {
            "heuristic-explorer": "Heuristic Explorer: untried-first + information-gain",
            "action-sweep": "Action Sweep: round-robin over simple actions",
            "visual-click-scan": "Visual Click Scan: visual-region clicks for complex actions",
            "transform-aware": "Transform-Aware: hypothesis confidence gate + probe/exploit",
        }
        return {
            "step_index": step_index,
            "policy": policy_map.get(agent_id, policy_map["heuristic-explorer"]),
            "agent": agent_label(agent_id),
            "action_stats": {
                f"ACTION{action_id}": {
                    "trials": int(stats["count"]),
                    "cumulative_information_reward": round(stats["reward"], 4),
                    "mean_information_reward": round(
                        stats["reward"] / max(stats["count"], 1.0), 4
                    ),
                }
                for action_id, stats in sorted(action_stats.items())
            },
            "pending_click_candidates": [
                {"x": point[0], "y": point[1]} for point in click_queue
            ],
            "used_clicks": [
                {"x": point[0], "y": point[1]} for point in sorted(used_clicks)
            ],
        }

    @staticmethod
    def _response_payload(current: Any, raw_layers: list[list[list[int]]]) -> dict[str, Any]:
        action_input = getattr(current, "action_input", None)
        if action_input is None:
            serialized_action = None
        else:
            action_id = getattr(action_input, "id", None)
            serialized_action = {
                "id": getattr(action_id, "value", action_id),
                "name": getattr(action_id, "name", str(action_id)),
                "data": getattr(action_input, "data", None),
                "reasoning": getattr(action_input, "reasoning", None),
            }
        return {
            "game_id": current.game_id,
            "guid": current.guid,
            "state": current.state.name,
            "levels_completed": int(current.levels_completed),
            "win_levels": int(current.win_levels),
            "full_reset": bool(getattr(current, "full_reset", False)),
            "available_actions": list(current.available_actions or []),
            "action_input": serialized_action,
            "frame_layer_count": len(raw_layers),
            "frame_shapes": [
                [len(layer), len(layer[0]) if layer else 0] for layer in raw_layers
            ],
            "frame_layers_ref": "raw_frame_layers",
        }

    @staticmethod
    def _compose_frame(layers: Any) -> list[list[int]]:
        arrays = [np.asarray(layer, dtype=np.int16) for layer in layers]
        if not arrays:
            return [[0]]
        composed = arrays[0].copy()
        for layer in arrays[1:]:
            mask = layer != 0
            composed[mask] = layer[mask]
        return composed.astype(int).tolist()

    @staticmethod
    def _analyze_frame(
        frame: list[list[int]], previous: list[list[int]] | None
    ) -> dict[str, Any]:
        array = np.asarray(frame)
        colors, counts = np.unique(array, return_counts=True)
        palette = sorted(
            ((int(color), int(count)) for color, count in zip(colors, counts, strict=True)),
            key=lambda item: item[1],
            reverse=True,
        )
        components = RunnerRuntime._extract_components(frame)
        changed_cells = 0
        changed_pixels: list[dict[str, int]] = []
        if previous is not None:
            before = np.asarray(previous)
            if before.shape == array.shape:
                changed_coordinates = np.argwhere(before != array)
                changed_cells = int(len(changed_coordinates))
                changed_pixels = [
                    {
                        "x": int(x),
                        "y": int(y),
                        "before": int(before[y, x]),
                        "after": int(array[y, x]),
                    }
                    for y, x in changed_coordinates
                ]
        dominant = ", ".join(f"{color}:{count}" for color, count in palette[:4])
        return {
            "summary": (
                f"读取 {array.shape[1]}×{array.shape[0]} 帧；"
                f"{len(colors)} 种颜色；主要颜色计数 {dominant}。"
            ),
            "change_summary": (
                "首帧，无前序差异。"
                if previous is None
                else f"相对上一步有 {changed_cells} 个像素变化。"
            ),
            "hypothesis": (
                "优先测试可用动作与显著视觉区域，保留能产生新状态或关卡进展的策略。"
            ),
            "changed_cells": changed_cells,
            "changed_pixels": changed_pixels,
            "width": int(array.shape[1]),
            "height": int(array.shape[0]),
            "background_color": palette[0][0],
            "color_histogram": [
                {"color": color, "count": count} for color, count in palette
            ],
            "components": components,
            "component_count": len(components),
        }

    @staticmethod
    def _extract_components(frame: list[list[int]]) -> list[dict[str, Any]]:
        array = np.asarray(frame)
        height, width = array.shape
        components: list[dict[str, Any]] = []
        visited = np.zeros_like(array, dtype=bool)
        values, counts = np.unique(array, return_counts=True)
        background = int(values[int(np.argmax(counts))])

        for y in range(height):
            for x in range(width):
                if visited[y, x] or int(array[y, x]) == background:
                    continue
                color = int(array[y, x])
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
                if cells:
                    px = round(sum(cell[0] for cell in cells) / len(cells))
                    py = round(sum(cell[1] for cell in cells) / len(cells))
                    xs = [cell[0] for cell in cells]
                    ys = [cell[1] for cell in cells]
                    components.append(
                        {
                            "id": len(components),
                            "color": color,
                            "size": len(cells),
                            "center": {"x": px, "y": py},
                            "bounds": {
                                "x_min": min(xs),
                                "y_min": min(ys),
                                "x_max": max(xs),
                                "y_max": max(ys),
                            },
                        }
                    )

        components.sort(key=lambda component: component["size"], reverse=True)
        for index, component in enumerate(components):
            component["id"] = index
        return components

    @staticmethod
    def _candidate_clicks(frame: list[list[int]]) -> list[tuple[int, int]]:
        array = np.asarray(frame)
        height, width = array.shape
        components = RunnerRuntime._extract_components(frame)

        scaled: list[tuple[int, int]] = []
        for component in components[:40]:
            x = int(component["center"]["x"])
            y = int(component["center"]["y"])
            sx = min(63, max(0, round(x * 64 / max(width, 1))))
            sy = min(63, max(0, round(y * 64 / max(height, 1))))
            if (sx, sy) not in scaled:
                scaled.append((sx, sy))
        return scaled or [(32, 32)]


def _summarize_eval_rows(rows: list[dict[str, Any]]) -> dict[str, float]:
    if not rows:
        return {"solve_rate": 0.0, "prediction_accuracy": 0.0, "ece": 0.0}
    return {
        "solve_rate": round(sum(1 for row in rows if row.get("solved")) / len(rows), 4),
        "prediction_accuracy": round(
            sum(float(row.get("prediction_accuracy", 0.0)) for row in rows) / len(rows),
            4,
        ),
        "ece": round(sum(float(row.get("ece", 0.0)) for row in rows) / len(rows), 4),
    }


def _eval_ece(points: list[dict[str, Any]]) -> float:
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


def _official_training_knowledge(
    training_knowledge: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not training_knowledge:
        return None
    return {
        # Synthetic action priors are source-specific; only calibration transfers to official eval.
        "priors": [],
        "calibration": list(training_knowledge.get("calibration", [])),
    }


runtime = RunnerRuntime()
trainer = AdversarialTrainer(official_evaluator=runtime.evaluate_official_agents)
app = FastAPI(title="ARC3 Runner API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(127\.0\.0\.1|localhost):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "arc3-runner"}


@app.get("/api/games")
def games(refresh: bool = False) -> dict[str, Any]:
    try:
        return {"mode": "official-live", "games": runtime.discover_games(force=refresh)}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Official discovery failed: {exc}") from exc


@app.get("/api/synth/specs")
def synth_specs() -> dict[str, Any]:
    return {"specs": runtime.list_synth_specs()}


@app.post("/api/synth/specs", status_code=201)
def create_synth_spec(request: SynthSpecRequest) -> dict[str, Any]:
    try:
        return runtime.create_synth_spec(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/synth/specs/{spec_id}")
def synth_spec_detail(spec_id: str) -> dict[str, Any]:
    try:
        return runtime.get_synth_spec(spec_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Synthetic spec not found") from exc


@app.post("/api/training/start", status_code=202)
def start_training(request: TrainingStartRequest) -> dict[str, Any]:
    return trainer.start(
        TrainingConfig(
            generations=request.generations,
            games_per_gen=request.games_per_gen,
            trap_filter=request.trap_filter,
            official_eval_interval=request.official_eval_interval,
            official_eval_game_limit=request.official_eval_game_limit,
        )
    )


@app.post("/api/training/stop")
def stop_training() -> dict[str, Any]:
    return trainer.stop()


@app.get("/api/training/status")
def training_status() -> dict[str, Any]:
    return trainer.status()


@app.get("/api/training/generations")
def training_generations() -> list[dict[str, Any]]:
    return trainer.store.list_generations()


@app.get("/api/training/generations/{gen}/games")
def training_generation_games(gen: int) -> list[dict[str, Any]]:
    return trainer.store.list_generation_games(gen)


@app.get("/api/training/generations/{gen}/episodes")
def training_generation_episodes(gen: int) -> list[dict[str, Any]]:
    return trainer.store.list_generation_episodes(gen)


@app.get("/api/training/episodes/{episode_id}")
def training_episode(episode_id: str) -> dict[str, Any]:
    try:
        return trainer.store.get_episode(episode_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Training episode not found") from exc


@app.get("/api/training/knowledge")
def training_knowledge() -> dict[str, Any]:
    return trainer.store.knowledge()


@app.get("/api/runs")
def runs() -> list[dict[str, Any]]:
    return runtime.list_runs()


@app.post("/api/runs", status_code=202)
def create_run(request: RunRequest) -> dict[str, Any]:
    try:
        return runtime.start_run(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str) -> dict[str, Any]:
    try:
        return runtime.get_run(run_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Run not found") from exc
