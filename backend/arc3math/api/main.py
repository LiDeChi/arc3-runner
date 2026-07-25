from __future__ import annotations

from pathlib import Path
from threading import Thread
from typing import Any
import asyncio
import json
import tempfile

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from arc3math.agent import calibration_bins, ece_score
from arc3math.arena.db import Database
from arc3math.arena.export_sft import export_sft
from arc3math.arena.loop import run_arena
from arc3math.engine.remote_adapter import env_api_key
from arc3math.generator import generate_game


DB_PATH = Path(tempfile.gettempdir()) / "arc3math_api.sqlite3"
db = Database(DB_PATH)
app = FastAPI(title="ARC3-Math API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Hub:
    def __init__(self) -> None:
        self.clients: dict[str, set[WebSocket]] = {}

    async def connect(self, run_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.clients.setdefault(run_id, set()).add(websocket)

    def disconnect(self, run_id: str, websocket: WebSocket) -> None:
        self.clients.get(run_id, set()).discard(websocket)

    def publish(self, run_id: str, event: dict[str, Any]) -> None:
        clients = list(self.clients.get(run_id, set()))
        if not clients:
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        for ws in clients:
            loop.create_task(ws.send_json(event))


hub = Hub()


def _run_background(run_id: str, cfg: dict[str, Any]) -> None:
    run_arena(cfg, db=db, run_id=run_id, broadcaster=lambda event: hub.publish(run_id, event))


@app.post("/api/runs")
def create_run(config: dict[str, Any]) -> dict[str, Any]:
    cfg = {
        "episodes": int(config.get("episodes", 3)),
        "seed": int(config.get("seed", 0)),
        "game_source": config.get("game_source", config.get("source", "handwritten")),
        "agent": config.get("agent", {}),
        "generator": config.get("generator", {}),
        "official": config.get("official", {}),
    }
    for key in ("game_id", "card_id", "max_steps", "base_url"):
        if key in config:
            cfg[key] = config[key]
    if cfg["game_source"] == "official" and not env_api_key() and not cfg["official"].get("allow_anonymous"):
        raise HTTPException(400, "official ARC-AGI-3 runs require ARC_API_KEY (or ARC_AGI_API) in the API server environment")
    run_id = db.create_run(cfg, status="running")
    if bool(config.get("async", False)) or cfg["episodes"] > 5:
        thread = Thread(target=_run_background, args=(run_id, cfg), daemon=True)
        thread.start()
    else:
        _run_background(run_id, cfg)
    return {"run_id": run_id, "id": run_id}


@app.post("/api/runs/{run_id}/pause")
def pause_run(run_id: str) -> dict[str, Any]:
    if not db.get_run(run_id):
        raise HTTPException(404, "run not found")
    db.update_run_status(run_id, "paused")
    return {"id": run_id, "status": "paused"}


@app.post("/api/runs/{run_id}/resume")
def resume_run(run_id: str) -> dict[str, Any]:
    if not db.get_run(run_id):
        raise HTTPException(404, "run not found")
    db.update_run_status(run_id, "running")
    return {"id": run_id, "status": "running"}


@app.get("/api/runs")
def list_runs() -> list[dict[str, Any]]:
    return db.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    run = db.get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    episodes = db.list_episodes(run_id, limit=5, offset=0)
    run["latest_episodes"] = episodes
    return run


@app.get("/api/runs/{run_id}/episodes")
def episodes(run_id: str, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    if not db.get_run(run_id):
        raise HTTPException(404, "run not found")
    return db.list_episodes(run_id, limit=limit, offset=offset)


@app.get("/api/episodes/{episode_id}/events")
def episode_events(episode_id: str, after_id: int | None = Query(default=None)) -> list[dict[str, Any]]:
    return db.episode_events(episode_id, after_id=after_id)


@app.get("/api/runs/{run_id}/metrics")
def metrics(run_id: str, names: str | None = None) -> list[dict[str, Any]]:
    name_list = [n for n in names.split(",") if n] if names else None
    return db.metrics(run_id, name_list)


@app.get("/api/runs/{run_id}/calibration")
def calibration(run_id: str) -> dict[str, Any]:
    events = db.run_events(run_id)
    predictions: dict[tuple[str, int], dict[str, Any]] = {}
    samples: list[tuple[float, bool]] = []
    high_errors = []
    episode_traps = {e["id"]: e.get("traps", []) for e in db.list_episodes(run_id, limit=100000, offset=0)}
    for event in events:
        key = (event["episode_id"], event["step_idx"])
        if event["type"] == "prediction":
            predictions[key] = event["payload"]
        elif event["type"] == "outcome":
            pred = predictions.get(key, {})
            conf = float(pred.get("conf", 0.0))
            correct = bool(event["payload"].get("correct"))
            samples.append((conf, correct))
            if conf > 0.8 and not correct:
                high_errors.append(
                    {
                        "episode_id": event["episode_id"],
                        "step_idx": event["step_idx"],
                        "conf": conf,
                        "math": pred.get("math", ""),
                        "traps": episode_traps.get(event["episode_id"], []),
                    }
                )
    return {"bins": calibration_bins(samples), "ece": ece_score(samples), "high_conf_errors": high_errors}


@app.get("/api/runs/{run_id}/traps")
def traps(run_id: str) -> list[dict[str, Any]]:
    return db.trap_stats(run_id)


@app.post("/api/games/preview")
def preview_game(params: dict[str, Any]) -> dict[str, Any]:
    game = generate_game(seed=int(params.get("seed", 0)), traps=params.get("traps"))
    return game.to_json()


@app.get("/api/export/sft")
def sft(run_id: str | None = None) -> Response:
    data = export_sft(db, run_id=run_id)
    return Response(data, media_type="application/x-jsonlines")


@app.websocket("/api/ws/runs/{run_id}")
async def ws_run(websocket: WebSocket, run_id: str) -> None:
    await hub.connect(run_id, websocket)
    try:
        for event in db.run_events(run_id):
            await websocket.send_json(event)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(run_id, websocket)
