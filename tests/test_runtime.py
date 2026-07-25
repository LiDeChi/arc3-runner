from collections import deque
from types import SimpleNamespace

import numpy as np

from server.main import RunnerRuntime, short_game_id


def test_short_game_id() -> None:
    assert short_game_id("ls20-9607627b") == "ls20"
    assert short_game_id("ft09") == "ft09"


def test_compose_frame_overlays_non_zero_cells() -> None:
    base = np.array([[1, 1], [1, 1]])
    overlay = np.array([[0, 2], [0, 0]])
    assert RunnerRuntime._compose_frame([base, overlay]) == [[1, 2], [1, 1]]


def test_frame_analysis_reports_changes() -> None:
    current = [[0, 1], [1, 1]]
    previous = [[0, 0], [1, 1]]
    analysis = RunnerRuntime._analyze_frame(current, previous)
    assert analysis["changed_cells"] == 1
    assert analysis["changed_pixels"] == [{"x": 1, "y": 0, "before": 0, "after": 1}]
    assert analysis["components"]
    assert analysis["color_histogram"][0]["count"] == 3
    assert "2×2" in analysis["summary"]


def test_click_candidates_are_bounded() -> None:
    frame = [[0 for _ in range(8)] for _ in range(8)]
    frame[4][6] = 3
    points = RunnerRuntime._candidate_clicks(frame)
    assert points
    assert all(0 <= x <= 63 and 0 <= y <= 63 for x, y in points)


def test_build_step_adds_decision_visibility_fields() -> None:
    runtime = RunnerRuntime()
    before = [[0, 1], [0, 0]]
    frame = [[0, 0], [0, 1]]
    current = SimpleNamespace(
        frame=[np.asarray(frame)],
        state=SimpleNamespace(name="NOT_FINISHED"),
        levels_completed=0,
        win_levels=1,
        available_actions=[1, 2],
        game_id="demo",
        guid="guid",
    )
    analysis = RunnerRuntime._analyze_frame(frame, before)
    agent_state = RunnerRuntime._agent_state(
        action_stats={},
        click_queue=deque(),
        used_clicks=set(),
        step_index=1,
        agent_name="Transform-Aware",
    )

    step = runtime._build_step(
        index=1,
        action_name="ACTION1",
        action_id=1,
        action_data={},
        before=before,
        current=current,
        analysis=analysis,
        candidates=[
            {
                "action": "ACTION1",
                "action_id": 1,
                "data": {},
                "score": 10.0,
                "evidence": "未尝试",
            }
        ],
        selected_reason="Transform-Aware exploit: 优先执行未充分探索动作。",
        duration_ms=12,
        reasoning={"schema": "arc3-runner.audit.v3"},
        agent_state=agent_state,
    )

    assert step["decision_gate"] == "probe"
    assert step["hypotheses"][0]["readable"] == "T(0,-1)"
    assert step["credibility"]["claimed"] > 0
    assert step["surprise"]["predicted_error_pixels"] >= 0
    assert step["imagination"]["predicted_frame"]
