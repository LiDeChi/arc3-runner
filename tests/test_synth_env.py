from fastapi.testclient import TestClient

from server.main import app
from server.synth_env import SyntheticEnv
from server.traps import make_trap_spec


def test_t1_rule_shift_changes_action_after_k_steps() -> None:
    spec = make_trap_spec(
        "T1",
        spec_id="test-t1",
        params={"k": 1, "grid": 8, "start": [2, 5], "target": [7, 7]},
    )
    env = SyntheticEnv(spec)
    action1 = env.action_space[0]

    env.step(action1)
    assert env.avatar == (2, 4)

    env.step(action1)
    assert env.avatar == (3, 4)


def test_t6_disguised_drift_adds_rightward_bias_after_k_steps() -> None:
    spec = make_trap_spec(
        "T6",
        spec_id="test-t6",
        params={"k": 1, "grid": 8, "start": [2, 5], "target": [7, 7]},
    )
    env = SyntheticEnv(spec)
    action1 = env.action_space[0]

    env.step(action1)
    assert env.avatar == (2, 4)

    env.step(action1)
    assert env.avatar == (3, 3)


def test_synth_spec_api_lists_creates_and_reads_specs() -> None:
    client = TestClient(app)

    initial = client.get("/api/synth/specs")
    assert initial.status_code == 200
    assert initial.json()["specs"]

    created = client.post("/api/synth/specs", json={"template": "T1", "params": {"k": 2}})
    assert created.status_code == 201
    spec_id = created.json()["spec_id"]

    detail = client.get(f"/api/synth/specs/{spec_id}")
    assert detail.status_code == 200
    assert detail.json()["traps"][0]["template"] == "T1"
