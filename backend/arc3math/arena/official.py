from __future__ import annotations

from statistics import median
from typing import Any, Callable
import copy
import json
import uuid

from arc3math.arena.db import Database
from arc3math.dsl import grids_equal, match_ratio
from arc3math.engine.remote_adapter import RemoteArcClient, RemoteArcEnv, arc_action_name, env_api_key


def official_spec(game_id: str, grid: list[list[int]], available_actions: list[int], meta: dict[str, Any]) -> dict[str, Any]:
    actions = {
        f"ACTION{action_id}": {
            "program": {"op": "identity"},
            "hint": f"action_{action_id}",
        }
        for action_id in available_actions
    }
    return {
        "id": game_id,
        "size": {"w": len(grid[0]) if grid else 0, "h": len(grid)},
        "tiles": copy.deepcopy(grid),
        "entities": [],
        "actions": actions,
        "win": {"type": "official_arc"},
        "max_steps": int(meta.get("max_steps", 100)),
        "meta": meta,
    }


def choose_action(available_actions: list[int], step_idx: int, scripted_actions: list[int] | None = None) -> int:
    if scripted_actions and step_idx < len(scripted_actions):
        candidate = scripted_actions[step_idx]
        if candidate in available_actions:
            return candidate
    simple = [a for a in available_actions if a in {1, 2, 3, 4, 5}]
    choices = simple or available_actions
    if not choices:
        raise RuntimeError("official game returned no available actions")
    return choices[step_idx % len(choices)]


