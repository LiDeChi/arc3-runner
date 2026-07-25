from fastapi.testclient import TestClient

from server.main import app


def test_training_start_lists_generation_episodes_and_frame_steps() -> None:
    client = TestClient(app)
    response = client.post(
        "/api/training/start",
        json={"generations": 2, "games_per_gen": 4, "trap_filter": ["T1", "T6"]},
    )
    assert response.status_code == 202
    generations = response.json()["generations"]
    assert len(generations) == 2
    assert generations[1]["gen"] == 2
    assert "fool_score" in generations[1]

    episodes_response = client.get("/api/training/generations/2/episodes")
    assert episodes_response.status_code == 200
    episodes = episodes_response.json()["episodes"]
    assert len(episodes) == 4
    assert {"T1", "T6"}.issubset({episode["trap"] for episode in episodes})

    detail_response = client.get(f"/api/training/episodes/{episodes[0]['episode_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["gen"] == 2
    assert detail["spec_id"]
    assert detail["trap"] in {"T1", "T6"}
    step = detail["steps"][0]
    assert step["before_frame"]
    assert step["frame"]
    assert step["predicted_frame"]
    assert step["imagination"]["predicted_frame"]
    assert step["hypotheses"]
    assert "surprise" in step


def test_training_knowledge_has_readable_priors_and_reliability() -> None:
    client = TestClient(app)
    client.post(
        "/api/training/start",
        json={"generations": 1, "games_per_gen": 2, "trap_filter": ["T1"]},
    )

    response = client.get("/api/training/knowledge")
    assert response.status_code == 200
    payload = response.json()
    assert payload["priors"]
    assert any("T(" in prior["readable"] for prior in payload["priors"])
    assert payload["reliability"]
