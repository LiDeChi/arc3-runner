from fastapi.testclient import TestClient

from arc3math.api.main import app


def test_api_run_endpoints_and_events():
    client = TestClient(app)
    created = client.post("/api/runs", json={"episodes": 3, "game_source": "handwritten", "seed": 11}).json()
    run_id = created["run_id"]
    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "done"
    episodes = client.get(f"/api/runs/{run_id}/episodes").json()
    assert len(episodes) == 3
    events = client.get(f"/api/episodes/{episodes[0]['id']}/events").json()
    assert events[0]["type"] == "episode_start"
    assert any(e["type"] == "episode_end" for e in events)
    assert client.get(f"/api/runs/{run_id}/metrics").json()
    assert "bins" in client.get(f"/api/runs/{run_id}/calibration").json()
    assert isinstance(client.get(f"/api/runs/{run_id}/traps").json(), list)
    assert client.get(f"/api/export/sft?run_id={run_id}").text


def test_ws_replays_stored_events():
    client = TestClient(app)
    run_id = client.post("/api/runs", json={"episodes": 1, "game_source": "handwritten"}).json()["run_id"]
    with client.websocket_connect(f"/api/ws/runs/{run_id}") as ws:
        first = ws.receive_json()
        assert first["type"] == "episode_start"


def test_official_run_requires_api_key(monkeypatch):
    monkeypatch.delenv("ARC_API_KEY", raising=False)
    monkeypatch.delenv("ARC_AGI_API", raising=False)
    client = TestClient(app)
    response = client.post(
        "/api/runs",
        json={"episodes": 1, "game_source": "official", "game_id": "ls20-016295f7601e", "card_id": "card-1"},
    )
    assert response.status_code == 400
