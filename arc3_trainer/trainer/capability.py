"""
CapabilityProfile — tracks agent performance by action type and difficulty.

Maintains a success rate matrix: action_kind × difficulty_level → 
(success_count, total_count). Used by WeaknessAnalyzer to identify
weak spots.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ActionStats:
    """Statistics for a single action type at a specific difficulty."""
    success: int = 0
    total: int = 0

    @property
    def rate(self) -> float:
        return self.success / max(self.total, 1)

    def merge(self, other: "ActionStats") -> "ActionStats":
        return ActionStats(
            success=self.success + other.success,
            total=self.total + other.total,
        )


@dataclass
class CapabilityProfile:
    """Full capability profile of the agent."""
    # matrix[kind][difficulty] -> ActionStats
    matrix: Dict[str, Dict[int, ActionStats]] = field(default_factory=dict)

    def record(self, action_kind: str, difficulty: int, success: bool) -> None:
        """Record one trial outcome."""
        if action_kind not in self.matrix:
            self.matrix[action_kind] = {}
        if difficulty not in self.matrix[action_kind]:
            self.matrix[action_kind][difficulty] = ActionStats()
        stats = self.matrix[action_kind][difficulty]
        stats.total += 1
        if success:
            stats.success += 1

    def get_rate(self, action_kind: str, difficulty: int) -> float:
        """Get success rate for a (kind, difficulty) combo."""
        return self.matrix.get(action_kind, {}).get(difficulty, ActionStats()).rate

    def overall_rate(self) -> float:
        """Overall success rate across everything."""
        total_s = sum(
            stats.success for kind_stats in self.matrix.values()
            for stats in kind_stats.values()
        )
        total_t = sum(
            stats.total for kind_stats in self.matrix.values()
            for stats in kind_stats.values()
        )
        return total_s / max(total_t, 1)

    def rate_by_kind(self, kind: str) -> float:
        """Success rate for a specific action kind."""
        if kind not in self.matrix:
            return 0.0
        total_s = sum(stats.success for stats in self.matrix[kind].values())
        total_t = sum(stats.total for stats in self.matrix[kind].values())
        return total_s / max(total_t, 1)

    def worst_kinds(self, n: int = 3) -> List[Tuple[str, float]]:
        """Return the n worst-performing action kinds."""
        rates = [(k, self.rate_by_kind(k)) for k in self.matrix]
        rates.sort(key=lambda x: x[1])
        return rates[:n]

    def to_dict(self) -> dict:
        """Serialise to dict."""
        return {
            kind: {str(diff): {"success": s.success, "total": s.total}
                   for diff, s in stats.items()}
            for kind, stats in self.matrix.items()
        }

    def save(self, path: str | Path) -> None:
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "CapabilityProfile":
        with open(path) as f:
            data = json.load(f)
        profile = cls()
        for kind, diff_data in data.items():
            for diff_str, s in diff_data.items():
                diff = int(diff_str)
                profile.matrix.setdefault(kind, {})[diff] = ActionStats(
                    success=s["success"], total=s["total"]
                )
        return profile
