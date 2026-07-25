"""
Demo official ARC tasks — a small set of hand-crafted ARC-AGI-style
tasks for testing the mixed-training workflow.

These tasks follow the standard ARC JSON format and can be loaded via
``CurriculumScheduler.set_official_tasks_dir()``.

Usage:
    from arc3_trainer.generator.demo_official import DEMO_OFFICIAL_DIR
    scheduler.set_official_tasks_dir(DEMO_OFFICIAL_DIR)
"""
from __future__ import annotations

from pathlib import Path

DEMO_OFFICIAL_DIR = str(Path(__file__).parent)

__all__ = ["DEMO_OFFICIAL_DIR"]