def run_official_arena(
    config: dict[str, Any],
    *,
    db: Database | None = None,
    run_id: str | None = None,
    broadcaster: Callable[[dict[str, Any]], None] | None = None,
    client: RemoteArcClient | None = None,
) -> dict[str, Any]:
    db = db or Database()
    official_cfg = dict(config.get("official", {}))
    if "game_id" in config:
        official_cfg["game_id"] = config["game_id"]
    if "card_id" in config:
        official_cfg["card_id"] = config["card_id"]
    if "max_steps" in config:
        official_cfg["max_steps"] = config["max_steps"]
    if "base_url" in config:
        official_cfg["base_url"] = config["base_url"]

    episodes = int(config.get("episodes", 1))
    max_steps = int(official_cfg.get("max_steps", 10))
    close_scorecard = bool(official_cfg.get("close_scorecard", False))
    scripted_actions = [int(a) for a in official_cfg.get("actions", [])]
    if client is None and not env_api_key() and not official_cfg.get("allow_anonymous"):
        raise RuntimeError("official ARC-AGI-3 runs require ARC_API_KEY (or ARC_AGI_API) in the environment")
    client = client or RemoteArcClient(base_url=official_cfg.get("base_url"))
    game_id = official_cfg.get("game_id")
    if not game_id:
        games = client.list_games()
        if not games:
            raise RuntimeError("ARC API returned no available games")
        game_id = games[0]["game_id"]
    card_id = official_cfg.get("card_id")
    opened_card = False
    if not card_id:
        card_id = client.open_scorecard(tags=["arc3-math", "official"], opaque={"run_config": official_cfg})
        opened_card = True

    cfg = {
        "episodes": episodes,
        "seed": int(config.get("seed", 0)),
        "game_source": "official",
        "official": {**official_cfg, "game_id": game_id, "card_id": card_id},
        "agent": config.get("agent", {}),
        "generator": config.get("generator", {}),
    }
    created = False
    if run_id is None:
        run_id = db.create_run(cfg, status="running")
        created = True
    else:
        db.update_run_status(run_id, "running")

    summaries: list[dict[str, Any]] = []
    for idx in range(episodes):
        episode_id = f"{run_id}-{idx:04d}-{uuid.uuid4().hex[:8]}"
        env = RemoteArcEnv(str(game_id), str(card_id), client=client)
        obs = env.reset()
        meta = {
            "source": "official",
            "game_id": game_id,
            "card_id": card_id,
            "guid": obs["guid"],
            "state": obs["state"],
            "levels_completed": obs["levels_completed"],
            "win_levels": obs["win_levels"],
            "available_actions": obs["available_actions"],
            "max_steps": max_steps,
        }
        spec = official_spec(str(game_id), obs["grid"], obs["available_actions"], meta)
        db.insert_game(run_id, spec)
        events: list[dict[str, Any]] = []

        def log(step_idx: int, type_: str, payload: dict[str, Any]) -> None:
            events.append({"episode_id": episode_id, "step_idx": step_idx, "type": type_, "payload": payload})

        log(0, "episode_start", {"game_id": game_id, "spec": spec, "official": True, "card_id": card_id, "guid": obs["guid"]})
        log(0, "observation", _observation_payload(obs, 0))

        result: str | None = obs["result"]
        action_count = 0
        confs: list[tuple[float, bool]] = []
        previous_grid = obs["grid"]
        for step_idx in range(max_steps):
            if obs["done"]:
                break
            available = [int(a) for a in obs.get("available_actions", [])]
            action_id = choose_action(available, step_idx, scripted_actions)
            action_name = arc_action_name(action_id)
            log(step_idx, "hypotheses", {"actions": []})
            log(step_idx, "plan", {"intent": "official_explore", "actions": [action_name], "imagined_grids": [], "risk": 0.0})
            log(step_idx, "prediction", {"action": action_name, "predicted_grid": previous_grid, "conf": 0.0, "math": "unknown official dynamics"})
            log(step_idx, "action_taken", {"action": action_name, "intent": "official_explore"})
            obs = env.step(action_id)
            action_count += 1
            actual_grid = obs["grid"]
            correct = grids_equal(previous_grid, actual_grid)
            confs.append((0.0, correct))
            log(step_idx, "observation", _observation_payload(obs, step_idx + 1))
            log(
                step_idx,
                "outcome",
                {
                    "actual_grid": actual_grid,
                    "match_ratio": match_ratio(previous_grid, actual_grid) if previous_grid and actual_grid else 0.0,
                    "surprise": 0.0 if correct else 1.0,
                    "correct": correct,
                    "official_state": obs["state"],
                    "levels_completed": obs["levels_completed"],
                },
            )
            previous_grid = actual_grid
            result = obs["result"]
            if obs["done"]:
                break

        if result is None:
            result = "timeout"
        avg_conf = sum(conf for conf, _ in confs) / len(confs) if confs else 0.0
        summary = {
            "result": result,
            "steps": action_count,
            "avg_conf": avg_conf,
            "overconf": 0.0,
            "probe_steps": 0,
            "revisions": 0,
        }
        log(
            action_count,
            "episode_end",
            {
                **summary,
                "official_state": obs["state"],
                "levels_completed": obs["levels_completed"],
                "win_levels": obs["win_levels"],
                "guid": obs["guid"],
                "card_id": card_id,
            },
        )
        db.insert_episode(run_id, str(game_id), idx, episode_id, summary)
        stored = db.insert_events(events)
        for event in stored:
            if broadcaster:
                broadcaster(event)
        summaries.append(summary)
        recent = summaries[-20:]
        db.insert_metric(run_id, idx, "solve_rate", sum(1 for s in recent if s["result"] == "win") / len(recent))
        db.insert_metric(run_id, idx, "median_steps", median([s["steps"] for s in recent]))
        db.insert_metric(run_id, idx, "ece", 0.0)
        db.insert_metric(run_id, idx, "overconf", 0.0)
        db.insert_metric(run_id, idx, "probe_steps", 0.0)
        db.insert_metric(run_id, idx, "difficulty", 0.0)

    scorecard = None
    if opened_card and close_scorecard:
        scorecard = client.close_scorecard(str(card_id))
    db.update_run_status(run_id, "done")
    return {"run_id": run_id, "created": created, "episodes": summaries, "game_id": game_id, "card_id": card_id, "scorecard": scorecard}


def _observation_payload(obs: dict[str, Any], step_idx: int) -> dict[str, Any]:
    return {
        "grid": obs["grid"],
        "frames": obs["frames"],
        "raw": obs.get("raw", {}),
        "step_idx": step_idx,
        "official_state": obs["state"],
        "guid": obs["guid"],
        "levels_completed": obs["levels_completed"],
        "win_levels": obs["win_levels"],
        "available_actions": obs["available_actions"],
    }
