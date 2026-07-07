from __future__ import annotations

from collections import deque
from typing import Any

from server.hypothesis import HypothesisTracker
from server.imagination import plan_one_step

AGENT_LABELS = {
    "heuristic-explorer": "Heuristic Explorer",
    "action-sweep": "Action Sweep",
    "visual-click-scan": "Visual Click Scan",
    "transform-aware": "Transform-Aware",
}


def normalize_agent_id(agent_name: str) -> str:
    normalized = agent_name.strip().lower().replace("_", "-")
    label_to_id = {
        "heuristic explorer": "heuristic-explorer",
        "action sweep": "action-sweep",
        "visual click scan": "visual-click-scan",
        "transform-aware": "transform-aware",
        "transform aware": "transform-aware",
    }
    return label_to_id.get(
        normalized,
        normalized if normalized in AGENT_LABELS else "heuristic-explorer",
    )


def agent_label(agent_name: str) -> str:
    return AGENT_LABELS[normalize_agent_id(agent_name)]


def choose_transform_aware_action(
    *,
    env: Any,
    action_stats: dict[int, dict[str, float]],
    click_queue: deque[tuple[int, int]],
    used_clicks: set[tuple[int, int]],
    analysis: dict[str, Any],
    frame: list[list[int]],
    step_index: int,
    tracker: HypothesisTracker,
) -> tuple[Any, dict[str, int], list[dict[str, Any]], str, dict[str, Any]]:
    actions = list(env.action_space)
    simple_actions = [action for action in actions if not action.is_complex()]
    complex_actions = [action for action in actions if action.is_complex()]

    if complex_actions and not any(tracker.top(int(action.value)) for action in simple_actions):
        action, data, candidates, reason = choose_visual_click_probe(
            complex_actions=complex_actions,
            click_queue=click_queue,
            used_clicks=used_clicks,
            analysis=analysis,
            step_index=step_index,
            evidence_prefix="Transform-Aware cold-start visual probe",
        )
        plan = {
            "mode": "probe",
            "threshold": 0.5,
            "selected_probe_action_id": int(action.value),
            "nodes": [],
        }
        return action, data, candidates, reason, plan

    unfit_simple_actions = [
        action for action in simple_actions if tracker.top(int(action.value)) is None
    ]
    if unfit_simple_actions:
        action = _choose_probe(unfit_simple_actions, action_stats, tracker)
        candidates = _probe_candidates(simple_actions, tracker, action_stats)
        plan = {
            "mode": "probe",
            "threshold": 0.5,
            "selected_probe_action_id": int(action.value),
            "nodes": [],
        }
        reason = (
            "Transform-Aware probe: 仍有动作没有拟合变换，"
            f"选择 {action.name} 建立动作语义先验。"
        )
        return action, {}, candidates, reason, plan

    plan = plan_one_step(
        simple_actions,
        frame,
        tracker,
        step_index=step_index,
        goal_hint=_extract_goal_hint(env),
    )
    if plan["mode"] == "exploit":
        selected_id = int(plan["selected_action_id"])
        action = next(action for action in simple_actions if int(action.value) == selected_id)
        candidates = _plan_candidates(simple_actions, plan, action_stats, mode="exploit")
        top = tracker.top(selected_id)
        reason = (
            "Transform-Aware exploit: "
            f"选择 {action.name}，当前假设 {top.transform.readable() if top else 'unfit'} "
            f"置信度 {top.confidence:.2f} >= 0.50。"
        )
        return action, {}, candidates, reason, plan

    if simple_actions:
        action = _choose_probe(simple_actions, action_stats, tracker)
        candidates = _probe_candidates(simple_actions, tracker, action_stats)
        top = tracker.top(int(action.value))
        confidence = top.confidence if top else 0.0
        reason = (
            "Transform-Aware probe: 最高路径置信度低于 0.50，"
            f"选择 {action.name} 来区分动作变换假设；当前置信度 {confidence:.2f}。"
        )
        plan["selected_probe_action_id"] = int(action.value)
        return action, {}, candidates, reason, plan

    if complex_actions:
        action, data, candidates, reason = choose_visual_click_probe(
            complex_actions=complex_actions,
            click_queue=click_queue,
            used_clicks=used_clicks,
            analysis=analysis,
            step_index=step_index,
            evidence_prefix="Transform-Aware fallback visual probe",
        )
        plan["mode"] = "probe"
        plan["selected_probe_action_id"] = int(action.value)
        return action, data, candidates, reason, plan

    raise RuntimeError("Environment exposed no available actions")


