from arc3math.agent import ece_score, run_episode
from arc3math.engine import load_game


def event_types(trace):
    return [e["type"] for e in trace.events]


def test_plain_game_solves_without_revision():
    trace = run_episode(load_game("games/g01_plain.json"), episode_id="g01")
    assert trace.summary()["result"] == "win"
    assert trace.summary()["steps"] <= 10
    assert "belief_revision" not in event_types(trace)


def test_mirror_game_revises_and_wins():
    trace = run_episode(load_game("games/g03_mirror.json"), episode_id="g03")
    assert trace.summary()["result"] == "win"
    assert "belief_revision" in event_types(trace)


def test_region_game_probes_and_calibrates():
    trace = run_episode(load_game("games/g05_region.json"), episode_id="g05")
    assert trace.summary()["result"] == "win"
    assert any(e["type"] == "action_taken" and e["payload"]["intent"] == "probe" for e in trace.events)
    assert trace.calibration
    assert ece_score(trace.calibration) >= 0.0


def test_event_order_core_step():
    trace = run_episode(load_game("games/g01_plain.json"), episode_id="order")
    by_step = {}
    for event in trace.events:
        by_step.setdefault(event["step_idx"], []).append(event["type"])
    first = by_step[0]
    for name in ["hypotheses", "plan", "prediction", "action_taken", "observation", "outcome"]:
        assert name in first
    assert first.index("hypotheses") < first.index("plan") < first.index("prediction") < first.index("action_taken")
