"""
AdversarialSampler — sample programs targeting specific weaknesses.

Takes weakness weights from WeaknessAnalyzer and biases the 
ProgramSampler toward those action types.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from arc3_trainer.cognitive.actions import Action, ActionDSL
from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.generator.program_sampler import ProgramSampler, SamplerConfig
from arc3_trainer.generator.task_packer import TaskPacker, PackConfig
from arc3_trainer.cognitive.task_io import Task
from arc3_trainer.trainer.capability import CapabilityProfile
from arc3_trainer.trainer.weakness import WeaknessAnalyzer


class AdversarialSampler:
    """Generate tasks targeting agent weaknesses."""

    def __init__(self, seed: Optional[int] = None):
        self._sampler = ProgramSampler(seed=seed)
        self._packer = TaskPacker(seed=seed)
        self._analyzer = WeaknessAnalyzer()
        self._last_program: Optional[Action] = None

    @property
    def last_program(self) -> Optional[Action]:
        """The most recently sampled program."""
        return self._last_program

    def sample_task(
        self,
        profile: CapabilityProfile,
        difficulty: int = 3,
    ) -> Optional[Task]:
        """Generate a task targeting weak areas of the agent."""
        # Get weakness-biased weights
        weights = self._analyzer.weakness_weights(profile)

        # Sample program with biased weights
        program = self._sampler.sample_biased(weights)
        self._last_program = program

        # Also scale difficulty
        effective_difficulty = min(difficulty, 8)

        # Pack into a task
        task = self._packer.pack(program, difficulty=effective_difficulty)
        return task

    def sample_mixed(
        self,
        profile: CapabilityProfile,
        n_tasks: int = 10,
        base_difficulty: int = 3,
        adversarial_ratio: float = 0.5,
    ) -> List[Task]:
        """Sample a mix of random (easy) and adversarial (harder) tasks."""
        tasks: List[Task] = []
        n_adv = int(n_tasks * adversarial_ratio)

        # Adversarial tasks
        for _ in range(n_adv):
            task = self.sample_task(profile, difficulty=base_difficulty + 1)
            if task is not None:
                tasks.append(task)

        # Random easy tasks
        for _ in range(n_tasks - n_adv):
            program = self._sampler.sample(difficulty=max(1, base_difficulty - 1))
            task = self._packer.pack(program, difficulty=max(1, base_difficulty - 1))
            if task is not None:
                tasks.append(task)

        return tasks
