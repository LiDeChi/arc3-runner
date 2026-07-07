from __future__ import annotations

import uuid
from copy import deepcopy
from typing import Any

BASE_RULES: dict[str, dict[str, Any]] = {
    "1": {"op": "translate", "dx": 0, "dy": -1},
    "2": {"op": "translate", "dx": 0, "dy": 1},
    "3": {"op": "translate", "dx": -1, "dy": 0},
    "4": {"op": "translate", "dx": 1, "dy": 0},
}


TRAP_DESCRIPTIONS = {
    "T1": "规则突变：前 k 步 ACTION1 向上，之后变为向右。",
    "T6": "伪装偏移：前 k 步 ACTION1 向上，之后变为向上并向右。",
}


def default_synth_specs() -> list[dict[str, Any]]:
    return [
        make_trap_spec("T1", spec_id="synth-t1-rule-shift", params={"k": 3}),
        make_trap_spec("T6", spec_id="synth-t6-disguised-drift", params={"k": 4}),
    ]


def make_trap_spec(
    template: str,
    *,
    spec_id: str | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    trap = template.upper()
    if trap not in TRAP_DESCRIPTIONS:
        raise ValueError(f"Unsupported trap template: {template}")

    trap_params = {"k": 4}
    if params:
        trap_params.update(params)

    grid = int(trap_params.get("grid", 16))
    start = trap_params.get("start", [3, grid - 3])
    target = trap_params.get("target", [grid - 3, 2])
    rules = deepcopy(BASE_RULES)

    if trap == "T1":
        rules["1"] = {
            "op": "periodic",
            "n": int(trap_params["k"]),
            "f": {"op": "translate", "dx": 0, "dy": -1},
            "g": {"op": "translate", "dx": 1, "dy": 0},
        }
    elif trap == "T6":
        rules["1"] = {
            "op": "periodic",
            "n": int(trap_params["k"]),
            "f": {"op": "translate", "dx": 0, "dy": -1},
            "g": {
                "op": "compose",
                "fs": [
                    {"op": "translate", "dx": 1, "dy": 0},
                    {"op": "translate", "dx": 0, "dy": -1},
                ],
            },
        }

    resolved_id = spec_id or f"synth-{trap.lower()}-{uuid.uuid4().hex[:8]}"
    return {
        "spec_id": resolved_id,
        "grid": grid,
        "avatar": {"color": 4, "start": [int(start[0]), int(start[1])]},
        "goal": {"type": "reach", "target": [int(target[0]), int(target[1])], "color": 8},
        "rules": rules,
        "traps": [{"template": trap, "params": trap_params}],
        "max_steps": int(trap_params.get("max_steps", 80)),
        "win_levels": 1,
        "title": f"{resolved_id} ({trap})",
    }


def synth_game_info(spec: dict[str, Any]) -> dict[str, Any]:
    trap = spec.get("traps", [{}])[0].get("template", "synth")
    return {
        "game_id": spec["spec_id"],
        "official_game_id": spec["spec_id"],
        "title": spec.get("title", spec["spec_id"]),
        "tags": ["synthetic", trap],
        "baseline_actions": [1, 2, 3, 4],
        "default_fps": 8,
        "source": "synth-local",
    }
