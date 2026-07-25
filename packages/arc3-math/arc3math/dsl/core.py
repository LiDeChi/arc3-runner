from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from math import exp
from typing import Any, Iterable
import copy
import json

Grid = list[list[int]]


@dataclass(frozen=True)
class Entity:
    id: str
    kind: str
    x: int
    y: int
    color: int = 4

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Entity":
        return cls(
            id=str(data["id"]),
            kind=str(data.get("kind", "agent")),
            x=int(data["x"]),
            y=int(data["y"]),
            color=int(data.get("color", 4)),
        )

    def to_json(self) -> dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "x": self.x, "y": self.y, "color": self.color}


@dataclass(frozen=True)
class State:
    grid: Grid
    entities: tuple[Entity, ...]
    step_count: int = 0
    regime: int = 0
    flags: dict[str, Any] = field(default_factory=dict)

    def agent(self) -> Entity:
        for ent in self.entities:
            if ent.kind == "agent" or ent.id == "agent":
                return ent
        raise ValueError("state has no agent entity")

    @property
    def w(self) -> int:
        return len(self.grid[0]) if self.grid else 0

    @property
    def h(self) -> int:
        return len(self.grid)

    def replace_agent(self, x: int, y: int, color: int | None = None) -> "State":
        agent = self.agent()
        entities = []
        for ent in self.entities:
            if ent.id == agent.id:
                entities.append(Entity(ent.id, ent.kind, x, y, ent.color if color is None else color))
            else:
                entities.append(ent)
        return State(copy_grid(self.grid), tuple(entities), self.step_count, self.regime, copy.deepcopy(self.flags))

    def with_grid(self, grid: Grid) -> "State":
        return State(copy_grid(grid), self.entities, self.step_count, self.regime, copy.deepcopy(self.flags))

    def with_runtime(self, *, step_count: int | None = None, regime: int | None = None, flags: dict[str, Any] | None = None) -> "State":
        return State(
            copy_grid(self.grid),
            self.entities,
            self.step_count if step_count is None else step_count,
            self.regime if regime is None else regime,
            copy.deepcopy(self.flags if flags is None else flags),
        )


def copy_grid(grid: Grid) -> Grid:
    return [list(row) for row in grid]


def state_from_json(data: dict[str, Any]) -> State:
    return State(
        grid=[[int(v) for v in row] for row in data["grid"]],
        entities=tuple(Entity.from_json(e) for e in data.get("entities", [])),
        step_count=int(data.get("step_count", 0)),
        regime=int(data.get("regime", 0)),
        flags=copy.deepcopy(data.get("flags", {})),
    )


def state_to_json(state: State) -> dict[str, Any]:
    return {
        "grid": copy_grid(state.grid),
        "entities": [e.to_json() for e in state.entities],
        "step_count": state.step_count,
        "regime": state.regime,
        "flags": copy.deepcopy(state.flags),
    }


def render_observation(state: State, include_entities: bool = True) -> Grid:
    grid = copy_grid(state.grid)
    if include_entities:
        for ent in state.entities:
            if 0 <= ent.x < state.w and 0 <= ent.y < state.h:
                grid[ent.y][ent.x] = int(ent.color)
    return grid


def grids_equal(a: Grid, b: Grid) -> bool:
    return len(a) == len(b) and all(row_a == row_b for row_a, row_b in zip(a, b))


def match_ratio(a: Grid, b: Grid) -> float:
    if not a or not b or len(a) != len(b) or len(a[0]) != len(b[0]):
        return 0.0
    total = len(a) * len(a[0])
    same = 0
    for y, row in enumerate(a):
        for x, value in enumerate(row):
            if value == b[y][x]:
                same += 1
    return same / total


def _agent_pos_after_geom(op: dict[str, Any], x: int, y: int, w: int, h: int) -> tuple[int, int]:
    name = op["op"]
    if name == "identity":
        return x, y
    if name == "translate":
        return x + int(op.get("dx", 0)), y + int(op.get("dy", 0))
    if name == "rotate":
        k = int(op["k"]) % 4
        if k == 0:
            return x, y
        if k == 1:
            return h - 1 - y, x
        if k == 2:
            return w - 1 - x, h - 1 - y
        return y, w - 1 - x
    if name == "reflect":
        axis = op["axis"]
        if axis == "h":
            return x, h - 1 - y
        if axis == "v":
            return w - 1 - x, y
        if axis == "d":
            return y, x
        if axis == "a":
            return w - 1 - y, h - 1 - x
    raise ValueError(f"unsupported geometry op: {name}")


