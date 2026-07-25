from arc3math.generator import Bandit, check_solvable, generate_game
from arc3math.engine import GameSpec


def blocked_spec():
    return {
        "id": "blocked",
        "size": {"w": 5, "h": 5},
        "tiles": [[1, 1, 1, 1, 1], [1, 0, 1, 2, 1], [1, 1, 1, 1, 1], [1, 0, 0, 0, 1], [1, 1, 1, 1, 1]],
        "entities": [{"id": "agent", "kind": "agent", "x": 1, "y": 1, "color": 4}],
        "actions": {
            "A1": {"program": {"op": "translate", "dx": 1, "dy": 0}, "hint": "arrow_right"},
            "A2": {"program": {"op": "translate", "dx": 0, "dy": 1}, "hint": "arrow_down"},
        },
        "win": {"type": "reach_goal"},
        "max_steps": 8,
        "meta": {"traps": [], "difficulty": 0, "seed": 0},
    }


def test_generate_seeded_games_solvable_and_diverse():
    traps = set()
    for seed in range(50):
        game = generate_game(seed=seed)
        assert check_solvable(game), game.id
        traps.update(game.meta.get("traps", []))
    assert len(traps) >= 6


def test_blocked_spec_unsolvable():
    assert not check_solvable(GameSpec.from_json(blocked_spec()))


def test_bandit_converges_to_high_reward_arm():
    bandit = Bandit(arms=[("low",), ("high",)])
    for _ in range(30):
        arm = bandit.choose()
        bandit.update(arm, 1.0 if arm == ("high",) else 0.0)
    assert bandit.choose() == ("high",)
