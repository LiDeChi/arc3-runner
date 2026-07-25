from __future__ import annotations

from dataclasses import dataclass, field
from math import log, sqrt
from random import Random
from typing import Any
import copy

from arc3math.dsl import mdl
from arc3math.engine import GameSpec, oracle_bfs

TRAPS = [
    "permute",
    "conjugate_mirror",
    "conjugate_rotate",
    "diagonal",
    "region_split",
    "color_state",
    "regime_switch",
    "decoy_hint",
    "wall_ambiguity",
    "long_jump",
]

BASE_ACTIONS = {
    "A1": {"program": {"op": "translate", "dx": 0, "dy": -1}, "hint": "arrow_up"},
    "A2": {"program": {"op": "translate", "dx": 0, "dy": 1}, "hint": "arrow_down"},
    "A3": {"program": {"op": "translate", "dx": -1, "dy": 0}, "hint": "arrow_left"},
    "A4": {"program": {"op": "translate", "dx": 1, "dy": 0}, "hint": "arrow_right"},
}


def _border_grid(w: int, h: int) -> list[list[int]]:
    grid = [[0 for _ in range(w)] for _ in range(h)]
    for x in range(w):
        grid[0][x] = 1
        grid[h - 1][x] = 1
    for y in range(h):
        grid[y][0] = 1
        grid[y][w - 1] = 1
    return grid


