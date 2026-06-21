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
