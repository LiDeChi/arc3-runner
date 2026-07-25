"""
TrainingLoop — main adversarial training loop.

The core algorithm:
  For each round:
    1. Curriculum determines current stage and generates a task
    2. Agent attempts to solve it
    3. Results are recorded in CapabilityProfile
    4. WeaknessAnalyzer updates the adversarial weights
    5. Curriculum checks if it's time to advance

The loop can emit events (via callbacks) for the dashboard.
All callbacks are wrapped in try/except so a failing dashboard
never crashes training.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from arc3_trainer.cognitive.grid import Grid
from arc3_trainer.cognitive.actions import Action
from arc3_trainer.cognitive.task_io import Task, save_task, format_task_preview
from arc3_trainer.cognitive.diff import DiffPerception
from arc3_trainer.agent.solver import Solver, SolveResult
from arc3_trainer.agent.searcher import program_cost  # noqa: F811
from arc3_trainer.generator.program_sampler import ProgramSampler, SamplerConfig
from arc3_trainer.generator.task_packer import TaskPacker, PackConfig
from arc3_trainer.generator.difficulty import DifficultyControl
from arc3_trainer.trainer.capability import CapabilityProfile
from arc3_trainer.trainer.weakness import WeaknessAnalyzer
from arc3_trainer.trainer.adversarial import AdversarialSampler
from arc3_trainer.trainer.curriculum import CurriculumScheduler

logger = logging.getLogger(__name__)


# Event callback type for dashboard integration
TrainEventCallback = Callable[[str, Dict[str, Any]], None]


def _null_callback(event: str, data: Dict[str, Any]) -> None:
    pass


def _safe_callback(cb: TrainEventCallback, event: str, data: Dict[str, Any]) -> None:
    """Call *cb* wrapped in try/except so a failing callback never crashes training."""
    try:
        cb(event, data)
    except Exception as exc:
        logger.warning(f"Callback failed for event '{event}': {exc}")


@dataclass
class RoundRecord:
    """Record of a single training round."""
    round_num: int
    stage: int
    task: Task
    result: SolveResult
    difficulty: int
    action_kind: str
    duration: float
    success: bool

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-compatible dict (without full task/result data)."""
        return {
            "round": self.round_num,
            "stage": self.stage,
            "difficulty": self.difficulty,
            "success": self.success,
            "action_kind": self.action_kind,
            "duration": self.duration,
        }


@dataclass
class TrainConfig:
    """Training configuration."""
    rounds: int = 100
    beam_width: int = 50
    max_depth: int = 5
    output_dir: str = "training_output"
    log_every: int = 10           # log summary every N rounds
    save_every: int = 50          # save checkpoint every N rounds
    official_ratio: float = 0.0   # fraction of tasks from official ARC (0.0 = all synthetic)
    official_tasks_dir: str = ""  # path to directory of official ARC task JSON files


