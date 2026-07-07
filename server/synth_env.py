from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any

import numpy as np

from server.transforms import from_spec


class SyntheticState(Enum):
    NOT_FINISHED = "NOT_FINISHED"
    WIN = "WIN"
    GAME_OVER = "GAME_OVER"


class EmptyActionModel:
    @staticmethod
    def model_json_schema() -> dict[str, Any]:
        return {}


@dataclass(frozen=True)
class SyntheticAction:
    value: int
    name: str
    action_type: type[EmptyActionModel] = EmptyActionModel

    def is_complex(self) -> bool:
        return False


@dataclass
class SyntheticActionInput:
    id: SyntheticAction
    data: dict[str, Any]
    reasoning: dict[str, Any] | None


@dataclass
class SyntheticObservation:
    game_id: str
    guid: str
    state: SyntheticState
    levels_completed: int
    win_levels: int
    available_actions: list[int]
    frame: list[list[list[int]]]
    full_reset: bool
    action_input: SyntheticActionInput | None = None


class SyntheticEnv:
    """Small local environment with an ARC runner-compatible step interface."""

    def __init__(self, spec: dict[str, Any]) -> None:
        self.spec = spec
        self.game_id = str(spec["spec_id"])
        self.guid = f"synth-{uuid.uuid4().hex[:10]}"
        self.grid = int(spec.get("grid", 16))
        self.avatar_color = int(spec.get("avatar", {}).get("color", 4))
        self.goal_color = int(spec.get("goal", {}).get("color", 8))
        self.avatar = tuple(int(value) for value in spec["avatar"]["start"])
        self.goal = tuple(int(value) for value in spec["goal"]["target"])
        self.rules = {int(key): from_spec(value) for key, value in spec["rules"].items()}
        self.action_space = [
            SyntheticAction(value=action_id, name=f"ACTION{action_id}")
            for action_id in sorted(self.rules)
        ]
        self.steps = 0
        self.state = SyntheticState.NOT_FINISHED
        self.levels_completed = 0
        self.win_levels = int(spec.get("win_levels", 1))
        self.max_steps = int(spec.get("max_steps", 80))
        self.observation_space = self._observation(full_reset=True)

    def step(
        self,
        action: SyntheticAction,
        data: dict[str, Any] | None = None,
        reasoning: dict[str, Any] | None = None,
    ) -> SyntheticObservation:
        if self.state != SyntheticState.NOT_FINISHED:
            return self._observation(
                full_reset=False,
                action_input=SyntheticActionInput(action, data or {}, reasoning),
            )

        transform = self.rules.get(int(action.value))
        if transform is None:
            self.state = SyntheticState.GAME_OVER
        else:
            avatar_layer = self._avatar_layer()
            transformed = transform.apply(avatar_layer, background_color=0, step_index=self.steps)
            self.avatar = self._avatar_from_layer(transformed)
            self.steps += 1
            if self.avatar == self.goal:
                self.levels_completed = self.win_levels
                self.state = SyntheticState.WIN
            elif self.steps >= self.max_steps:
                self.state = SyntheticState.GAME_OVER

        observation = self._observation(
            full_reset=False,
            action_input=SyntheticActionInput(action, data or {}, reasoning),
        )
        self.observation_space = observation
        return observation

    def _observation(
        self,
        *,
        full_reset: bool,
        action_input: SyntheticActionInput | None = None,
    ) -> SyntheticObservation:
        return SyntheticObservation(
            game_id=self.game_id,
            guid=self.guid,
            state=self.state,
            levels_completed=self.levels_completed,
            win_levels=self.win_levels,
            available_actions=[action.value for action in self.action_space],
            frame=[self._render()],
            full_reset=full_reset,
            action_input=action_input,
        )

    def _render(self) -> list[list[int]]:
        frame = np.zeros((self.grid, self.grid), dtype=np.int16)
        gx, gy = self.goal
        if 0 <= gx < self.grid and 0 <= gy < self.grid:
            frame[gy, gx] = self.goal_color
        ax, ay = self.avatar
        if 0 <= ax < self.grid and 0 <= ay < self.grid:
            frame[ay, ax] = self.avatar_color
        return frame.astype(int).tolist()

    def _avatar_layer(self) -> list[list[int]]:
        frame = np.zeros((self.grid, self.grid), dtype=np.int16)
        ax, ay = self.avatar
        if 0 <= ax < self.grid and 0 <= ay < self.grid:
            frame[ay, ax] = self.avatar_color
        return frame.astype(int).tolist()

    def _avatar_from_layer(self, layer: list[list[int]]) -> tuple[int, int]:
        array = np.asarray(layer, dtype=np.int16)
        positions = np.argwhere(array == self.avatar_color)
        if len(positions) == 0:
            return self.avatar
        y, x = positions[0]
        return int(x), int(y)
