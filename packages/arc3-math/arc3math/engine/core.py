from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from collections import deque
import copy
import json

from arc3math.dsl import Entity, State, apply_program, render_observation, state_from_json, state_to_json

ACTIONS = ["RESET", "A1", "A2", "A3", "A4", "A5"]
TILE_NAMES = {
    0: "empty",
    1: "wall",
    2: "goal",
    3: "lava",
    4: "switch",
    5: "portal_a",
    6: "portal_b",
    7: "key",
    8: "door",
    9: "hint_decor",
}


@dataclass(frozen=True)
class GameSpec:
    id: str
    size: dict[str, int]
    tiles: list[list[int]]
    entities: tuple[Entity, ...]
    actions: dict[str, dict[str, Any]]
    regimes: tuple[dict[str, Any], ...]
    win: dict[str, Any]
    max_steps: int
    meta: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "GameSpec":
        return cls(
            id=str(data["id"]),
            size={"w": int(data["size"]["w"]), "h": int(data["size"]["h"])},
            tiles=[[int(v) for v in row] for row in data["tiles"]],
            entities=tuple(Entity.from_json(e) for e in data.get("entities", [])),
            actions=copy.deepcopy(data.get("actions", {})),
            regimes=tuple(copy.deepcopy(data.get("regimes", []))),
            win=copy.deepcopy(data.get("win", {"type": "reach_goal"})),
            max_steps=int(data.get("max_steps", 100)),
            meta=copy.deepcopy(data.get("meta", {})),
        )

    def to_json(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "size": dict(self.size),
            "tiles": [list(row) for row in self.tiles],
            "entities": [e.to_json() for e in self.entities],
            "actions": copy.deepcopy(self.actions),
            "regimes": copy.deepcopy(list(self.regimes)),
            "win": copy.deepcopy(self.win),
            "max_steps": self.max_steps,
            "meta": copy.deepcopy(self.meta),
        }


@dataclass(frozen=True)
class StepResult:
    state: State
    done: bool
    result: str | None

    def observation(self) -> dict[str, Any]:
        return {"grid": render_observation(self.state), "done": self.done, "result": self.result}


class EnvAdapter(Protocol):
    def reset(self) -> dict[str, Any]: ...

    def step(self, action: str) -> dict[str, Any]: ...

    def action_space(self) -> list[str]: ...


def load_game(path: str | Path) -> GameSpec:
    with Path(path).open("r", encoding="utf-8") as fh:
        return GameSpec.from_json(json.load(fh))


def initial_state(spec: GameSpec | dict[str, Any]) -> State:
    if isinstance(spec, dict):
        spec = GameSpec.from_json(spec)
    return State([list(row) for row in spec.tiles], spec.entities, step_count=0, regime=0, flags={})


def _program_for_action(spec: GameSpec, state: State, action: str) -> dict[str, Any]:
    if action == "RESET":
        return {"op": "identity"}
    base = copy.deepcopy(spec.actions[action])
    if state.regime > 0 and state.regime - 1 < len(spec.regimes):
        override = spec.regimes[state.regime - 1].get("actions", {}).get(action)
        if override is not None:
            base = copy.deepcopy(override)
    return copy.deepcopy(base["program"])


def _find_agent(state: State) -> Entity:
    return state.agent()


def _tile_at(state: State, x: int, y: int) -> int | None:
    if 0 <= x < state.w and 0 <= y < state.h:
        return int(state.grid[y][x])
    return None


def _set_tile(grid: list[list[int]], x: int, y: int, value: int) -> list[list[int]]:
    out = [list(row) for row in grid]
    out[y][x] = value
    return out


def _portal_target(state: State, tile: int) -> tuple[int, int] | None:
    target = 6 if tile == 5 else 5
    for y, row in enumerate(state.grid):
        for x, value in enumerate(row):
            if value == target:
                return x, y
    return None


def check_win(spec: GameSpec, state: State) -> bool:
    agent = _find_agent(state)
    if spec.win.get("type") == "reach_goal":
        return _tile_at(state, agent.x, agent.y) == 2
    if spec.win.get("type") == "collect_keys":
        return int(state.flags.get("keys_collected", 0)) >= int(spec.win.get("n", 1))
    return False