class TrainingLoop:
    """Main adversarial training loop."""

    def __init__(
        self,
        config: Optional[TrainConfig] = None,
        event_callback: Optional[TrainEventCallback] = None,
        seed: Optional[int] = None,
    ):
        self.config = config or TrainConfig()
        self.callback = event_callback or _null_callback

        # Core components
        self.solver = Solver(beam_width=self.config.beam_width,
                             max_depth=self.config.max_depth,
                             event_callback=self.callback)
        self.sampler = ProgramSampler(seed=seed)
        self.packer = TaskPacker(seed=seed)
        self.adversarial = AdversarialSampler(seed=seed)
        self.curriculum = CurriculumScheduler()
        # Load official ARC tasks if configured
        official_dir = self.config.official_tasks_dir
        if self.config.official_ratio > 0:
            if not official_dir:
                # Auto-load demo tasks when ratio > 0 but no dir specified
                from arc3_trainer.generator.demo_official import DEMO_OFFICIAL_DIR
                official_dir = DEMO_OFFICIAL_DIR
            p = Path(official_dir)
            if p.exists() and p.is_dir():
                self.curriculum.set_official_tasks_dir(p)
                for stage in self.curriculum.stages:
                    stage.official_ratio = self.config.official_ratio
                logger.info(
                    "Loaded %d official tasks from %s, ratio=%.0f%%",
                    self.curriculum.num_official_tasks,
                    official_dir,
                    self.config.official_ratio * 100,
                )
        self.analyzer = WeaknessAnalyzer()

        # State
        self.profile = CapabilityProfile()
        self.history: List[RoundRecord] = []
        self.current_round = 0
        self._stop_requested = False
        self._diff = DiffPerception()

    def _cb(self, event: str, data: Dict[str, Any]) -> None:
        """Safe callback wrapper."""
        _safe_callback(self.callback, event, data)

    def _safe_mkdir(self, path: Path) -> bool:
        """Create directories, returning False on failure instead of crashing."""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except OSError as exc:
            logger.error(f"Failed to create output directory {path}: {exc}")
            return False

    def train(self) -> Optional[CapabilityProfile]:
        """Run the full training loop.  Returns None on fatal I/O error.

        If resuming from a checkpoint (self.current_round > 0), starts from
        the next round and runs *additional* ``config.rounds`` rounds.
        """
        output_dir = Path(self.config.output_dir)
        if not self._safe_mkdir(output_dir):
            return None

        self._cb("training_start", {"total_rounds": self.config.rounds})

        start_round = self.current_round + 1
        end_round = self.current_round + self.config.rounds

        # Ensure tasks directory exists
        tasks_dir = output_dir / "tasks"
        self._safe_mkdir(tasks_dir)

        for round_num in range(start_round, end_round + 1):
            if self._stop_requested:
                logger.info("Training stopped by user request")
                break

            self.current_round = round_num

            stage_idx = self.curriculum.current_stage_index
            stage = self.curriculum.current_stage

            self._cb("round_start", {
                "round": round_num,
                "stage": stage.name,
                "stage_index": stage_idx,
            })

            # --- Generate task ---
            self._cb("node_enter", {"node": "generator", "stage": stage.name})
            task = self.curriculum.generate_task(
                self.profile, self.sampler, self.packer,
                adversarial_sampler=self.adversarial if stage.adversarial else None,
            )

            # Emit generation strategy info (after task is generated, so metadata is populated)
            gen_info = self.curriculum.last_generation_info
            gen_program = gen_info.get("program")
            gen_source = gen_info.get("source", "synthetic")
            self._cb("task_generation", {
                "source": gen_source,
                "strategy": gen_info.get("strategy", "random"),
                "stage": stage.name,
                "stage_index": stage_idx,
                "difficulty": gen_info.get("difficulty", 1),
                "program_kind": gen_program.kind() if gen_program else None,
                "program_cost": program_cost(gen_program) if gen_program else None,
                "pattern_family": self.packer.last_pattern if gen_source == "synthetic" else "official",
            })
            # Save task to disk for persistence
            if task is not None:
                try:
                    task_path = tasks_dir / f"round_{round_num:04d}.json"
                    save_task(task, task_path)
                except Exception as exc:
                    logger.warning(f"Failed to save task {task_path}: {exc}")

            # Emit task grid data for frontend visualization
            if task is not None and task.train:
                grid_data = {
                    "train_pairs": [
                        [inp.as_list(), out.as_list()]
                        for inp, out in task.train[:3]
                    ],
                    "test_input": task.test[0][0].as_list() if task.test else None,
                }
                self._cb("task_grids", grid_data)
            self._cb("node_exit", {"node": "generator"})

            if task is None:
                logger.warning(f"Round {round_num}: failed to generate task, skipping")
                self._cb("round_skip", {"round": round_num, "reason": "task_generation_failed"})
                self._cb("log", {
                    "level": "warning",
                    "message": f"⚠️ Round {round_num}: task generation failed, skipping",
                })
                continue

            # --- Solve (protected) ---
            self._cb("node_enter", {"node": "solver"})
            self._cb("log", {
                "level": "info",
                "message": f"🔍 Round {round_num}: solving task (difficulty={task.difficulty if hasattr(task, 'difficulty') else '?'})",
            })
            t0 = time.time()
            try:
                result = self.solver.solve(task)
            except Exception as exc:
                logger.error(f"Round {round_num}: solver crashed: {exc}")
                self._cb("log", {"level": "error", "message": f"💥 Round {round_num}: solver crashed: {exc}"})
                result = SolveResult(success=False, error_rate=1.0)
            duration = time.time() - t0
            self._cb("node_exit", {"node": "solver"})

            # --- Score ---
            self._cb("node_enter", {"node": "scoring"})
            success = result.success
            self._cb("node_exit", {"node": "scoring"})
            self._cb("log", {
                "level": "success" if success else "error",
                "message": f"{'✅' if success else '❌'} Round {round_num}: "
                           f"{'solved' if success else 'failed'} "
                           f"({result.error_rate:.1%} error, {duration:.2f}s)",
            })

            # --- Profile update ---
            self._cb("node_enter", {"node": "profiling"})
            # Only record if we have a real program — skip "unknown" noise
            if result.program is not None:
                action_kind = result.program.kind()
                diff = DifficultyControl.level(result.program, task.train[0][0]) if task.train else 3
                self.profile.record(action_kind, diff, success)

                record = RoundRecord(
                    round_num=round_num,
                    stage=stage_idx,
                    task=task,
                    result=result,
                    difficulty=diff,
                    action_kind=action_kind,
                    duration=duration,
                    success=success,
                )
                self.history.append(record)
            else:
                # No program found — still record a generic failure marker
                self.profile.record("_no_program", 0, False)
                record = RoundRecord(
                    round_num=round_num, stage=stage_idx,
                    task=task, result=result,
                    difficulty=0, action_kind="_no_program",
                    duration=duration, success=False,
                )
                self.history.append(record)
            self._cb("node_exit", {"node": "profiling"})

            # --- Adapt (curriculum advancement) ---
            self._cb("node_enter", {"node": "adaptation"})
            advanced = self.curriculum.should_advance(self.profile)
            if advanced:
                did_advance = self.curriculum.advance()
                if did_advance:
                    logger.info(f"Round {round_num}: advanced to {self.curriculum.current_stage.name}")
                    self._cb("stage_advance", {
                        "from_stage": stage.name,
                        "to_stage": self.curriculum.current_stage.name,
                    })
            self._cb("node_exit", {"node": "adaptation"})

            # --- Logging ---
            if round_num % self.config.log_every == 0:
                self._log_summary(round_num)

            # --- Save checkpoint (protected) ---
            if round_num % self.config.save_every == 0:
                try:
                    self._save_checkpoint(output_dir)
                except OSError as exc:
                    logger.error(f"Failed to save checkpoint at round {round_num}: {exc}")

            self._cb("round_end", {
                "round": round_num,
                "success": success,
                "duration": duration,
                "stage": stage.name,
                "stage_index": stage_idx,
                "difficulty": record.difficulty,
                "action_kind": record.action_kind,
                "overall_rate": self.profile.overall_rate(),
                # Attach result grid data
                "predicted": result.predicted_grid.as_list() if result.predicted_grid else None,
                "expected": (task.test[0][1].as_list()
                             if task and task.test and task.test[0][1] is not None
                             else None),
                # Solver trace for frontend persistence
                "trace_details": {
                    "search_trace": result.search_trace if result and result.search_trace else None,
                    "perceive_data": {
                        "shape_changed": result.constraints.shape_changed
                            if result and result.constraints else None,
                        "colours_used": sorted(result.constraints.colours_used)
                            if result and result.constraints else [],
                        "consensus_operation": result.constraints.consensus_operation.operation
                            if result and result.constraints and result.constraints.consensus_operation
                            else None,
                        "num_pairs": len(result.constraints.pairs)
                            if result and result.constraints else 0,
                    } if result and result.constraints else None,
                    "program_kind": result.program.kind() if result and result.program else None,
                    "program_cost": result.program_cost if result else 0,
                    "seed_kinds": [a.kind() for a in result.seed_actions[:5]]
                                   if result and result.seed_actions else [],
                },
                # Generation info included for frontend history storage
                "generation": {
                    "strategy": self.curriculum.last_generation_info.get("strategy", "random"),
                    "source": self.curriculum.last_generation_info.get("source", "synthetic"),
                    "pattern_family": self.packer.last_pattern,
                    "program_kind": gen_program.kind() if gen_program else None,
                    "program_cost": program_cost(gen_program) if gen_program else None,
                    "difficulty": self.curriculum.last_generation_info.get("difficulty", 1),
                },
            })

        self._cb("training_end", {
            "total_rounds": self.config.rounds,
            "overall_rate": self.profile.overall_rate(),
            "weaknesses": self.analyzer.weakness_summary(self.profile),
            "allocation": self.curriculum.allocation_summary,
        })

        # Final save (protected)
        try:
            self._save_checkpoint(output_dir, final=True)
        except OSError as exc:
            logger.error(f"Failed to save final checkpoint: {exc}")

        return self.profile

    def _log_summary(self, round_num: int) -> None:
        """Log a training summary."""
        recent = self.history[-self.config.log_every:]
        successes = sum(1 for r in recent if r.success)
        overall = self.profile.overall_rate()
        weaknesses = self.analyzer.analyse(self.profile)[:3]

        logger.info(
            f"[Round {round_num}] "
            f"Recent: {successes}/{len(recent)} successful ({successes/len(recent):.0%}) "
            f"| Overall: {overall:.0%} "
            f"| Stage: {self.curriculum.summary()}"
        )
        if weaknesses:
            for w in weaknesses[:3]:
                logger.info(f"  Weakness: {w.action_kind} @ diff={w.difficulty} "
                            f"({w.success_rate:.0%})")

    def _save_checkpoint(self, output_dir: Path, final: bool = False) -> None:
        """Save training checkpoint with full history and metadata."""
        suffix = "final" if final else f"round_{self.current_round}"
        profile_path = output_dir / f"profile_{suffix}.json"
        history_path = output_dir / f"history_{suffix}.jsonl"
        metadata_path = output_dir / f"metadata_{suffix}.json"

        self.profile.save(profile_path)

        # Save full history as JSONL (all records, no truncation)
        with open(history_path, "w") as f:
            for rec in self.history:
                f.write(json.dumps(rec.to_dict()) + "\n")

        # Save metadata for resume
        metadata = {
            "last_round": self.current_round,
            "stage_index": self.curriculum.current_stage_index,
            "rounds_in_stage": self.curriculum._rounds_in_stage,
            "total_rounds_target": self.config.rounds,
            "overall_rate": self.profile.overall_rate(),
        }
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(
            f"Checkpoint saved to {output_dir} "
            f"(profile: {profile_path}, history: {len(self.history)} records)"
        )

    # ------------------------------------------------------------------
    # Checkpoint loading / resume
    # ------------------------------------------------------------------

    @classmethod
    def load_checkpoint(
        cls,
        checkpoint_dir: str,
        config: Optional[TrainConfig] = None,
        seed: Optional[int] = None,
    ) -> "TrainingLoop":
        """Load training loop state from a checkpoint directory for resume.

        Restores the capability profile, curriculum stage, and round count.
        The returned loop can then be passed to ``train()`` which will
        continue from the next uncompleted round.
        """
        output_dir = Path(checkpoint_dir)

        metadata_path = _find_latest_metadata(output_dir)
        if metadata_path is None:
            raise FileNotFoundError(
                f"No checkpoint metadata found in {checkpoint_dir} — "
                f"run training at least once first"
            )

        suffix = metadata_path.stem.replace("metadata_", "")

        # Load profile
        profile_path = output_dir / f"profile_{suffix}.json"
        profile = CapabilityProfile.load(profile_path)

        # Load metadata
        with open(metadata_path) as f:
            metadata = json.load(f)

        # Load history (as lightweight dict-based RoundRecord objects)
        history_path = output_dir / f"history_{suffix}.jsonl"
        history: List[RoundRecord] = []
        if history_path.exists():
            with open(history_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        d = json.loads(line)
                        history.append(RoundRecord(
                            round_num=d["round"],
                            stage=d["stage"],
                            task=None,       # not loaded — only metadata needed
                            result=None,     # not loaded
                            difficulty=d.get("difficulty", 0),
                            action_kind=d.get("action_kind", ""),
                            duration=d.get("duration", 0.0),
                            success=d.get("success", False),
                        ))

        # Build config defaults from metadata when none provided
        if config is None:
            config = TrainConfig(
                rounds=metadata.get("total_rounds_target", 100),
                output_dir=checkpoint_dir,
            )

        loop = cls(config=config, seed=seed)
        loop.profile = profile
        loop.history = history
        loop.current_round = metadata.get("last_round", 0)
        loop.curriculum._current_stage_idx = metadata.get("stage_index", 0)
        loop.curriculum._rounds_in_stage = metadata.get("rounds_in_stage", 0)

        logger.info(
            "Resumed from checkpoint: round %d, stage %d, overall rate %.1f%%",
            loop.current_round,
            loop.curriculum.current_stage_index + 1,
            profile.overall_rate() * 100,
        )
        return loop

    def export_solver(self, path: str = "exported_solver.py") -> None:
        """Export a standalone ARC solver with zero external dependencies.

        The exported script is pure Python (no numpy) and covers all
        16 DSL action types with beam search over compositions.
        """
        source = r'''"""
Exported ARC solver — fully autonomous, offline, zero external dependencies.

Usage:
    python exported_solver.py <task.json>   # prints output grid as JSON

Generated by the ARC3 adversarial training platform.
"""
from __future__ import annotations
import json
import sys
from typing import Dict, List, Tuple, Optional


class Grid:
    """2D grid of ints 0..9, 1x1 up to 30x30. Pure Python."""

    def __init__(self, data):
        self._h = len(data)
        self._w = len(data[0]) if data else 0
        self._rows = tuple(tuple(int(v) for v in row) for row in data)

    @classmethod
    def zeros(cls, h, w):
        return cls([[0] * w for _ in range(h)])

    @property
    def height(self): return self._h
    @property
    def width(self): return self._w
    @property
    def shape(self): return (self._h, self._w)

    def __eq__(self, other):
        if not isinstance(other, Grid): return NotImplemented
        return self._rows == other._rows

    def as_list(self):
        return [list(row) for row in self._rows]

    def copy(self):
        return Grid(self.as_list())

    def _mut(self):
        return [list(row) for row in self._rows]

    def get(self, x, y):
        return self._rows[y][x]

    def has_color(self, c):
        return any(self._rows[y][x] == c for y in range(self._h) for x in range(self._w))

    def colours(self):
        return {self._rows[y][x] for y in range(self._h) for x in range(self._w)}

    # --- Geometric ---
    def rotate_cw(self):
        h, w = self._h, self._w
        out = [[0] * h for _ in range(w)]
        for y in range(h):
            for x in range(w):
                out[x][h - 1 - y] = self._rows[y][x]
        return Grid(out)

    def rotate_ccw(self):
        h, w = self._h, self._w
        out = [[0] * h for _ in range(w)]
        for y in range(h):
            for x in range(w):
                out[w - 1 - x][y] = self._rows[y][x]
        return Grid(out)

    def rotate_180(self):
        h, w = self._h, self._w
        out = [[0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                out[h - 1 - y][w - 1 - x] = self._rows[y][x]
        return Grid(out)

    def flip_h(self):
        return Grid([list(reversed(row)) for row in self._rows])

    def flip_v(self):
        return Grid(list(reversed(self._rows)))

    def translate(self, dx, dy, fill=0):
        h, w = self._h, self._w
        out = [[fill] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    out[ny][nx] = self._rows[y][x]
        return Grid(out)

    # --- Colouring ---
    def recolor(self, old, new):
        out = self._mut()
        for y in range(self._h):
            for x in range(self._w):
                if out[y][x] == old:
                    out[y][x] = new
        return Grid(out)

    def fill_rect(self, x, y, w, h, color):
        out = self._mut()
        for dy in range(h):
            for dx in range(w):
                tx, ty = x + dx, y + dy
                if 0 <= tx < self._w and 0 <= ty < self._h:
                    out[ty][tx] = color
        return Grid(out)

    def flood_fill(self, x, y, color):
        target = self._rows[y][x]
        if target == color:
            return self.copy()
        out = self._mut()
        stack = [(x, y)]
        seen = set()
        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in seen: continue
            seen.add((cx, cy))
            if 0 <= cx < self._w and 0 <= cy < self._h and out[cy][cx] == target:
                out[cy][cx] = color
                stack.extend([(cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)])
        return Grid(out)

    # --- Structural ---
    def crop(self, x, y, w, h):
        return Grid([[self._rows[y + dy][x + dx] for dx in range(w)] for dy in range(h)])

    def expand(self, new_h, new_w, fill=0):
        out = [[fill] * new_w for _ in range(new_h)]
        for y in range(min(self._h, new_h)):
            for x in range(min(self._w, new_w)):
                out[y][x] = self._rows[y][x]
        return Grid(out)

    def copy_region(self, sx, sy, w, h, dx, dy):
        out = self._mut()
        for ry in range(h):
            for rx in range(w):
                if (0 <= sx + rx < self._w and 0 <= sy + ry < self._h
                        and 0 <= dx + rx < self._w and 0 <= dy + ry < self._h):
                    out[dy + ry][dx + rx] = self._rows[sy + ry][sx + rx]
        return Grid(out)

    def overlay(self, other, x=0, y=0, mask_color=None):
        out = self._mut()
        for oy in range(other.height):
            for ox in range(other.width):
                tx, ty = x + ox, y + oy
                if 0 <= tx < self._w and 0 <= ty < self._h:
                    v = other._rows[oy][ox]
                    if mask_color is None or v != mask_color:
                        out[ty][tx] = v
        return Grid(out)


class Action:
    """DSL action: apply() transforms a Grid."""
    def __init__(self, kind_, params=None):
        self.kind = kind_
        self.params = params or {}

    def apply(self, g):
        k = self.kind
        p = self.params
        if k == "rotate_cw":    return g.rotate_cw()
        if k == "rotate_ccw":   return g.rotate_ccw()
        if k == "rotate_180":   return g.rotate_180()
        if k == "flip_h":       return g.flip_h()
        if k == "flip_v":       return g.flip_v()
        if k == "translate":    return g.translate(p["dx"], p["dy"], p.get("fill", 0))
        if k == "recolor":      return g.recolor(p["old"], p["new"])
        if k == "fill_rect":    return g.fill_rect(p["x"], p["y"], p["w"], p["h"], p["color"])
        if k == "flood_fill":   return g.flood_fill(p["x"], p["y"], p["color"])
        if k == "crop":         return g.crop(p["x"], p["y"], p["w"], p["h"])
        if k == "expand":       return g.expand(p["new_h"], p["new_w"], p.get("fill", 0))
        if k == "copy_region":  return g.copy_region(p["sx"], p["sy"], p["w"], p["h"], p["dx"], p["dy"])
        if k == "overlay":      return g.overlay(p["other"], p.get("x", 0), p.get("y", 0), p.get("mask_color"))
        if k == "compose":      return p["second"].apply(p["first"].apply(g))
        if k == "repeat":
            for _ in range(p["n"]): g = p["action"].apply(g)
            return g
        if k == "conditional":
            c = p["cond"]
            if c == "has_color_1": cond = g.has_color(1)
            elif c == "has_color_2": cond = g.has_color(2)
            elif c == "width_gt_height": cond = g.width > g.height
            elif c == "height_gt_width": cond = g.height > g.width
            else: cond = False
            return p["then_a"].apply(g) if cond else p["else_a"].apply(g)
        return g.copy()


_ACTION_COST = {
    "rotate_cw": 1, "rotate_ccw": 1, "rotate_180": 1,
    "flip_h": 1, "flip_v": 1, "translate": 2,
    "recolor": 2, "fill_rect": 4, "flood_fill": 3,
    "crop": 3, "expand": 3, "copy_region": 4, "overlay": 5,
    "compose": 0, "repeat": 0, "conditional": 0,
}


def _cost(prog):
    if isinstance(prog, Action):
        if prog.kind == "compose":
            return _cost(prog.params["first"]) + _cost(prog.params["second"])
        if prog.kind == "repeat":
            return _cost(prog.params["action"]) * prog.params["n"]
        if prog.kind == "conditional":
            return 1 + _cost(prog.params["then_a"]) + _cost(prog.params["else_a"])
        return _ACTION_COST.get(prog.kind, 5)
    return 5


_ATOMICS = [
    ("rotate_cw", {}), ("rotate_ccw", {}), ("rotate_180", {}),
    ("flip_h", {}), ("flip_v", {}),
    ("translate", {"dx": 1, "dy": 0}), ("translate", {"dx": -1, "dy": 0}),
    ("translate", {"dx": 0, "dy": 1}), ("translate", {"dx": 0, "dy": -1}),
    ("recolor", {"old": 0, "new": 1}), ("recolor", {"old": 1, "new": 0}),
    ("fill_rect", {"x": 0, "y": 0, "w": 2, "h": 2, "color": 0}),
    ("flood_fill", {"x": 0, "y": 0, "color": 0}),
    ("crop", {"x": 0, "y": 0, "w": 2, "h": 2}),
    ("expand", {"new_h": 4, "new_w": 4}),
]


def _eval(prog, pairs):
    total = 0
    wrong = 0
    for inp, out in pairs:
        try:
            pred = prog.apply(inp)
            h = max(pred.height, out.height)
            w = max(pred.width, out.width)
            for y in range(h):
                for x in range(w):
                    pv = pred.get(x, y) if x < pred.width and y < pred.height else -1
                    ov = out.get(x, y) if x < out.width and y < out.height else -1
                    if pv != ov: wrong += 1
                    total += 1
        except Exception:
            wrong += out.height * out.width
            total += out.height * out.width
    return wrong / max(total, 1)


def solve(task_json):
    train = task_json.get("train", [])
    test = task_json.get("test", [])
    if not train or not test:
        return [[0]]
    pairs = [(Grid(p["input"]), Grid(p["output"])) for p in train]
    test_inp = Grid(test[0]["input"])

    if all(inp == out for inp, out in pairs):
        return test_inp.as_list()

    # Build dynamic atomics from colours in the task
    in_cols, out_cols = set(), set()
    for inp, out in pairs:
        in_cols |= inp.colours()
        out_cols |= out.colours()
    atoms = list(_ATOMICS)
    for old in in_cols:
        for new in out_cols:
            if old != new:
                atoms.append(("recolor", {"old": old, "new": new}))

    beam = []  # (prog, cost, error)
    for kind, params in atoms:
        prog = Action(kind, params)
        err = _eval(prog, pairs)
        if err < 1.0:
            beam.append((prog, _cost(prog), err))

    if not beam:
        return test_inp.as_list()

    beam.sort(key=lambda x: x[1] + x[2] * 100)
    beam = beam[:80]
    for prog, _, err in beam:
        if err == 0.0:
            return prog.apply(test_inp).as_list()

    for _depth in range(2, 7):
        nb = []
        for parent, _, _ in beam:
            for kind, params in atoms:
                child = Action("compose", {"first": parent, "second": Action(kind, params)})
                nb.append((child, _cost(child), _eval(child, pairs)))
        beam = sorted(beam + nb, key=lambda x: x[1] + x[2] * 100)[:80]
        for prog, _, err in beam:
            if err == 0.0:
                return prog.apply(test_inp).as_list()

    return beam[0][0].apply(test_inp).as_list()


def main():
    if len(sys.argv) < 2:
        print("Usage: python exported_solver.py <task.json>", file=sys.stderr)
        sys.exit(1)
    with open(sys.argv[1]) as f:
        task = json.load(f)
    output = solve(task)
    print(json.dumps(output))


if __name__ == "__main__":
    main()
'''
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(source)
        logger.info(f"Solver exported to {path}")


def _find_latest_metadata(output_dir: Path) -> Optional[Path]:
    """Find the metadata file with the highest round number, preferring 'final'."""
    metadata_files = list(output_dir.glob("metadata_*.json"))
    if not metadata_files:
        return None

    # Prefer 'final' if it exists
    final = output_dir / "metadata_final.json"
    if final in metadata_files:
        return final

    # Otherwise find the one with the highest round number
    def _round_num(p: Path) -> int:
        stem = p.stem.replace("metadata_", "")
        if stem.startswith("round_"):
            try:
                return int(stem.split("_")[1])
            except (IndexError, ValueError):
                return 0
        return 0

    return max(metadata_files, key=_round_num)