def _base_spec(seed: int, template: str) -> dict[str, Any]:
    rng = Random(seed)
    w = h = rng.choice([8, 10, 12])
    grid = _border_grid(w, h)
    start = (1, h // 2)
    goal = (w - 2, h // 2)
    if template == "corridor":
        for y in range(1, h - 1):
            if y != h // 2:
                for x in range(2, w - 2):
                    if x % 3 == 0:
                        grid[y][x] = 1
    elif template == "two_rooms":
        wall_x = w // 2
        for y in range(1, h - 1):
            grid[y][wall_x] = 1
        grid[h // 2][wall_x] = 0
    elif template == "maze_small":
        for x in range(2, w - 2, 2):
            for y in range(1, h - 1):
                if y != (x + seed) % (h - 2) + 1:
                    grid[y][x] = 1
    elif template == "open_field":
        for _ in range(rng.randint(0, 3)):
            x = rng.randint(2, w - 3)
            y = rng.randint(1, h - 2)
            if (x, y) not in {start, goal}:
                grid[y][x] = 3
    elif template == "key_door":
        grid[h // 2][w // 2] = 8
        grid[h // 2][2] = 7
    grid[goal[1]][goal[0]] = 2
    return {
        "id": f"adv_{seed}_{template}",
        "size": {"w": w, "h": h},
        "tiles": grid,
        "entities": [{"id": "agent", "kind": "agent", "x": start[0], "y": start[1], "color": 4}],
        "actions": copy.deepcopy(BASE_ACTIONS),
        "win": {"type": "reach_goal"},
        "max_steps": 80,
        "meta": {"traps": [], "difficulty": 1.0, "seed": seed, "template": template},
    }


def _apply_trap(spec: dict[str, Any], trap: str, rng: Random) -> None:
    actions = spec["actions"]
    if trap == "permute":
        programs = [copy.deepcopy(actions[a]["program"]) for a in ("A1", "A2", "A3", "A4")]
        rng.shuffle(programs)
        for action, prog in zip(("A1", "A2", "A3", "A4"), programs):
            actions[action]["program"] = prog
    elif trap == "conjugate_mirror":
        axis = rng.choice(["h", "v"])
        for action in ("A1", "A2", "A3", "A4"):
            actions[action]["program"] = {"op": "conjugate", "g": {"op": "reflect", "axis": axis}, "f": actions[action]["program"]}
    elif trap == "conjugate_rotate":
        k = rng.choice([1, 2, 3])
        for action in ("A1", "A2", "A3", "A4"):
            actions[action]["program"] = {"op": "conjugate", "g": {"op": "rotate", "k": k}, "f": actions[action]["program"]}
    elif trap == "diagonal":
        actions["A1"]["program"] = {"op": "translate", "dx": rng.choice([-1, 1]), "dy": -1}
    elif trap == "region_split":
        split = spec["size"]["w"] // 2 - 1
        actions["A3"]["program"] = {
            "op": "conditional",
            "pred": {"pred": "in_region", "x0": 0, "y0": 0, "x1": split, "y1": spec["size"]["h"] - 1},
            "then": {"op": "translate", "dx": -1, "dy": 0},
            "else": {"op": "translate", "dx": 1, "dy": 0},
        }
        actions["A4"]["program"] = {
            "op": "conditional",
            "pred": {"pred": "in_region", "x0": 0, "y0": 0, "x1": split, "y1": spec["size"]["h"] - 1},
            "then": {"op": "translate", "dx": 1, "dy": 0},
            "else": {"op": "translate", "dx": -1, "dy": 0},
        }
    elif trap == "color_state":
        actions["A1"]["program"] = {
            "op": "conditional",
            "pred": {"pred": "agent_color", "c": 4},
            "then": {"op": "translate", "dx": 0, "dy": -1},
            "else": {"op": "translate", "dx": 0, "dy": 1},
        }
    elif trap == "regime_switch":
        sx, sy = 2, spec["size"]["h"] // 2
        spec["tiles"][sy][sx] = 4
        spec["regimes"] = [
            {
                "actions": {
                    "A1": {"program": {"op": "translate", "dx": 1, "dy": 0}, "hint": "arrow_up"},
                    "A4": {"program": {"op": "translate", "dx": 0, "dy": -1}, "hint": "arrow_right"},
                }
            }
        ]
    elif trap == "decoy_hint":
        hints = {"A1": "arrow_down", "A2": "arrow_up", "A3": "arrow_right", "A4": "arrow_left"}
        for action, hint in hints.items():
            actions[action]["hint"] = hint
        spec["tiles"][1][1] = 9
    elif trap == "wall_ambiguity":
        ax = spec["entities"][0]["x"]
        ay = spec["entities"][0]["y"]
        if ay > 1:
            spec["tiles"][ay - 1][ax] = 1
    elif trap == "long_jump":
        actions["A4"]["program"] = {"op": "translate", "dx": 2, "dy": 0}


def _valid_combo(combo: list[str]) -> bool:
    if "conjugate_mirror" in combo and "conjugate_rotate" in combo:
        return False
    if sum(1 for t in ("region_split", "color_state", "regime_switch") if t in combo) > 1:
        return False
    return True


def difficulty_score(spec: GameSpec | dict[str, Any]) -> float:
    data = spec.to_json() if isinstance(spec, GameSpec) else spec
    score = 3.0 * len(data.get("meta", {}).get("traps", []))
    base = BASE_ACTIONS
    for action in ("A1", "A2", "A3", "A4"):
        true_prog = data["actions"][action]["program"]
        score += max(0.0, mdl(true_prog) - mdl(base[action]["program"]))
    if data.get("regimes"):
        score += 2.0
    return round(score, 3)


def check_solvable(spec: GameSpec | dict[str, Any]) -> bool:
    game = GameSpec.from_json(spec) if isinstance(spec, dict) else spec
    return oracle_bfs(game, game.max_steps) is not None


def check_identifiable(spec: GameSpec | dict[str, Any]) -> bool:
    game = GameSpec.from_json(spec) if isinstance(spec, dict) else spec
    return check_solvable(game)


@dataclass
class Bandit:
    arms: list[tuple[str, ...]] = field(default_factory=list)
    c: float = 1.2
    counts: dict[tuple[str, ...], int] = field(default_factory=dict)
    rewards: dict[tuple[str, ...], float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.arms:
            singles = [(t,) for t in TRAPS]
            pairs = [
                ("permute", "wall_ambiguity"),
                ("permute", "decoy_hint"),
                ("conjugate_mirror", "decoy_hint"),
                ("conjugate_rotate", "long_jump"),
                ("diagonal", "wall_ambiguity"),
                ("region_split", "decoy_hint"),
                ("long_jump", "wall_ambiguity"),
                ("color_state", "decoy_hint"),
                ("regime_switch", "wall_ambiguity"),
                ("diagonal", "decoy_hint"),
            ]
            self.arms = singles + [p for p in pairs if _valid_combo(list(p))]
        for arm in self.arms:
            self.counts.setdefault(tuple(arm), 0)
            self.rewards.setdefault(tuple(arm), 0.0)

    def scores(self) -> dict[str, float]:
        total = sum(self.counts.values()) + 1
        out = {}
        for arm in self.arms:
            arm = tuple(arm)
            n = self.counts.get(arm, 0)
            avg = self.rewards.get(arm, 0.0) / n if n else 0.0
            bonus = float("inf") if n == 0 else self.c * sqrt(log(total) / n)
            out["+".join(arm)] = avg + bonus
        return out

    def choose(self) -> tuple[str, ...]:
        for arm in self.arms:
            if self.counts.get(tuple(arm), 0) == 0:
                return tuple(arm)
        return max((tuple(a) for a in self.arms), key=lambda arm: (self.scores()["+".join(arm)], "+".join(arm)))

    def update(self, arm: tuple[str, ...] | list[str], reward: float) -> None:
        key = tuple(arm)
        self.counts[key] = self.counts.get(key, 0) + 1
        self.rewards[key] = self.rewards.get(key, 0.0) + float(reward)

    def stats(self) -> list[dict[str, Any]]:
        scores = self.scores()
        rows = []
        for arm in self.arms:
            key = tuple(arm)
            plays = self.counts.get(key, 0)
            rows.append(
                {
                    "arm": "+".join(key),
                    "plays": plays,
                    "reward_mean": self.rewards.get(key, 0.0) / plays if plays else 0.0,
                    "ucb": scores["+".join(key)],
                }
            )
        return rows


def generate_game(seed: int = 0, bandit: Bandit | None = None, traps: list[str] | None = None) -> GameSpec:
    rng = Random(seed)
    templates = ["corridor", "two_rooms", "maze_small", "open_field", "key_door"]
    combo = traps or list((bandit.choose() if bandit else (TRAPS[seed % len(TRAPS)],)))
    for attempt in range(20):
        template = templates[(seed + attempt) % len(templates)]
        data = _base_spec(seed + attempt * 997, template)
        data["id"] = f"adv_{seed}_{attempt}"
        selected = [t for t in combo if t in TRAPS]
        if not _valid_combo(selected):
            selected = [selected[0]]
        for trap in selected:
            _apply_trap(data, trap, rng)
        data["meta"]["traps"] = selected
        game = GameSpec.from_json(data)
        oracle = oracle_bfs(game, game.max_steps)
        data["meta"]["oracle_len"] = len(oracle or [])
        data["meta"]["difficulty"] = difficulty_score(data)
        game = GameSpec.from_json(data)
        if oracle is not None:
            return game
    fallback = _base_spec(seed, "open_field")
    fallback["meta"]["traps"] = []
    fallback["meta"]["difficulty"] = difficulty_score(fallback)
    fallback["meta"]["oracle_len"] = len(oracle_bfs(GameSpec.from_json(fallback)) or [])
    return GameSpec.from_json(fallback)
