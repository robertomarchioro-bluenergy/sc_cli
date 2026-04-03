"""Test per il modulo Difficulty — preset e serializzazione."""

import pytest

from src.engine.difficulty import DifficultyConfig, DifficultyPreset


class TestDifficultyPreset:
    """Test creazione da preset"""

    def test_all_presets_create(self):
        for preset in DifficultyPreset:
            config = DifficultyConfig.from_preset(preset)
            assert config.preset == preset

    def test_easy_is_easier(self):
        easy = DifficultyConfig.from_preset(DifficultyPreset.EASY)
        normal = DifficultyConfig.from_preset(DifficultyPreset.NORMAL)
        assert easy.enemy_accuracy < normal.enemy_accuracy
        assert easy.repair_speed > normal.repair_speed
        assert easy.officer_ai_quality > normal.officer_ai_quality

    def test_doom_is_harder(self):
        doom = DifficultyConfig.from_preset(DifficultyPreset.DOOM)
        normal = DifficultyConfig.from_preset(DifficultyPreset.NORMAL)
        assert doom.enemy_accuracy > normal.enemy_accuracy
        assert doom.morale_decay > normal.morale_decay
        assert doom.repair_speed < normal.repair_speed

    def test_normal_is_baseline(self):
        normal = DifficultyConfig.from_preset(DifficultyPreset.NORMAL)
        assert normal.enemy_accuracy == 1.0
        assert normal.resource_drain == 1.0
        assert normal.repair_speed == 1.0


class TestDifficultySerialization:
    """Test serializzazione"""

    def test_roundtrip(self):
        config = DifficultyConfig.from_preset(DifficultyPreset.HARD)
        d = config.to_dict()
        restored = DifficultyConfig.from_dict(d)
        assert restored.preset == DifficultyPreset.HARD
        assert restored.enemy_accuracy == config.enemy_accuracy
        assert restored.repair_speed == config.repair_speed
