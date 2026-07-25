from __future__ import annotations

from typing import Any
import json

from arc3math.arena.db import Database

SYSTEM_PROMPT = "你是空间变换推理agent。动作是未知的空间变换函数，请用DSL假设、置信度和实验意识解决网格任务。"


def _grid_chars(grid: list[list[int]]) -> str:
    return "\n".join(" ".join(f"{v:02d}" for v in row) for row in grid)


def export_sft(db: Database, run_id: str | None = None) -> str:
    if run_id:
        episodes = db.list_episodes(run_id, limit=100000, offset=0)
    else:
        episodes = []
        for run in db.list_runs():
            episodes.extend(db.list_episodes(run["id"], limit=100000, offset=0))
    lines = []
    for episode in episodes:
        if episode.get("result") != "win":
            continue
        events = db.episode_events(episode["id"])
        last_obs: dict[str, Any] | None = None
        last_hyp: dict[str, Any] | None = None
        for event in events:
            if event["type"] == "observation":
                last_obs = event["payload"]
            elif event["type"] == "hypotheses":
                last_hyp = event["payload"]
            elif event["type"] == "action_taken" and last_obs and last_hyp:
                action = event["payload"]["action"]
                intent = event["payload"]["intent"]
                row = {
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"最近观察:\n{_grid_chars(last_obs['grid'])}\n问题：给出每个动作的最优假设、置信度、下一步行动及理由。",
                        },
                        {
                            "role": "assistant",
                            "content": json.dumps({"hypotheses": last_hyp["actions"], "action": action, "intent": intent}, ensure_ascii=False),
                        },
                    ]
                }
                lines.append(json.dumps(row, ensure_ascii=False, sort_keys=True))
    return "\n".join(lines) + ("\n" if lines else "")
