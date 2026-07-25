from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, log
from typing import Any
from collections import Counter, deque
import copy
import json

from arc3math.dsl import (
    State,
    enumerate_programs,
    extensional_key,
    grids_equal,
    match_ratio,
    mdl,
    program_to_math,
    render_observation,
    state_to_json,
)
from arc3math.engine import GameSpec, StepResult, check_win, oracle_bfs, transition_with_program


@dataclass
class AgentConfig:
    init_mdl: float = 4.0
    max_mdl: float = 8.0
    beta: float = 20.0
    epsilon: float = 1e-6
    tau: float = 0.55
    plan_depth: int = 40
    max_steps: int = 100
    oracle_entities: bool = False
    oracle_fallback: bool = True
    seed: int = 0


@dataclass
class Trace:
    episode_id: str
    game_id: str
    events: list[dict[str, Any]] = field(default_factory=list)
    calibration: list[tuple[float, bool]] = field(default_factory=list)
    result: str | None = None
    steps: int = 0

    def log(self, step_idx: int, type_: str, payload: dict[str, Any]) -> None:
        self.events.append(
            {
                "episode_id": self.episode_id,
                "step_idx": step_idx,
                "type": type_,
                "payload": copy.deepcopy(payload),
            }
        )

    def summary(self) -> dict[str, Any]:
        wrong = [(conf, ok) for conf, ok in self.calibration if not ok]
        avg_conf = sum(conf for conf, _ in self.calibration) / len(self.calibration) if self.calibration else 0.0
        overconf = sum(conf for conf, _ in wrong) / len(self.calibration) if self.calibration else 0.0
        return {
            "result": self.result,
            "steps": self.steps,
            "avg_conf": avg_conf,
            "overconf": overconf,
            "probe_steps": sum(1 for e in self.events if e["type"] == "action_taken" and e["payload"].get("intent") == "probe"),
            "revisions": sum(1 for e in self.events if e["type"] == "belief_revision"),
            "ece": ece_score(self.calibration),
        }


def _logsumexp(logs: list[float]) -> float:
    if not logs:
        return 0.0
    m = max(logs)
    if m < -1e100:
        return m
    return m + log(sum(exp(v - m) for v in logs))


def _normalise(items: list[dict[str, Any]]) -> None:
    denom = _logsumexp([it["log_w"] for it in items])
    for it in items:
        it["prob"] = exp(it["log_w"] - denom) if denom > -1e100 else 1.0 / max(1, len(items))


def _expected_program_for_hint(hint: str | None, action: str) -> dict[str, Any]:
    by_hint = {
        "arrow_up": {"op": "translate", "dx": 0, "dy": -1},
        "arrow_down": {"op": "translate", "dx": 0, "dy": 1},
        "arrow_left": {"op": "translate", "dx": -1, "dy": 0},
        "arrow_right": {"op": "translate", "dx": 1, "dy": 0},
    }
    by_action = {
        "A1": {"op": "translate", "dx": 0, "dy": -1},
        "A2": {"op": "translate", "dx": 0, "dy": 1},
        "A3": {"op": "translate", "dx": -1, "dy": 0},
        "A4": {"op": "translate", "dx": 1, "dy": 0},
    }
    return by_hint.get(hint or "", by_action.get(action, {"op": "identity"}))


def _same_extension(a: dict[str, Any], b: dict[str, Any]) -> bool:
    try:
        return extensional_key(a) == extensional_key(b)
    except Exception:
        return json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def _action_bias(spec: GameSpec, action: str, prog: dict[str, Any]) -> float:
    expected = _expected_program_for_hint(spec.actions.get(action, {}).get("hint"), action)
    if _same_extension(prog, expected):
        return 4.0
    return 0.0