def choose_action_sweep(
    env: Any,
    action_stats: dict[int, dict[str, float]],
) -> tuple[Any, dict[str, int], list[dict[str, Any]], str]:
    actions = list(env.action_space)
    simple_actions = [action for action in actions if not action.is_complex()] or actions
    ranked = sorted(
        simple_actions,
        key=lambda action: (action_stats.get(action.value, {"count": 0.0})["count"], action.value),
    )
    action = ranked[0]
    candidates = [
        {
            "action": item.name,
            "action_id": item.value,
            "data": {},
            "score": round(10.0 - rank * 0.5, 3),
            "evidence": f"Action Sweep 轮询顺序 #{rank + 1}",
        }
        for rank, item in enumerate(ranked[:10])
    ]
    reason = (
        f"Action Sweep: 选择尝试次数最少的动作 {action.name}，"
        f"当前尝试 {action_stats.get(action.value, {'count': 0.0})['count']:.0f} 次。"
    )
    return action, {}, candidates, reason


def choose_visual_click_probe(
    *,
    complex_actions: list[Any],
    click_queue: deque[tuple[int, int]],
    used_clicks: set[tuple[int, int]],
    analysis: dict[str, Any],
    step_index: int,
    evidence_prefix: str = "Visual Click Scan",
) -> tuple[Any, dict[str, int], list[dict[str, Any]], str]:
    action = complex_actions[0]
    while click_queue and click_queue[0] in used_clicks:
        click_queue.popleft()
    queued_points = [point for point in click_queue if point not in used_clicks]
    if not queued_points:
        queued_points = [((step_index * 17) % 64, (step_index * 29) % 64)]
    candidates = [
        {
            "action": action.name,
            "action_id": action.value,
            "data": {"x": point[0], "y": point[1]},
            "score": round(10.0 - rank * 0.2, 3),
            "evidence": f"{evidence_prefix}: 连通区域候选 #{rank + 1}",
        }
        for rank, point in enumerate(queued_points[:20])
    ]
    point = queued_points[0]
    if click_queue and click_queue[0] == point:
        click_queue.popleft()
    used_clicks.add(point)
    data = {"x": point[0], "y": point[1]}
    reason = (
        f"{evidence_prefix}: 选择视觉候选区域中心 ({point[0]}, {point[1]})，"
        f"当前识别到 {analysis['component_count']} 个连通区域。"
    )
    return action, data, candidates, reason


def _plan_candidates(
    actions: list[Any],
    plan: dict[str, Any],
    action_stats: dict[int, dict[str, float]],
    *,
    mode: str,
) -> list[dict[str, Any]]:
    action_by_id = {int(action.value): action for action in actions}
    candidates = []
    for rank, node in enumerate(plan["nodes"]):
        action = action_by_id[int(node["action_id"])]
        candidates.append(
            {
                "action": action.name,
                "action_id": action.value,
                "data": {},
                "score": round(float(node["utility"]) * 10 + float(node["confidence"]) * 5, 3),
                "evidence": (
                    f"Transform-Aware {mode}: {node['readable']} "
                    f"conf={node['confidence']}; trials="
                    f"{int(action_stats.get(action.value, {'count': 0.0})['count'])}"
                ),
            }
        )
        if rank >= 9:
            break
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _probe_candidates(
    actions: list[Any],
    tracker: HypothesisTracker,
    action_stats: dict[int, dict[str, float]],
) -> list[dict[str, Any]]:
    candidates = []
    for action in actions:
        top = tracker.top(int(action.value))
        confidence = top.confidence if top else 0.0
        trials = action_stats.get(action.value, {"count": 0.0})["count"]
        score = (1.0 - confidence) * 5 + 2.0 / (trials + 1.0)
        candidates.append(
            {
                "action": action.name,
                "action_id": action.value,
                "data": {},
                "score": round(score, 3),
                "evidence": (
                    "Transform-Aware probe: no fitted transform"
                    if top is None
                    else f"Transform-Aware probe: {top.transform.readable()} conf={confidence:.2f}"
                ),
            }
        )
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _choose_probe(
    actions: list[Any],
    action_stats: dict[int, dict[str, float]],
    tracker: HypothesisTracker,
) -> Any:
    ranked = sorted(
        actions,
        key=lambda action: (
            tracker.top(int(action.value)).confidence if tracker.top(int(action.value)) else 0.0,
            action_stats.get(action.value, {"count": 0.0})["count"],
            action.value,
        ),
    )
    return ranked[0]


def _extract_goal_hint(env: Any) -> dict[str, Any] | None:
    avatar = getattr(env, "avatar", None)
    goal = getattr(env, "goal", None)
    grid = getattr(env, "grid", None)
    if avatar is None or goal is None or grid is None:
        return None
    return {"avatar": avatar, "goal": goal, "grid": grid}