def transform_vector(g: dict[str, Any], dx: int, dy: int) -> tuple[int, int]:
    if g["op"] == "rotate":
        k = int(g["k"]) % 4
        if k == 0:
            return dx, dy
        if k == 1:
            return -dy, dx
        if k == 2:
            return -dx, -dy
        return dy, -dx
    if g["op"] == "reflect":
        axis = g["axis"]
        if axis == "h":
            return dx, -dy
        if axis == "v":
            return -dx, dy
        if axis == "d":
            return dy, dx
        if axis == "a":
            return -dy, -dx
    raise ValueError("conjugate g must be rotate or reflect")


def _rotate_grid_clockwise(grid: Grid, k: int) -> Grid:
    k %= 4
    out = copy_grid(grid)
    for _ in range(k):
        out = [list(row) for row in zip(*out[::-1])]
    return out


def _reflect_grid(grid: Grid, axis: str) -> Grid:
    if axis == "h":
        return copy_grid(list(reversed(grid)))
    if axis == "v":
        return [list(reversed(row)) for row in grid]
    if axis == "d":
        return [list(row) for row in zip(*grid)]
    if axis == "a":
        return [list(row) for row in zip(*grid[::-1])][::-1]
    raise ValueError(f"unknown reflect axis: {axis}")


def _apply_world_geom(prog: dict[str, Any], state: State) -> State:
    if prog["op"] == "identity":
        return state
    if prog["op"] == "rotate":
        k = int(prog["k"]) % 4
        new_grid = _rotate_grid_clockwise(state.grid, k)
        ents = []
        for ent in state.entities:
            nx, ny = _agent_pos_after_geom({"op": "rotate", "k": k}, ent.x, ent.y, state.w, state.h)
            ents.append(Entity(ent.id, ent.kind, nx, ny, ent.color))
        return State(new_grid, tuple(ents), state.step_count, state.regime, copy.deepcopy(state.flags))
    if prog["op"] == "reflect":
        axis = prog["axis"]
        new_grid = _reflect_grid(state.grid, axis)
        ents = []
        for ent in state.entities:
            nx, ny = _agent_pos_after_geom({"op": "reflect", "axis": axis}, ent.x, ent.y, state.w, state.h)
            ents.append(Entity(ent.id, ent.kind, nx, ny, ent.color))
        return State(new_grid, tuple(ents), state.step_count, state.regime, copy.deepcopy(state.flags))
    if prog["op"] == "color_map":
        cmap = {int(k): int(v) for k, v in prog.get("map", {}).items()}
        return state.with_grid([[cmap.get(v, v) for v in row] for row in state.grid])
    raise ValueError(f"unsupported world op: {prog['op']}")


def _pred_true(pred: dict[str, Any], state: State) -> bool:
    agent = state.agent()
    name = pred["pred"]
    if name == "in_region":
        return int(pred["x0"]) <= agent.x <= int(pred["x1"]) and int(pred["y0"]) <= agent.y <= int(pred["y1"])
    if name == "agent_color":
        return agent.color == int(pred["c"])
    if name == "tile_under":
        return state.grid[agent.y][agent.x] == int(pred["t"])
    if name == "step_mod":
        return state.step_count % int(pred["k"]) == int(pred["r"])
    if name == "regime_is":
        return state.regime == int(pred["i"])
    raise ValueError(f"unsupported pred: {name}")


