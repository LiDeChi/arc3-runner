from __future__ import annotations

from dataclasses import dataclass
from http.cookiejar import CookieJar
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener
import json
import os


TERMINAL_STATES = {"WIN", "GAME_OVER", "NOT_STARTED"}


class ArcApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class ArcSnapshot:
    game_id: str
    guid: str
    frame: list[list[list[int]]]
    state: str
    levels_completed: int
    win_levels: int
    action_input: dict[str, Any]
    available_actions: list[int]
    raw: dict[str, Any]

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "ArcSnapshot":
        return cls(
            game_id=str(data["game_id"]),
            guid=str(data["guid"]),
            frame=_coerce_frames(data.get("frame", [])),
            state=str(data.get("state", "NOT_STARTED")),
            levels_completed=int(data.get("levels_completed", 0)),
            win_levels=int(data.get("win_levels", 0)),
            action_input=dict(data.get("action_input", {})),
            available_actions=[int(a) for a in data.get("available_actions", [])],
            raw=dict(data),
        )

    @property
    def latest_grid(self) -> list[list[int]]:
        return self.frame[-1] if self.frame else []

    @property
    def done(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def result(self) -> str | None:
        if self.state == "WIN":
            return "win"
        if self.state in {"GAME_OVER", "NOT_STARTED"}:
            return "lose"
        return None


def _coerce_frames(value: Any) -> list[list[list[int]]]:
    if not isinstance(value, list):
        return []
    frames: list[list[list[int]]] = []
    for frame in value:
        if not isinstance(frame, list):
            continue
        grid: list[list[int]] = []
        for row in frame:
            if isinstance(row, list):
                grid.append([int(cell) for cell in row])
        if grid:
            frames.append(grid)
    return frames


def env_api_key() -> str | None:
    return os.getenv("ARC_API_KEY") or os.getenv("ARC_AGI_API")


class RemoteArcClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
        opener: Any | None = None,
    ):
        self.api_key = api_key if api_key is not None else env_api_key()
        self.base_url = (base_url or os.getenv("ARC_BASE_URL") or "https://three.arcprize.org").rstrip("/") + "/"
        self.timeout = timeout
        self.cookie_jar = CookieJar()
        self.opener = opener or build_opener(HTTPCookieProcessor(self.cookie_jar))

    def list_games(self) -> list[dict[str, Any]]:
        return list(self._request("GET", "/api/games"))

    def open_scorecard(
        self,
        *,
        source_url: str | None = None,
        tags: list[str] | None = None,
        opaque: dict[str, Any] | None = None,
    ) -> str:
        payload: dict[str, Any] = {}
        if source_url:
            payload["source_url"] = source_url
        if tags:
            payload["tags"] = tags
        if opaque:
            payload["opaque"] = opaque
        data = self._request("POST", "/api/scorecard/open", payload)
        return str(data["card_id"])

    def close_scorecard(self, card_id: str) -> dict[str, Any]:
        return dict(self._request("POST", "/api/scorecard/close", {"card_id": card_id}))

    def reset(self, game_id: str, card_id: str, guid: str | None = None) -> ArcSnapshot:
        payload: dict[str, Any] = {"game_id": game_id, "card_id": card_id}
        if guid:
            payload["guid"] = guid
        return ArcSnapshot.from_json(dict(self._request("POST", "/api/cmd/RESET", payload)))

    def action(
        self,
        game_id: str,
        guid: str,
        action_id: int,
        *,
        x: int | None = None,
        y: int | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> ArcSnapshot:
        if action_id not in {1, 2, 3, 4, 5, 6, 7}:
            raise ValueError(f"ARC action id must be 1..7, got {action_id}")
        payload: dict[str, Any] = {"game_id": game_id, "guid": guid}
        if action_id == 6:
            if x is None or y is None:
                raise ValueError("ACTION6 requires x and y")
            payload["x"] = int(x)
            payload["y"] = int(y)
        if reasoning:
            payload["reasoning"] = reasoning
        return ArcSnapshot.from_json(dict(self._request("POST", f"/api/cmd/ACTION{action_id}", payload)))

    def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        request = Request(urljoin(self.base_url, path.lstrip("/")), data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ArcApiError(f"ARC API {method} {path} failed: HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise ArcApiError(f"ARC API {method} {path} failed: {exc.reason}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ArcApiError(f"ARC API {method} {path} returned non-JSON response") from exc


def arc_action_name(action_id: int) -> str:
    return f"ACTION{action_id}"


def parse_arc_action(action: str | int) -> int:
    if isinstance(action, int):
        return action
    text = action.upper()
    if text.startswith("ACTION"):
        return int(text.removeprefix("ACTION"))
    if text.startswith("A"):
        return int(text.removeprefix("A"))
    return int(text)


class RemoteArcEnv:
    def __init__(
        self,
        game_id: str,
        card_id: str,
        *,
        client: RemoteArcClient | None = None,
        guid: str | None = None,
    ):
        self.game_id = game_id
        self.card_id = card_id
        self.client = client or RemoteArcClient()
        self.guid = guid
        self.snapshot: ArcSnapshot | None = None

    def reset(self) -> dict[str, Any]:
        self.snapshot = self.client.reset(self.game_id, self.card_id, self.guid)
        self.guid = self.snapshot.guid
        return self.observation()

    def step(self, action: str | int) -> dict[str, Any]:
        if not self.snapshot or not self.guid:
            raise RuntimeError("RemoteArcEnv.step called before reset")
        action_id = parse_arc_action(action)
        self.snapshot = self.client.action(self.game_id, self.guid, action_id)
        self.guid = self.snapshot.guid
        return self.observation()

    def action_space(self) -> list[str]:
        if not self.snapshot:
            return []
        return [arc_action_name(action_id) for action_id in self.snapshot.available_actions]

    def observation(self) -> dict[str, Any]:
        if not self.snapshot:
            raise RuntimeError("RemoteArcEnv has no snapshot")
        return {
            "grid": self.snapshot.latest_grid,
            "frames": self.snapshot.frame,
            "done": self.snapshot.done,
            "result": self.snapshot.result,
            "state": self.snapshot.state,
            "game_id": self.snapshot.game_id,
            "guid": self.snapshot.guid,
            "levels_completed": self.snapshot.levels_completed,
            "win_levels": self.snapshot.win_levels,
            "available_actions": self.snapshot.available_actions,
            "raw": self.snapshot.raw,
        }
