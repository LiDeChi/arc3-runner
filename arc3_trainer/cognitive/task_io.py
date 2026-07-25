"""
task_io — load and save ARC tasks in the standard JSON format.

An ARC task file contains:
{
  "train": [{"input": grid, "output": grid}, ...],
  "test":  [{"input": grid, "output": grid}, ...]
}

Grid is a list of lists of ints 0..9.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from arc3_trainer.cognitive.grid import Grid


@dataclass
class Task:
    """A single ARC task with train and test pairs."""
    train: List[Tuple[Grid, Grid]] = field(default_factory=list)  # (input, output)
    test: List[Tuple[Grid, Grid]] = field(default_factory=list)   # (input, output)
    metadata: Dict = field(default_factory=dict)


def load_task(path: str | Path) -> Task:
    """Load a single ARC JSON task file."""
    p = Path(path)
    with open(p, "r") as f:
        raw = json.load(f)

    task = Task(metadata={"source": str(p)})

    for pair in raw.get("train", []):
        inp = _grid_from_list(pair["input"])
        out = _grid_from_list(pair["output"])
        task.train.append((inp, out))

    for pair in raw.get("test", []):
        inp = _grid_from_list(pair["input"])
        out = _grid_from_list(pair.get("output", pair["input"]))  # fallback for prediction
        task.test.append((inp, out))

    return task


def save_task(task: Task, path: str | Path) -> None:
    """Save a Task to a JSON file in ARC format."""
    raw: Dict[str, List] = {
        "train": [
            {"input": inp.as_list(), "output": out.as_list()}
            for inp, out in task.train
        ],
        "test": [
            {"input": inp.as_list(), "output": out.as_list()}
            for inp, out in task.test
        ],
    }
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(raw, f, indent=2)


def load_tasks_from_dir(dir_path: str | Path) -> List[Task]:
    """Load all ARC task JSON files from a directory."""
    p = Path(dir_path)
    tasks: List[Task] = []
    for f in sorted(p.iterdir()):
        if f.suffix.lower() == ".json":
            tasks.append(load_task(f))
    return tasks


def _grid_from_list(data: List[List[int]]) -> Grid:
    return Grid(data)


def format_task_preview(task: Task, max_train: int = 3) -> str:
    """Return a short text preview of a task for logging."""
    lines = [
        f"Task: {task.metadata.get('source', 'unknown')}",
        f"  Train pairs: {len(task.train)}",
        f"  Test pairs:  {len(task.test)}",
    ]
    for i, (inp, out) in enumerate(task.train[:max_train]):
        lines.append(f"  Train[{i}]: {inp.height}x{inp.width} → {out.height}x{out.width}")
    if len(task.train) > max_train:
        lines.append(f"  ... ({len(task.train) - max_train} more)")
    return "\n".join(lines)
