from collections import deque

from server.hypothesis import HypothesisTracker
from server.imagination import plan_one_step
from server.policy import choose_transform_aware_action, normalize_agent_id


class FakeAction:
    def __init__(self, value: int, name: str, complex_action: bool = False) -> None:
        self.value = value
        self.name = name
        self._complex_action = complex_action

    def is_complex(self) -> bool:
        return self._complex_action


class FakeEnv:
    def __init__(self, actions: list[FakeAction]) -> None:
        self.action_space = actions


def test_normalize_agent_id_accepts_labels_and_ids() -> None:
    assert normalize_agent_id("Transform-Aware") == "transform-aware"
    assert normalize_agent_id("transform-aware") == "transform-aware"
    assert normalize_agent_id("Heuristic Explorer") == "heuristic-explorer"


def test_plan_one_step_exploits_confident_transform() -> None:
    tracker = HypothesisTracker()
    tracker.observe(
        action_id=2,
        before_frame=[[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        after_frame=[[0, 0, 0], [0, 0, 7], [0, 0, 0]],
        step_index=1,
    )

    plan = plan_one_step(
        [FakeAction(1, "ACTION1"), FakeAction(2, "ACTION2")],
        [[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        tracker,
        step_index=2,
    )

    assert plan["mode"] == "exploit"
    assert plan["selected_action_id"] == 2
    assert plan["nodes"][0]["readable"] == "T(1,0)"


def test_transform_aware_policy_probes_without_hypotheses() -> None:
    tracker = HypothesisTracker()
    action, data, candidates, reason, decision_trace = choose_transform_aware_action(
        env=FakeEnv([FakeAction(1, "ACTION1"), FakeAction(2, "ACTION2")]),
        action_stats={},
        click_queue=deque(),
        used_clicks=set(),
        analysis={"component_count": 0},
        frame=[[0, 1], [0, 0]],
        step_index=1,
        tracker=tracker,
    )

    assert action.value == 1
    assert data == {}
    assert candidates[0]["evidence"].startswith("Transform-Aware probe")
    assert "probe" in reason
    assert decision_trace["mode"] == "probe"


def test_transform_aware_policy_exploits_confident_hypothesis() -> None:
    tracker = HypothesisTracker()
    tracker.observe(
        action_id=1,
        before_frame=[[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        after_frame=[[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        step_index=1,
    )
    tracker.observe(
        action_id=2,
        before_frame=[[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        after_frame=[[0, 0, 0], [0, 0, 7], [0, 0, 0]],
        step_index=2,
    )
    tracker.observe(
        action_id=2,
        before_frame=[[0, 0, 0, 0], [0, 7, 0, 0], [0, 0, 0, 0]],
        after_frame=[[0, 0, 0, 0], [0, 0, 7, 0], [0, 0, 0, 0]],
        step_index=3,
    )

    action, data, candidates, reason, decision_trace = choose_transform_aware_action(
        env=FakeEnv([FakeAction(1, "ACTION1"), FakeAction(2, "ACTION2")]),
        action_stats={2: {"count": 1.0, "reward": 1.0}},
        click_queue=deque(),
        used_clicks=set(),
        analysis={"component_count": 0},
        frame=[[0, 0, 0], [0, 7, 0], [0, 0, 0]],
        step_index=4,
        tracker=tracker,
    )

    assert action.value == 2
    assert data == {}
    assert candidates[0]["action_id"] == 2
    assert "exploit" in reason
    assert decision_trace["mode"] == "exploit"