def transition_with_program(spec: GameSpec | dict[str, Any], state: State, program: dict[str, Any]) -> StepResult:
    if isinstance(spec, dict):
        spec = GameSpec.from_json(spec)
    before = state
    intended = apply_program(program, before)
    intended_agent = intended.agent()
    old_agent = before.agent()
    flags = copy.deepcopy(before.flags)
    grid = [list(row) for row in before.grid]
    nx, ny = intended_agent.x, intended_agent.y
    tile = _tile_at(before, nx, ny)
    blocked = tile is None or tile == 1 or (tile == 8 and int(flags.get("keys", 0)) <= 0)
    if blocked:
        nx, ny = old_agent.x, old_agent.y
        tile = _tile_at(before, nx, ny)

    moved = before.replace_agent(nx, ny)
    result: str | None = None
    done = False

    if not blocked and tile == 3:
        result = "lose"
        done = True
    elif not blocked and tile == 5:
        target = _portal_target(before, 5)
        if target:
            moved = moved.replace_agent(*target)
    elif not blocked and tile == 6:
        target = _portal_target(before, 6)
        if target:
            moved = moved.replace_agent(*target)
    elif not blocked and tile == 7:
        flags["keys"] = int(flags.get("keys", 0)) + 1
        flags["keys_collected"] = int(flags.get("keys_collected", 0)) + 1
        grid = _set_tile(grid, nx, ny, 0)
    elif not blocked and tile == 8:
        flags["keys"] = int(flags.get("keys", 0)) - 1
        grid = _set_tile(grid, nx, ny, 0)
    elif not blocked and tile == 4:
        moved = moved.with_runtime(regime=(before.regime + 1) % (len(spec.regimes) + 1))

    moved = State(grid, moved.entities, before.step_count, moved.regime, flags)
    if check_win(spec, moved):
        result = "win"
        done = True

    moved = moved.with_runtime(step_count=before.step_count + 1)
    if not done and moved.step_count > spec.max_steps:
        result = "timeout"
        done = True

    if program.get("scope") == "world":
        moved = apply_program(program, moved)
    return StepResult(moved, done, result)


def step(spec: GameSpec | dict[str, Any], state: State | dict[str, Any], action: str) -> StepResult:
    if isinstance(spec, dict):
        spec = GameSpec.from_json(spec)
    if isinstance(state, dict):
        state = state_from_json(state)
    if action == "RESET":
        return StepResult(initial_state(spec), False, None)
    if action not in spec.actions:
        raise KeyError(f"unknown action {action}")
    return transition_with_program(spec, state, _program_for_action(spec, state, action))


def _state_key(state: State) -> str:
    agent = state.agent()
    return json.dumps(
        {
            "x": agent.x,
            "y": agent.y,
            "grid": state.grid,
            "regime": state.regime,
            "flags": state.flags,
            "step": state.step_count,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def oracle_bfs(spec: GameSpec, max_depth: int | None = None, start: State | None = None) -> list[str] | None:
    limit = max_depth if max_depth is not None else spec.max_steps
    start_state = start or initial_state(spec)
    queue = deque([(start_state, [])])
    seen = {_state_key(start_state)}
    actions = [a for a in ("A1", "A2", "A3", "A4", "A5") if a in spec.actions]
    while queue:
        state, path = queue.popleft()
        if len(path) > limit:
            continue
        if check_win(spec, state):
            return path
        for action in actions:
            result = step(spec, state, action)
            key = _state_key(result.state)
            if key in seen:
                continue
            next_path = path + [action]
            if result.result == "win":
                return next_path
            if result.done:
                continue
            seen.add(key)
            queue.append((result.state, next_path))
    return None


class LocalEnv:
    def __init__(self, spec: GameSpec | dict[str, Any]):
        self.spec = GameSpec.from_json(spec) if isinstance(spec, dict) else spec
        self.state = initial_state(self.spec)
        self.done = False
        self.result: str | None = None

    def reset(self) -> dict[str, Any]:
        self.state = initial_state(self.spec)
        self.done = False
        self.result = None
        return self.observation()

    def observation(self) -> dict[str, Any]:
        return {
            "grid": render_observation(self.state),
            "state": state_to_json(self.state),
            "done": self.done,
            "result": self.result,
        }

    def step(self, action: str) -> dict[str, Any]:
        res = step(self.spec, self.state, action)
        self.state = res.state
        self.done = res.done
        self.result = res.result
        return self.observation()

    def action_space(self) -> list[str]:
        return [a for a in ("A1", "A2", "A3", "A4", "A5") if a in self.spec.actions]
