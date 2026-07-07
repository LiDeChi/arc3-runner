import time

from fastapi.testclient import TestClient

from server.main import app
from server.store import TrainingStore
from server.trainer import (
    AdversarialTrainer,
    TrainingConfig,
    run_training_episode,
    summarize_generation,
)
from server.traps import make_trap_spec


def test_training_episode_returns_metrics_and_audit_steps() -> None:
    spec = make_trap_spec("T1", spec_id="train-test", params={"k": 2, "grid": 8, "max_steps": 8})

    episode = run_training_episode(spec, max_steps=8)

    assert episode["episode_id"].startswith("ep-")
    assert "fool_score" in episode["metrics"]
    assert episode["steps"]
    assert "surprise" in episode["steps"][0]
    assert summarize_generation([episode])["prediction_accuracy"] <= 1.0


def test_training_store_persists_generation_and_knowledge(tmp_path) -> None:
    store = TrainingStore(tmp_path / "runner.db")
    store.record_prior("ACTION1", "translate")
    store.record_calibration(0.8, True)
    store.record_trap_signal("T1", "surprise>=0.3")
    store.record_generation(1, "now", {"solve_rate": 0.5}, {"fool_score": 2.0}, {"T1": 1.0})

    generations = store.list_generations()
    knowledge = store.knowledge()

    assert generations[0]["gen"] == 1
    assert knowledge["priors"][0]["action_key"] == "ACTION1"
    assert knowledge["calibration"][0]["n"] == 1
    assert knowledge["trap_signals"][0]["trap"] == "T1"


def test_training_api_runs_small_job() -> None:
    client = TestClient(app)

    response = client.post("/api/training/start", json={"generations": 1, "games_per_gen": 1})
    assert response.status_code == 202

    for _ in range(30):
        status = client.get("/api/training/status").json()
        if status["status"] == "completed":
            break
        time.sleep(0.05)

    assert client.get("/api/training/status").json()["status"] == "completed"
    assert client.get("/api/training/generations").json()
    assert client.get("/api/training/knowledge").json()["calibration"]


def test_trainer_persists_official_eval_hook(tmp_path) -> None:
    def fake_official_eval(max_games: int, training_knowledge: dict | None = None) -> dict:
        assert training_knowledge is not None
        return {
            "game_count": max_games,
            "summary": {
                "heuristic-explorer": {
                    "solve_rate": 0.0,
                    "prediction_accuracy": 0.4,
                    "ece": 0.5,
                },
                "transform-aware": {
                    "solve_rate": 0.5,
                    "prediction_accuracy": 0.8,
                    "ece": 0.2,
                },
            },
            "delta": {"solve_rate": 0.5, "prediction_accuracy": 0.4, "ece": -0.3},
        }

    trainer = AdversarialTrainer(
        store=TrainingStore(tmp_path / "runner.db"),
        official_evaluator=fake_official_eval,
    )
    trainer.start(
        TrainingConfig(
            generations=1,
            games_per_gen=1,
            official_eval_interval=1,
            official_eval_game_limit=2,
        )
    )

    for _ in range(30):
        if trainer.status()["status"] == "completed":
            break
        time.sleep(0.05)

    generation = trainer.store.list_generations()[0]
    official_eval = generation["gen_metrics"]["official_eval"]
    assert official_eval["game_count"] == 2
    assert official_eval["delta"]["solve_rate"] == 0.5
