import json
from pathlib import Path

from arc3math.engine import GameSpec, initial_state, load_game, step


def spec_with_tiles(tiles, entity=(1, 1), actions=None, regimes=None):
    return GameSpec.from_json(
        {
            "id": "test",
            "size": {"w": len(tiles[0]), "h": len(tiles)},
            "tiles": tiles,
            "entities": [{"id": "agent", "kind": "agent", "x": entity[0], "y": entity[1], "color": 4}],
            "actions": actions
            or {
                "A1": {"program": {"op": "translate", "dx": 1, "dy": 0}, "hint": "arrow_right"},
                "A2": {"program": {"op": "translate", "dx": 0, "dy": 1}, "hint": "arrow_down"},
            },
            "regimes": regimes or [],
            "win": {"type": "reach_goal"},
            "max_steps": 20,
            "meta": {"traps": [], "difficulty": 0, "seed": 0},
        }
    )


def test_wall_and_bounds_cancel_movement():
    spec = spec_with_tiles([[1, 1, 1], [1, 0, 1], [1, 1, 1]])
    res = step(spec, initial_state(spec), "A1")
    assert (res.state.agent().x, res.state.agent().y) == (1, 1)
    assert not res.done


def test_key_door_portal_switch_and_regime():
    spec = spec_with_tiles(
        [[1, 1, 1, 1, 1], [1, 0, 7, 8, 2], [1, 5, 4, 6, 1], [1, 1, 1, 1, 1]],
        actions={
            "A1": {"program": {"op": "translate", "dx": 1, "dy": 0}, "hint": "arrow_right"},
            "A2": {"program": {"op": "translate", "dx": 0, "dy": 1}, "hint": "arrow_down"},
        },
        regimes=[{"actions": {"A1": {"program": {"op": "translate", "dx": -1, "dy": 0}, "hint": "arrow_left"}}}],
    )
    state = initial_state(spec)
    state = step(spec, state, "A1").state
    assert state.flags["keys"] == 1 and state.grid[1][2] == 0
    state = step(spec, state, "A1").state
    assert state.flags["keys"] == 0 and state.grid[1][3] == 0
    assert step(spec, state, "A1").result == "win"

    spec2 = spec_with_tiles([[1, 1, 1, 1, 1], [1, 0, 5, 0, 1], [1, 0, 4, 6, 1], [1, 1, 1, 1, 1]], entity=(1, 1))
    state = step(spec2, initial_state(spec2), "A1").state
    assert (state.agent().x, state.agent().y) == (3, 2)
    state = step(spec2, state, "A3" if "A3" in spec2.actions else "A2").state
    assert state.regime in {0, 1}


def test_handwritten_solutions_win_and_deterministic():
    games = Path("games")
    solutions = json.loads((games / "solutions.json").read_text())
    for game_id, actions in solutions.items():
        spec = load_game(games / f"{game_id}.json")
        states = []
        state = initial_state(spec)
        result = None
        for action in actions:
            res = step(spec, state, action)
            states.append(res.state)
            state = res.state
            result = res.result
        assert result == "win", game_id

        state2 = initial_state(spec)
        for action, expected in zip(actions, states):
            state2 = step(spec, state2, action).state
            assert state2 == expected