def apply_program(prog: dict[str, Any], state: State | dict[str, Any]) -> State:
    if isinstance(state, dict):
        state = state_from_json(state)
    prog = copy.deepcopy(prog)
    op = prog["op"]
    scope = prog.get("scope", "agent")

    if op == "compose":
        out = state
        for child in prog.get("fs", []):
            out = apply_program(child, out)
        return out
    if op == "conditional":
        return apply_program(prog["then"] if _pred_true(prog["pred"], state) else prog["else"], state)
    if op == "conjugate":
        f = prog["f"]
        if f["op"] != "translate":
            raise ValueError("v1 conjugate requires translate f")
        dx, dy = transform_vector(prog["g"], int(f["dx"]), int(f["dy"]))
        return apply_program({"op": "translate", "dx": dx, "dy": dy, "scope": scope}, state)

    if scope == "world":
        return _apply_world_geom(prog, state)

    if op == "color_map":
        return state
    agent = state.agent()
    nx, ny = _agent_pos_after_geom(prog, agent.x, agent.y, state.w, state.h)
    return state.replace_agent(nx, ny)


def _pred_cost(pred: dict[str, Any]) -> float:
    return 1.5 if pred["pred"] == "step_mod" else 1.0


def mdl(prog: dict[str, Any]) -> float:
    op = prog["op"]
    if op == "identity":
        return 1.0
    if op == "translate":
        dx = abs(int(prog.get("dx", 0)))
        dy = abs(int(prog.get("dy", 0)))
        norm = dx + dy
        return 1.0 if norm <= 1 else 1.0 + 0.5 * (norm - 1)
    if op in {"rotate", "reflect"}:
        return 2.0
    if op == "color_map":
        return 2.0 + 0.5 * len(prog.get("map", {}))
    if op == "compose":
        return 0.5 + sum(mdl(f) for f in prog.get("fs", []))
    if op == "conjugate":
        return 1.5 + mdl(prog["g"]) + mdl(prog["f"])
    if op == "conditional":
        return 2.0 + _pred_cost(prog["pred"]) + mdl(prog["then"]) + mdl(prog["else"])
    raise ValueError(f"unsupported op: {op}")


def prior_distribution(programs: Iterable[dict[str, Any]]) -> list[float]:
    weights = [exp(-mdl(p)) for p in programs]
    total = sum(weights) or 1.0
    return [w / total for w in weights]


def prior(prog: dict[str, Any]) -> float:
    return exp(-mdl(prog))


def normalize_program(prog: dict[str, Any]) -> dict[str, Any]:
    if prog["op"] == "conjugate":
        f = prog["f"]
        dx, dy = transform_vector(prog["g"], int(f["dx"]), int(f["dy"]))
        return {"op": "translate", "dx": dx, "dy": dy}
    return copy.deepcopy(prog)


def program_to_math(prog: dict[str, Any]) -> str:
    op = prog["op"]
    if op == "identity":
        return "I"
    if op == "translate":
        return f"T({int(prog.get('dx', 0))},{int(prog.get('dy', 0))})"
    if op == "rotate":
        return f"R_{int(prog['k'])}"
    if op == "reflect":
        return f"M_{prog['axis']}"
    if op == "color_map":
        items = ",".join(f"{k}->{v}" for k, v in sorted(prog.get("map", {}).items(), key=lambda kv: int(kv[0])))
        return f"C({items})"
    if op == "compose":
        return " ∘ ".join(program_to_math(f) for f in prog.get("fs", []))
    if op == "conjugate":
        g = program_to_math(prog["g"])
        return f"{g} ∘ {program_to_math(prog['f'])} ∘ {g}^-1"
    if op == "conditional":
        pred = prog["pred"]
        pname = pred["pred"]
        if pname == "in_region":
            ps = f"in([{pred['x0']},{pred['y0']}],[{pred['x1']},{pred['y1']}])"
        elif pname == "agent_color":
            ps = f"color={pred['c']}"
        elif pname == "tile_under":
            ps = f"tile={pred['t']}"
        elif pname == "step_mod":
            ps = f"step%{pred['k']}={pred['r']}"
        else:
            ps = f"regime={pred['i']}"
        return f"if {ps} then {program_to_math(prog['then'])} else {program_to_math(prog['else'])}"
    raise ValueError(f"unsupported op: {op}")


def _probe_states() -> list[State]:
    states: list[State] = []
    grid = [[0 for _ in range(5)] for _ in range(5)]
    positions = [(1, 1), (2, 1), (3, 2), (1, 3)]
    colors = [4, 5]
    steps = [0, 1]
    for idx, (x, y) in enumerate(positions):
        for color in colors:
            for step in steps:
                g = copy_grid(grid)
                if idx % 2 == 0:
                    g[2][2] = 9
                states.append(State(g, (Entity("agent", "agent", x, y, color),), step_count=step, regime=idx % 2, flags={}))
                if len(states) == 16:
                    return states
    return states


