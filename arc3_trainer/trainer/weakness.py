"""
WeaknessAnalyzer — analyse the CapabilityProfile to identify the agent's
weakest areas, which the adversarial sampler can then target.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from arc3_trainer.trainer.capability import CapabilityProfile


@dataclass
class Weakness:
    """A specific weakness identified."""
    action_kind: str
    difficulty: int
    success_rate: float
    sample_count: int

    @property
    def severity(self) -> float:
        """0 = no weakness, 1 = critical (never succeeds)."""
        return 1.0 - self.success_rate


class WeaknessAnalyzer:
    """Analyse a capability profile to find weaknesses."""

    def __init__(self, min_samples: int = 3):
        self.min_samples = min_samples

    def analyse(self, profile: CapabilityProfile) -> List[Weakness]:
        """Find all weaknesses in the profile."""
        weaknesses: List[Weakness] = []

        for kind, diff_stats in profile.matrix.items():
            for diff, stats in diff_stats.items():
                if stats.total >= self.min_samples and stats.rate < 0.7:
                    weaknesses.append(Weakness(
                        action_kind=kind,
                        difficulty=diff,
                        success_rate=stats.rate,
                        sample_count=stats.total,
                    ))

        weaknesses.sort(key=lambda w: w.severity, reverse=True)
        return weaknesses

    def top_weaknesses(self, profile: CapabilityProfile, n: int = 5) -> List[Weakness]:
        """Return the n most severe weaknesses."""
        return self.analyse(profile)[:n]

    def weakness_summary(self, profile: CapabilityProfile) -> str:
        """Human-readable summary of current weaknesses."""
        weaknesses = self.analyse(profile)
        if not weaknesses:
            return "No significant weaknesses detected."

        lines = ["Top Weaknesses:"]
        for w in weaknesses[:5]:
            lines.append(
                f"  - {w.action_kind} @ diff={w.difficulty}: "
                f"{w.success_rate:.0%} success ({w.sample_count} trials)"
            )
        return "\n".join(lines)

    def weakness_weights(self, profile: CapabilityProfile) -> Dict[str, float]:
        """Return action type weights biased toward weaknesses.

        Weak action types get higher weight so the adversarial sampler
        generates more of them.
        """
        weaknesses = self.analyse(profile)
        weights: Dict[str, float] = {}

        # Default neutral weights
        for kind in ["rotate_cw", "rotate_ccw", "rotate_180",
                     "flip_h", "flip_v", "translate",
                     "recolor", "fill_rect", "flood_fill",
                     "crop", "expand", "copy_region", "overlay"]:
            weights[kind] = 1.0

        # Boost weak kinds
        for w in weaknesses:
            boost = 1.0 + w.severity * 4.0  # up to 5x for total failures
            weights[w.action_kind] = max(weights.get(w.action_kind, 1.0), boost)

        return weights
