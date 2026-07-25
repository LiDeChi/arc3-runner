"""Tests for the trainer module."""
import unittest
import tempfile
from pathlib import Path
from arc3_trainer.trainer.capability import CapabilityProfile, ActionStats
from arc3_trainer.trainer.weakness import WeaknessAnalyzer
from arc3_trainer.trainer.adversarial import AdversarialSampler
from arc3_trainer.trainer.curriculum import CurriculumScheduler
from arc3_trainer.trainer.loop import TrainingLoop, TrainConfig


class TestCapabilityProfile(unittest.TestCase):

    def setUp(self):
        self.profile = CapabilityProfile()

    def test_record_and_rate(self):
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("rotate_cw", 1, False)
        self.assertEqual(self.profile.get_rate("rotate_cw", 1), 0.5)
        self.assertEqual(self.profile.overall_rate(), 0.5)

    def test_rate_by_kind(self):
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("recolor", 1, False)
        self.assertEqual(self.profile.rate_by_kind("rotate_cw"), 1.0)

    def test_worst_kinds(self):
        self.profile.record("a", 1, True)
        self.profile.record("b", 1, False)
        self.profile.record("b", 2, False)
        worst = self.profile.worst_kinds(2)
        self.assertEqual(worst[0][0], "b")

    def test_save_and_load(self):
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("recolor", 2, False)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
            self.profile.save(path)
        loaded = CapabilityProfile.load(path)
        self.assertEqual(loaded.get_rate("rotate_cw", 1), 1.0)
        self.assertEqual(loaded.get_rate("recolor", 2), 0.0)
        Path(path).unlink()


class TestWeaknessAnalyzer(unittest.TestCase):

    def setUp(self):
        self.analyzer = WeaknessAnalyzer(min_samples=2)
        self.profile = CapabilityProfile()

    def test_no_weaknesses(self):
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("rotate_cw", 1, True)
        weaknesses = self.analyzer.analyse(self.profile)
        self.assertEqual(len(weaknesses), 0)

    def test_with_weakness(self):
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("rotate_cw", 1, True)
        self.profile.record("recolor", 1, False)
        self.profile.record("recolor", 1, False)
        weaknesses = self.analyzer.analyse(self.profile)
        self.assertGreaterEqual(len(weaknesses), 1)
        self.assertEqual(weaknesses[0].action_kind, "recolor")

    def test_weights(self):
        self.profile.record("recolor", 1, False)
        self.profile.record("recolor", 1, False)
        self.profile.record("recolor", 1, False)
        weights = self.analyzer.weakness_weights(self.profile)
        self.assertGreater(weights.get("recolor", 1.0), 1.0)


class TestCurriculumScheduler(unittest.TestCase):

    def setUp(self):
        self.curriculum = CurriculumScheduler()

    def test_initial_stage(self):
        self.assertEqual(self.curriculum.current_stage.name, "S1: Atomic")
        self.assertEqual(self.curriculum.current_stage_index, 0)

    def test_advance(self):
        profile = CapabilityProfile()
        profile.record("rotate_cw", 1, True)
        profile.record("rotate_cw", 1, True)
        # Override min_rounds to 0 for testing
        self.curriculum.stages[0].min_rounds = 0
        self.curriculum.stages[0].max_rounds = 5
        should = self.curriculum.should_advance(profile)
        self.assertTrue(should)

    def test_advance_method(self):
        self.curriculum.advance()
        self.assertEqual(self.curriculum.current_stage_index, 1)
        self.assertEqual(self.curriculum.current_stage.name, "S2: Composition")


if __name__ == "__main__":
    unittest.main()
