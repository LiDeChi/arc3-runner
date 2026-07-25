"""
CurriculumScheduler — stage-based training schedule.

4 stages:
  S1: Single atomic actions (difficulty 1-2)
  S2: 2-3 primitive combinations (difficulty 2-4)
  S3: Control flow (repeat/conditional, difficulty 4-7)
  S4: Adversarial (target weaknesses, difficulty 5-8)

Each stage has a target number of rounds and a pass condition
to advance to the next stage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple
from pathlib import Path

from arc3_trainer.cognitive.actions import Action
from arc3_trainer.cognitive.task_io import Task, load_task, load_tasks_from_dir
from arc3_trainer.generator.program_sampler import ProgramSampler, SamplerConfig
from arc3_trainer.generator.task_packer import TaskPacker
from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.trainer.capability import CapabilityProfile
from arc3_trainer.trainer.weakness import WeaknessAnalyzer


@dataclass
class StageConfig:
    """Configuration for a single curriculum stage."""
    name: str
    min_rounds: int          # minimum rounds to stay in this stage
    max_rounds: int          # force advance after this many rounds
    difficulty_range: range  # difficulty levels to sample from
    adversarial: bool = False  # use adversarial sampling?
    pass_rate: float = 0.7   # overall rate needed to advance
    official_ratio: float = 0.0  # fraction of tasks from official ARC (0.0 = all synthetic)


# Pre-defined stages
STAGES = [
    StageConfig("S1: Atomic", min_rounds=5, max_rounds=30,
                difficulty_range=range(1, 3), adversarial=False, pass_rate=0.8),
    StageConfig("S2: Composition", min_rounds=10, max_rounds=40,
                difficulty_range=range(2, 5), adversarial=False, pass_rate=0.7),
    StageConfig("S3: Control Flow", min_rounds=15, max_rounds=50,
                difficulty_range=range(4, 7), adversarial=False, pass_rate=0.6),
    StageConfig("S4: Adversarial", min_rounds=20, max_rounds=100,
                difficulty_range=range(5, 9), adversarial=True, pass_rate=0.5),
]


class CurriculumScheduler:
    """Manages the training curriculum and stage transitions."""

    def __init__(self, stages: Optional[List[StageConfig]] = None):
        self.stages = stages or STAGES
        self._current_stage_idx = 0
        self._rounds_in_stage = 0
        self._last_program: Optional[Action] = None
        self._last_strategy: str = "random"
        self._last_difficulty: int = 1
        self._last_source: str = "synthetic"
        self._official_tasks: List[Task] = []
        self._official_task_idx: int = 0

    def set_official_tasks(self, tasks: List[Task]) -> None:
        """Load official ARC tasks for mixed training."""
        self._official_tasks = list(tasks)

    def set_official_tasks_dir(self, path: str | Path) -> None:
        """Load official ARC tasks from a directory of JSON files."""
        p = Path(path)
        if p.exists() and p.is_dir():
            self._official_tasks = load_tasks_from_dir(p)
        else:
            pass  # silently ignore — may not be configured

    @property
    def num_official_tasks(self) -> int:
        """Number of loaded official ARC tasks."""
        return len(self._official_tasks)

    @property
    def current_stage(self) -> StageConfig:
        return self.stages[self._current_stage_idx]

    @property
    def current_stage_index(self) -> int:
        return self._current_stage_idx

    @property
    def is_final_stage(self) -> bool:
        return self._current_stage_idx >= len(self.stages) - 1

    def should_advance(self, profile: CapabilityProfile) -> bool:
        """Check if the agent is ready for the next stage."""
        stage = self.current_stage
        self._rounds_in_stage += 1

        # Force advancement
        if self._rounds_in_stage >= stage.max_rounds:
            return True

        # Need minimum rounds
        if self._rounds_in_stage < stage.min_rounds:
            return False

        # Check pass rate
        rate = profile.overall_rate()
        if rate >= stage.pass_rate:
            return True

        return False

    def advance(self) -> bool:
        """Advance to the next stage. Returns True if advanced."""
        if self.is_final_stage:
            return False
        self._current_stage_idx += 1
        self._rounds_in_stage = 0
        return True

    def reset(self):
        """Reset to the first stage."""
        self._current_stage_idx = 0
        self._rounds_in_stage = 0

    def generate_task(
        self,
        profile: CapabilityProfile,
        sampler: ProgramSampler,
        packer: TaskPacker,
        adversarial_sampler=None,
    ) -> Optional[Task]:
        """Generate a task appropriate for the current stage.

        Mixes official ARC tasks with synthetic ones based on
        ``stage.official_ratio``.
        """
        import random as _random
        stage = self.current_stage
        difficulty = stage.difficulty_range.start

        # Decide source: official vs synthetic
        use_official = (
            self._official_tasks
            and stage.official_ratio > 0
            and _random.random() < stage.official_ratio
        )

        if use_official:
            # Cycle through official tasks
            task = self._official_tasks[self._official_task_idx % len(self._official_tasks)]
            self._official_task_idx += 1
            self._last_source = "official"
            self._last_strategy = "official_arc"
            self._last_difficulty = difficulty
            self._last_program = None
            return task

        if stage.adversarial and adversarial_sampler is not None:
            self._last_source = "synthetic"
            self._last_strategy = "adversarial"
            self._last_difficulty = min(difficulty + 1, 8)
            task = adversarial_sampler.sample_task(
                profile, difficulty=difficulty
            )
            self._last_program = adversarial_sampler.last_program
            return task
        else:
            self._last_source = "synthetic"
            self._last_strategy = "random"
            self._last_difficulty = difficulty
            program = sampler.sample(difficulty=difficulty)
            self._last_program = program
            return packer.pack(program, difficulty=difficulty)

    def summary(self) -> str:
        """Return a short text summary."""
        stage = self.current_stage
        return (
            f"[Stage {self._current_stage_idx + 1}/{len(self.stages)}] "
            f"{stage.name} — round {self._rounds_in_stage}/{stage.max_rounds}"
        )

    @property
    def last_program(self) -> Optional[Action]:
        """The program sampled in the most recent generate_task() call."""
        return self._last_program

    @property
    def last_generation_info(self) -> dict:
        return {
            "strategy": self._last_strategy,
            "difficulty": self._last_difficulty,
            "program": self._last_program,
            "source": self._last_source,
        }

    @property
    def allocation_summary(self) -> List[dict]:
        """Return a per-stage allocation breakdown for the frontend."""
        return [
            {
                "stage": s.name,
                "adversarial": s.adversarial,
                "official_ratio": s.official_ratio,
                "synthetic_ratio": round(1.0 - s.official_ratio, 2),
                "difficulty": f"{s.difficulty_range.start}-{s.difficulty_range.stop - 1}",
                "sampling": "adversarial" if s.adversarial else "random",
            }
            for i, s in enumerate(self.stages)
        ]
