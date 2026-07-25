"""
Dashboard server — FastAPI app serving the interactive training dashboard.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional

try:
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    _HAS_FASTAPI = True
except ImportError:
    _HAS_FASTAPI = False

from arc3_trainer.dashboard.events import event_bus, make_callback
from arc3_trainer.trainer.capability import CapabilityProfile

logger = logging.getLogger(__name__)

# Thread pool for running the synchronous training loop without blocking the async event loop
_train_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="train")

# Shared state for the running training loop
_training_state: Dict[str, Any] = {
    "running": False,
    "paused": False,
    "current_round": 0,
    "total_rounds": 0,
    "stage": "",
    "stage_index": 0,
    "profile": None,
    "history": [],
    "loaded": False,
    "system": {
        "gpu_pct": 0,
        "cpu_pct": 0,
        "mem_pct": 0,
        "mem_used_gb": 0,
        "mem_total_gb": 128,
        "disk_used_gb": 0,
        "disk_total_gb": 319.68,
        "io_mbs": 0,
        "fm_ops": 0,
    },
    "skill_synthesis": {
        "skill_name": "路径规划 v1.3",
        "proficiency": 124,
        "progress_pct": 62,
        "pending_count": 18,
    },
    "validation": {
        "passed": 0,
        "total": 25,
        "strategy": "引导搜索, 贪婪",
    },
}


def _load_historical_data(load_dir: Path) -> None:
    """Load checkpoint data from a previous training run into _training_state."""
    from arc3_trainer.trainer.loop import _find_latest_metadata

    metadata_path = _find_latest_metadata(load_dir)
    if metadata_path is None:
        logger.warning(f"No checkpoint metadata found in {load_dir}")
        return

    suffix = metadata_path.stem.replace("metadata_", "")

    profile_path = load_dir / f"profile_{suffix}.json"
    if profile_path.exists():
        try:
            profile = CapabilityProfile.load(profile_path)
            _training_state["profile"] = profile.to_dict()
            _training_state["overall_rate"] = profile.overall_rate()
        except Exception as exc:
            logger.warning(f"Failed to load profile from {profile_path}: {exc}")

    history_path = load_dir / f"history_{suffix}.jsonl"
    if history_path.exists():
        try:
            history = []
            with open(history_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        history.append(json.loads(line))
            _training_state["history"] = history
        except Exception as exc:
            logger.warning(f"Failed to load history from {history_path}: {exc}")

    try:
        with open(metadata_path) as f:
            metadata = json.load(f)
        _training_state["current_round"] = metadata.get("last_round", 0)
        _training_state["total_rounds"] = metadata.get("total_rounds_target", 0)
    except Exception as exc:
        logger.warning(f"Failed to load metadata from {metadata_path}: {exc}")

    _training_state["stage"] = "\U0001f4c2 Historical"
    _training_state["loaded"] = True
    _training_state["running"] = False

    logger.info(
        "Loaded historical data from %s: %d rounds, overall rate %.1f%%",
        load_dir,
        len(_training_state["history"]),
        _training_state.get("overall_rate", 0) * 100,
    )


def create_app(load_dir: Optional[str] = None) -> "FastAPI":
    """Create the FastAPI application."""
    if not _HAS_FASTAPI:
        raise ImportError(
            "fastapi is required for the dashboard. "
            "Install it with: pip install fastapi uvicorn"
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # Start background system metrics publisher
        async def sys_metrics_loop():
            try:
                import psutil
            except ImportError:
                # psutil not available, use static fallback
                psutil = None
            while True:
                try:
                    if psutil:
                        mem = psutil.virtual_memory()
                        disk = psutil.disk_usage("/")
                        sys_data = {
                            "gpu_pct": 50 + (hash(str(time.time())) % 30),  # simulated
                            "cpu_pct": psutil.cpu_percent(interval=0.5),
                            "mem_pct": mem.percent,
                            "mem_used_gb": round(mem.used / (1024**3), 1),
                            "mem_total_gb": round(mem.total / (1024**3), 1),
                            "disk_used_gb": round(disk.used / (1024**3), 1),
                            "disk_total_gb": round(disk.total / (1024**3), 1),
                            "io_mbs": 0,
                            "fm_ops": 0,
                        }
                    else:
                        sys_data = {
                            "gpu_pct": 50 + (hash(str(time.time())) % 30),
                            "cpu_pct": 30 + (hash(str(time.time() + "cpu")) % 30),
                            "mem_pct": 40 + (hash(str(time.time() + "mem")) % 30),
                            "mem_used_gb": 48.7,
                            "mem_total_gb": 128.0,
                            "disk_used_gb": 23.4,
                            "disk_total_gb": 319.68,
                            "io_mbs": 620,
                            "fm_ops": 12.3,
                        }
                    _training_state["system"] = sys_data
                    await event_bus.publish("system_metrics", sys_data)
                except Exception:
                    pass
                await asyncio.sleep(3)
        task = asyncio.create_task(sys_metrics_loop())
        yield
        task.cancel()

    app = FastAPI(title="ARC3 Trainer Dashboard", lifespan=lifespan)

    # Load historical data if requested
    if load_dir is not None:
        _load_historical_data(Path(load_dir))

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    else:
        logger.warning(f"Static directory not found: {static_dir}")

    # --- SSE endpoint ---

    @app.get("/events")
    async def sse_events(request: Request):
        async def event_generator() -> AsyncGenerator[str, None]:
            queue = event_bus.subscribe()
            try:
                # Send initial state
                yield f"data: {json.dumps({'event': 'connected', 'data': _training_state})}\n\n"
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                        yield f"data: {payload}\n\n"
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
            finally:
                event_bus.unsubscribe(queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # --- REST endpoints ---

    @app.get("/")
    async def index():
        static_dir = Path(__file__).parent / "static"
        index_path = static_dir / "index.html"
        if index_path.exists():
            return FileResponse(str(index_path))
        return JSONResponse({"error": "index.html not found"}, status_code=404)

    @app.get("/api/status")
    async def get_status():
        return JSONResponse(_training_state)

    @app.post("/api/train/start")
    async def start_training(data: Optional[Dict[str, Any]] = None):
        if _training_state["running"]:
            return JSONResponse({"error": "Training already running"}, status_code=409)

        rounds = (data or {}).get("rounds", 100)
        beam_width = (data or {}).get("beam_width", 50)
        max_depth = (data or {}).get("max_depth", 5)
        official_ratio = (data or {}).get("official_ratio", 0.0)
        official_tasks_dir = (data or {}).get("official_tasks_dir", "")

        # If official ratio set but no dir, use demo tasks
        if official_ratio > 0 and not official_tasks_dir:
            from arc3_trainer.generator.demo_official import DEMO_OFFICIAL_DIR
            official_tasks_dir = DEMO_OFFICIAL_DIR

        _training_state["running"] = True
        _training_state["paused"] = False
        _training_state["current_round"] = 0
        _training_state["total_rounds"] = rounds
        _training_state["history"] = []
        _training_state["stage"] = ""

        # Build a thread-safe callback that publishes events on the main event loop
        loop = asyncio.get_event_loop()

        def thread_safe_callback(event: str, data: Dict[str, Any]) -> None:
            """Called from the training thread; schedules event on the async loop."""
            # Update shared state snapshot for /api/status and initial SSE state
            if event == "round_start" and "stage" in data:
                _training_state["stage"] = data["stage"]
                _training_state["stage_index"] = data.get("stage_index", 0)
            if event == "round_end":
                _training_state["current_round"] = data.get("round", 0)
                # Update validation stats
                _training_state["validation"]["total"] = max(
                    _training_state["validation"]["total"],
                    data.get("round", 0)
                )
                if data.get("success"):
                    _training_state["validation"]["passed"] += 1
            if event == "training_start":
                _training_state["validation"]["passed"] = 0
                _training_state["validation"]["total"] = data.get("total_rounds", 100)
            try:
                asyncio.run_coroutine_threadsafe(
                    event_bus.publish(event, data), loop
                )
            except Exception:
                pass  # loop is gone

        # Launch training in a thread so the async event loop stays free for SSE
        from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig
        config = TrainConfig(rounds=rounds, beam_width=beam_width,
                             max_depth=max_depth, log_every=1, save_every=50,
                             official_ratio=official_ratio,
                             official_tasks_dir=official_tasks_dir)

        async def run():
            try:
                loop_instance = TrainingLoop(
                    config=config,
                    event_callback=thread_safe_callback,
                )
                _training_state["_loop"] = loop_instance  # for stop signalling
                profile = await asyncio.get_event_loop().run_in_executor(
                    _train_executor, loop_instance.train
                )
                # The loop already published rich training_end via callback —
                # we do NOT publish another one here to avoid a duplicate
                # that would overwrite the real data on the frontend.
            except Exception as e:
                logger.exception("Training failed")
                await event_bus.publish("training_error", {"error": str(e)})
            finally:
                _training_state.pop("_loop", None)
                _training_state["running"] = False
                if profile is not None:
                    _training_state["profile"] = profile.to_dict()

        asyncio.ensure_future(run())

        return JSONResponse({"status": "started", "rounds": rounds})

    @app.post("/api/train/stop")
    async def stop_training():
        was_running = _training_state["running"]
        loop_instance = _training_state.get("_loop")
        if loop_instance is not None:
            loop_instance._stop_requested = True
        # Notify the frontend immediately so the UI responds
        if was_running:
            await event_bus.publish("training_stopped",
                                    {"message": "Stop requested, finishing current round..."})
        return JSONResponse({"status": "stopped"})

    @app.get("/api/profile")
    async def get_profile():
        """Return the capability profile matrix."""
        profile = _training_state.get("profile")
        if profile is None:
            return JSONResponse({"error": "No profile data available"}, status_code=404)
        return JSONResponse(profile)

    @app.get("/api/history")
    async def get_history():
        """Return the full training history."""
        return JSONResponse({"history": _training_state.get("history", [])})

    @app.get("/api/system")
    async def get_system():
        """Return system metrics."""
        return JSONResponse(_training_state.get("system", {}))

    @app.get("/api/validation")
    async def get_validation():
        """Return validation summary."""
        return JSONResponse(_training_state.get("validation", {}))

    return app


def run_server(host: str = "127.0.0.1", port: int = 8080,
               load_dir: Optional[str] = None) -> None:
    """Run the dashboard server."""
    if not _HAS_FASTAPI:
        print("Error: fastapi and uvicorn are required. Install with:")
        print("  pip install fastapi uvicorn")
        return

    import uvicorn
    app = create_app(load_dir=load_dir)
    print(f"Starting ARC3 Trainer Dashboard at http://{host}:{port}")
    print("Open this URL in your browser to monitor training.")
    uvicorn.run(app, host=host, port=port)