def _init_belief(spec: GameSpec, action: str, cfg: AgentConfig, max_mdl: float | None = None) -> dict[str, Any]:
    programs = enumerate_programs(cfg.init_mdl if max_mdl is None else max_mdl)
    items = [{"program": p, "log_w": -mdl(p) + _action_bias(spec, action, p), "prob": 0.0} for p in programs]
    _normalise(items)
    return {"items": items, "history": [], "revisions": 0}


def _rebuild_belief(spec: GameSpec, action: str, belief: dict[str, Any], cfg: AgentConfig) -> None:
    items = [{"program": p, "log_w": -mdl(p) + _action_bias(spec, action, p), "prob": 0.0} for p in enumerate_programs(cfg.max_mdl)]
    for before, after_grid in belief["history"]:
        for item in items:
            pred = transition_with_program(spec, before, item["program"]).state
            item["log_w"] += cfg.beta * log(max(match_ratio(render_observation(pred), after_grid), cfg.epsilon))
    belief["items"] = items
    _normalise(belief["items"])


def _prediction_groups(spec: GameSpec, state: State, belief: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    groups: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for item in belief["items"]:
        predicted = transition_with_program(spec, state, item["program"]).state
        grid = render_observation(predicted)
        key = json.dumps(grid, sort_keys=True, separators=(",", ":"))
        groups[key] = groups.get(key, 0.0) + item["prob"]
        rows.append({"item": item, "state": predicted, "grid": grid, "key": key})
    top_item = max(rows, key=lambda r: r["item"]["prob"])
    top_key = top_item["key"]
    return {
        "program": top_item["item"]["program"],
        "math": program_to_math(top_item["item"]["program"]),
        "state": top_item["state"],
        "grid": top_item["grid"],
        "conf": groups.get(top_key, top_item["item"]["prob"]),
        "prob": top_item["item"]["prob"],
    }, rows


def _hypotheses_payload(spec: GameSpec, beliefs: dict[str, dict[str, Any]]) -> dict[str, Any]:
    actions = []
    for action in sorted(beliefs):
        top = sorted(beliefs[action]["items"], key=lambda item: item["prob"], reverse=True)[:3]
        actions.append(
            {
                "action": action,
                "items": [
                    {"program": copy.deepcopy(item["program"]), "math": program_to_math(item["program"]), "prob": item["prob"]}
                    for item in top
                ],
            }
        )
    return {"actions": actions}


def _state_key(state: State) -> str:
    agent = state.agent()
    return json.dumps(
        {"x": agent.x, "y": agent.y, "grid": state.grid, "regime": state.regime, "flags": state.flags},
        sort_keys=True,
        separators=(",", ":"),
    )


def imagine_plan(spec: GameSpec, state: State, beliefs: dict[str, dict[str, Any]], cfg: AgentConfig) -> dict[str, Any]:
    actions = sorted(beliefs)
    maps = {a: _prediction_groups(spec, state, beliefs[a])[0] for a in actions}
    top_programs = {a: maps[a]["program"] for a in actions}
    queue = deque([(state, [], [render_observation(state)])])
    seen = {_state_key(state)}
    while queue:
        current, path, grids = queue.popleft()
        if check_win(spec, current):
            used = set(path)
            risk = min((maps[a]["conf"] for a in used), default=1.0)
            return {"intent": "goal", "actions": path, "imagined_grids": grids[1:], "risk": risk}
        if len(path) >= cfg.plan_depth:
            continue
        for action in actions:
            res = transition_with_program(spec, current, top_programs[action])
            if res.result == "lose":
                continue
            key = _state_key(res.state)
            if key in seen:
                continue
            seen.add(key)
            queue.append((res.state, path + [action], grids + [render_observation(res.state)]))
    return {"intent": "probe", "actions": [], "imagined_grids": [], "risk": 0.0}


def _safe_score(spec: GameSpec, state: State, belief: dict[str, Any]) -> float:
    sample = sorted(belief["items"], key=lambda item: item["prob"], reverse=True)[:5]
    for item in sample:
        res = transition_with_program(spec, state, item["program"])
        agent = res.state.agent()
        tile = res.state.grid[agent.y][agent.x]
        if tile == 3:
            return 0.1
    return 1.0


def design_probe(spec: GameSpec, state: State, beliefs: dict[str, dict[str, Any]], action_counts: Counter[str]) -> str:
    best: tuple[float, str] | None = None
    for action, belief in sorted(beliefs.items()):
        top = sorted(belief["items"], key=lambda item: item["prob"], reverse=True)[:2]
        if len(top) < 2:
            disagreement = 0.0
        else:
            g1 = render_observation(transition_with_program(spec, state, top[0]["program"]).state)
            g2 = render_observation(transition_with_program(spec, state, top[1]["program"]).state)
            disagreement = 1.0 - match_ratio(g1, g2)
        pred = _prediction_groups(spec, state, belief)[0]
        score = disagreement * (1.0 - pred["conf"]) * _safe_score(spec, state, belief)
        rank = (score, action)
        if best is None or rank > best:
            best = rank
    if best and best[0] > 0:
        return best[1]
    min_count = min(action_counts.get(a, 0) for a in beliefs)
    return sorted(a for a in beliefs if action_counts.get(a, 0) == min_count)[0]


def _update_belief(
    spec: GameSpec,
    action: str,
    belief: dict[str, Any],
    before: State,
    after: State,
    cfg: AgentConfig,
) -> dict[str, Any]:
    actual_grid = render_observation(after)
    old_top, predictions = _prediction_groups(spec, before, belief)
    exact_mass = sum(row["item"]["prob"] for row in predictions if grids_equal(row["grid"], actual_grid))
    old_correct = grids_equal(old_top["grid"], actual_grid)
    for row in predictions:
        m = match_ratio(row["grid"], actual_grid)
        row["item"]["log_w"] += cfg.beta * log(max(m, cfg.epsilon))
    _normalise(belief["items"])
    belief["history"].append((before, actual_grid))

    revision = None
    if (not old_correct and old_top["conf"] >= 0.45) or exact_mass < 1e-9:
        old = old_top["math"]
        _rebuild_belief(spec, action, belief, cfg)
        belief["revisions"] += 1
        new_top = sorted(belief["items"], key=lambda item: item["prob"], reverse=True)[0]
        revision = {
            "action": action,
            "old_top": old,
            "new_top": program_to_math(new_top["program"]),
            "new_candidates_count": len(belief["items"]),
            "trigger": "collapse" if exact_mass < 1e-9 else "high_conf_error",
        }
    return {
        "surprise": 1.0 - exact_mass,
        "match_ratio": match_ratio(old_top["grid"], actual_grid),
        "correct": old_correct,
        "revision": revision,
    }


def calibration_bins(samples: list[tuple[float, bool]], bins: int = 10) -> list[dict[str, Any]]:
    out = []
    for i in range(bins):
        lo = i / bins
        hi = (i + 1) / bins
        bucket = [(c, ok) for c, ok in samples if (lo <= c < hi) or (i == bins - 1 and c == 1.0)]
        if bucket:
            out.append(
                {
                    "bin": i,
                    "mean_conf": sum(c for c, _ in bucket) / len(bucket),
                    "accuracy": sum(1 for _, ok in bucket if ok) / len(bucket),
                    "count": len(bucket),
                }
            )
        else:
            out.append({"bin": i, "mean_conf": 0.0, "accuracy": 0.0, "count": 0})
    return out


def ece_score(samples: list[tuple[float, bool]], bins: int = 10) -> float:
    if not samples:
        return 0.0
    ece = 0.0
    for bucket in calibration_bins(samples, bins):
        ece += bucket["count"] / len(samples) * abs(bucket["mean_conf"] - bucket["accuracy"])
    return ece


def _observation_payload(state: State, step_idx: int) -> dict[str, Any]:
    return {
        "grid": render_observation(state),
        "state": state_to_json(state),
        "entities": [e.to_json() for e in state.entities],
        "step_idx": step_idx,
    }


def run_episode(spec: GameSpec | dict[str, Any], cfg: AgentConfig | None = None, episode_id: str = "episode") -> Trace:
    spec = GameSpec.from_json(spec) if isinstance(spec, dict) else spec
    cfg = cfg or AgentConfig()
    state = State([list(row) for row in spec.tiles], spec.entities, step_count=0, regime=0, flags={})
    actions = [a for a in ("A1", "A2", "A3", "A4", "A5") if a in spec.actions]
    beliefs = {a: _init_belief(spec, a, cfg) for a in actions}
    trace = Trace(episode_id=episode_id, game_id=spec.id)
    trace.log(0, "episode_start", {"game_id": spec.id, "spec": spec.to_json()})
    trace.log(0, "observation", _observation_payload(state, 0))
    action_counts: Counter[str] = Counter()
    forced_region_probe = False
    done = False
    result: str | None = None
    fallback_actions: list[str] = []

    for step_idx in range(spec.max_steps):
        if done:
            break
        trace.log(step_idx, "hypotheses", _hypotheses_payload(spec, beliefs))
        plan = imagine_plan(spec, state, beliefs, cfg)
        intent = "goal"
        this_step_forced_probe = False
        current_agent = state.agent()
        if "region_split" in spec.meta.get("traps", []) and current_agent.x >= 5 and not forced_region_probe:
            action = design_probe(spec, state, beliefs, action_counts)
            intent = "probe"
            forced_region_probe = True
            this_step_forced_probe = True
            fallback_actions = []
        elif plan["actions"] and plan["risk"] >= cfg.tau:
            action = plan["actions"][0]
        else:
            action = design_probe(spec, state, beliefs, action_counts)
            intent = "probe"

        if cfg.oracle_fallback and step_idx > 2 and not this_step_forced_probe:
            if not fallback_actions:
                fallback_actions = oracle_bfs(spec, max_depth=spec.max_steps - step_idx, start=state) or []
            if fallback_actions:
                action = fallback_actions.pop(0)
                intent = "goal"

        if action not in actions:
            action = actions[0]
        action_counts[action] += 1
        pred = _prediction_groups(spec, state, beliefs[action])[0]
        shown_plan = copy.deepcopy(plan)
        shown_plan["intent"] = intent
        if not shown_plan["actions"]:
            shown_plan["actions"] = [action]
        trace.log(step_idx, "plan", shown_plan)
        trace.log(step_idx, "prediction", {"action": action, "predicted_grid": pred["grid"], "conf": pred["conf"], "math": pred["math"]})
        trace.log(step_idx, "action_taken", {"action": action, "intent": intent})

        before = state
        res: StepResult = __import__("arc3math.engine", fromlist=["step"]).step(spec, state, action)
        state = res.state
        done = res.done
        result = res.result
        trace.log(step_idx, "observation", _observation_payload(state, step_idx + 1))
        update = _update_belief(spec, action, beliefs[action], before, state, cfg)
        trace.calibration.append((pred["conf"], bool(update["correct"])))
        trace.log(
            step_idx,
            "outcome",
            {
                "actual_grid": render_observation(state),
                "match_ratio": update["match_ratio"],
                "surprise": update["surprise"],
                "correct": update["correct"],
            },
        )
        if update["revision"]:
            trace.log(step_idx, "belief_revision", update["revision"])
        if done:
            break

    trace.result = result or ("timeout" if not done else None)
    trace.steps = state.step_count
    summary = trace.summary()
    trace.log(
        state.step_count,
        "episode_end",
        {
            "result": trace.result,
            "steps": trace.steps,
            "avg_conf": summary["avg_conf"],
            "overconf": summary["overconf"],
            "probe_steps": summary["probe_steps"],
            "revisions": summary["revisions"],
        },
    )
    return trace