def extensional_key(prog: dict[str, Any], states: Iterable[State] | None = None) -> tuple[str, ...]:
    return tuple(
        json.dumps(state_to_json(apply_program(prog, s)), sort_keys=True, separators=(",", ":"))
        for s in (states or _probe_states())
    )


def _candidate_programs(scope: str) -> list[dict[str, Any]]:
    simple: list[dict[str, Any]] = [{"op": "identity"}]
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            if dx == 0 and dy == 0:
                continue
            simple.append({"op": "translate", "dx": dx, "dy": dy})
    simple.extend({"op": "rotate", "k": k} for k in (1, 2, 3))
    simple.extend({"op": "reflect", "axis": axis} for axis in ("h", "v", "d", "a"))
    if scope == "world":
        simple.extend(
            [
                {"op": "color_map", "map": {"1": 2}},
                {"op": "color_map", "map": {"2": 1}},
                {"op": "color_map", "map": {"3": 0}},
            ]
        )

    unit = [
        {"op": "identity"},
        {"op": "translate", "dx": 0, "dy": -1},
        {"op": "translate", "dx": 0, "dy": 1},
        {"op": "translate", "dx": -1, "dy": 0},
        {"op": "translate", "dx": 1, "dy": 0},
    ]
    diagonals = [
        {"op": "translate", "dx": -1, "dy": -1},
        {"op": "translate", "dx": 1, "dy": -1},
        {"op": "translate", "dx": -1, "dy": 1},
        {"op": "translate", "dx": 1, "dy": 1},
    ]
    geom = [{"op": "rotate", "k": k} for k in (1, 2, 3)] + [{"op": "reflect", "axis": a} for a in ("h", "v", "d", "a")]
    candidates = list(simple)
    candidates.extend({"op": "compose", "fs": [a, b]} for a in unit + diagonals for b in unit + diagonals)
    candidates.extend({"op": "compose", "fs": [a, b, c]} for a in unit for b in unit for c in unit)
    candidates.extend({"op": "conjugate", "g": g, "f": f} for g in geom for f in unit[1:] + diagonals)

    predicates = [
        {"pred": "in_region", "x0": 0, "y0": 0, "x1": 2, "y1": 4},
        {"pred": "in_region", "x0": 3, "y0": 0, "x1": 4, "y1": 4},
        {"pred": "agent_color", "c": 4},
        {"pred": "agent_color", "c": 5},
        {"pred": "tile_under", "t": 9},
        {"pred": "step_mod", "k": 2, "r": 0},
        {"pred": "regime_is", "i": 1},
    ]
    branch_terms = unit + diagonals
    for pred in predicates:
        for then in branch_terms:
            for els in branch_terms:
                if then != els:
                    candidates.append({"op": "conditional", "pred": pred, "then": then, "else": els})
    return candidates


@lru_cache(maxsize=16)
def _enumerate_programs_cached(max_mdl: float, scope: str) -> tuple[str, ...]:
    probes = _probe_states()
    by_ext: dict[tuple[str, ...], dict[str, Any]] = {}
    for prog in _candidate_programs(scope):
        if prog.get("scope") != "world" and scope == "world":
            prog = {**prog, "scope": "world"}
        cost = mdl(prog)
        if cost > max_mdl:
            continue
        try:
            key = extensional_key(prog, probes)
        except Exception:
            continue
        old = by_ext.get(key)
        if old is None or (cost, program_to_math(prog)) < (mdl(old), program_to_math(old)):
            by_ext[key] = copy.deepcopy(prog)
    ordered = sorted(by_ext.values(), key=lambda p: (mdl(p), program_to_math(p)))
    return tuple(json.dumps(p, sort_keys=True, separators=(",", ":")) for p in ordered)


def enumerate_programs(max_mdl: float = 8.0, scope: str = "agent") -> list[dict[str, Any]]:
    return [json.loads(s) for s in _enumerate_programs_cached(float(max_mdl), scope)]
