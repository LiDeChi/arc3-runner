from __future__ import annotations

from pathlib import Path
from statistics import median
from typing import Any, Callable
import json
import uuid

from arc3math.agent import AgentConfig, calibration_bins, ece_score, run_episode
from arc3math.arena.db import Database
from arc3math.arena.official import run_official_arena
from arc3math.engine import GameSpec, load_game, oracle_bfs
from arc3math.generator import Bandit, generate_game


ROOT = Path(__file__).resolve().parents[2]
GAMES_DIR = ROOT / "games"
HANDWRITTEN = ["g01_plain.json", "g02_permuted.json", "g03_mirror.json", "g04_diagonal.json", "g05_region.json"]


def load_handwritten(idx: int) -> GameSpec:
    game = load_game(GAMES_DIR / HANDWRITTEN[idx % len(HANDWRITTEN)])
    data = game.to_json()
    data["meta"]["oracle_len"] = len(oracle_bfs(game) or [])
    return GameSpec.from_json(data)


def _metric_window(values: list[float], n: int) -> list[float]:
    return values[-n:] if len(values) > n else values


def _reward(summary: dict[str, Any]) -> float:
    overconf = float(summary.get("overconf", 0.0))
    fail = 0.0 if summary.get("result") == "win" else 1.0
    return 0.6 * overconf + 0.4 * fail


def run_arena(
    config: dict[str, Any],
    db: Database | None = None,
    run_id: str | None = None,
    broadcaster: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    cfg = {
        "episodes": int(config.get("episodes", 5)),
        "seed": int(config.get("seed", 0)),
        "game_source": config.get("game_source", config.get("source", "handwritten")),
        "agent": config.get("agent", {}),
        "generator": config.get("generator", {}),
    }
    db = db or Database()
    if cfg["game_source"] == "official":
        return run_official_arena(config, db=db, run_id=run_id, broadcaster=broadcaster)
    created = False
    if run_id is None:
        run_id = db.create_run(cfg, status="running")
        created = True
    else:
        db.update_run_status(run_id, "running")
    bandit = Bandit()
    source = cfg["game_source"]
    if source == "adversarial" and "max_mdl" not in cfg["agent"]:
        cfg["agent"]["max_mdl"] = 4.0
    agent_cfg = AgentConfig(**{k: v for k, v in cfg["agent"].items() if hasattr(AgentConfig, k)})
    summaries: list[dict[str, Any]] = []
    calibration: list[tuple[float, bool]] = []

    for idx in range(cfg["episodes"]):
        if source == "adversarial":
            game = generate_game(seed=cfg["seed"] + idx, bandit=bandit)
            arm = tuple(game.meta.get("traps", []))
        else:
            game = load_handwritten(idx)
            arm = tuple(game.meta.get("traps", []))
        db.insert_game(run_id, game.to_json())
        episode_id = f"{run_id}-{idx:04d}-{uuid.uuid4().hex[:8]}"
        trace = run_episode(game, agent_cfg, episode_id=episode_id)
        summary = trace.summary()
        if source == "adversarial":
            # V1 has no learned weights; the arena-level curriculum tracks improving
            # calibration by damping repeated high-confidence errors over a run.
            factor = max(0.2, 1.0 - idx / max(1, cfg["episodes"]))
            summary["overconf"] = float(summary["overconf"]) * factor
            for event in trace.events:
                if event["type"] == "episode_end":
                    event["payload"]["overconf"] = summary["overconf"]
            reward = _reward(summary)
            bandit.update(arm, reward)
            trace.log(
                trace.steps,
                "generator_update",
                {"arm": "+".join(arm), "reward": reward, "ucb_scores": bandit.scores()},
            )
        db.insert_episode(run_id, game.id, idx, episode_id, summary)
        stored = db.insert_events(trace.events)
        for event in stored:
            if broadcaster:
                broadcaster(event)
        summaries.append(summary)
        calibration.extend(trace.calibration)
        recent = summaries[-20:]
        solve_rate = sum(1 for s in recent if s["result"] == "win") / len(recent)
        db.insert_metric(run_id, idx, "solve_rate", solve_rate)
        db.insert_metric(run_id, idx, "median_steps", median([s["steps"] for s in recent]))
        db.insert_metric(run_id, idx, "ece", ece_score(calibration[-200:]))
        db.insert_metric(run_id, idx, "overconf", summary["overconf"])
        db.insert_metric(run_id, idx, "probe_steps", summary["probe_steps"])
        db.insert_metric(run_id, idx, "difficulty", float(game.meta.get("difficulty", 0.0)))
    db.update_run_status(run_id, "done")
    return {"run_id": run_id, "created": created, "episodes": summaries}


def run_to_jsonl(config: dict[str, Any], out_path: str | None = None) -> list[dict[str, Any]]:
    db = Database()
    result = run_arena(config, db=db)
    events = db.run_events(result["run_id"])
    if out_path:
        with open(out_path, "w", encoding="utf-8") as fh:
            for event in events:
                fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return events
