"""
Preset e modifier granulari per il sistema di difficoltà.
Ogni preset bilancia precisione nemica, consumo risorse, pressione temporale
e qualità dei suggerimenti degli ufficiali AI.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class DifficultyPreset(Enum):
    """Livelli di difficoltà predefiniti"""
    EASY = "Esploratore"
    NORMAL = "Ufficiale"
    HARD = "Comandante"
    DOOM = "Capitano Kirk"


@dataclass
class DifficultyConfig:
    """Configurazione granulare della difficoltà di gioco"""
    preset: DifficultyPreset
    enemy_accuracy: float       # precisione colpi nemici
    enemy_aggression: float     # frequenza attacchi iniziati dal nemico
    resource_drain: float       # velocità consumo energia e dilithium
    stardate_pressure: float    # velocità avanzamento stardate
    repair_speed: float         # velocità riparazioni sistemi
    torpedo_scarcity: float     # siluri trovati alle basi
    officer_ai_quality: float   # qualità suggerimenti ufficiali
    morale_decay: float         # velocità calo morale dopo perdite

    @classmethod
    def from_preset(cls, preset: DifficultyPreset) -> "DifficultyConfig":
        """Crea configurazione dai valori predefiniti per il preset selezionato"""
        presets: dict[DifficultyPreset, dict[str, float]] = {
            DifficultyPreset.EASY: {
                "enemy_accuracy": 0.6,
                "enemy_aggression": 0.5,
                "resource_drain": 0.7,
                "stardate_pressure": 0.7,
                "repair_speed": 1.5,
                "torpedo_scarcity": 0.5,
                "officer_ai_quality": 1.5,
                "morale_decay": 0.5,
            },
            DifficultyPreset.NORMAL: {
                "enemy_accuracy": 1.0,
                "enemy_aggression": 1.0,
                "resource_drain": 1.0,
                "stardate_pressure": 1.0,
                "repair_speed": 1.0,
                "torpedo_scarcity": 1.0,
                "officer_ai_quality": 1.0,
                "morale_decay": 1.0,
            },
            DifficultyPreset.HARD: {
                "enemy_accuracy": 1.4,
                "enemy_aggression": 1.5,
                "resource_drain": 1.3,
                "stardate_pressure": 1.2,
                "repair_speed": 0.7,
                "torpedo_scarcity": 1.2,
                "officer_ai_quality": 0.8,
                "morale_decay": 1.3,
            },
            DifficultyPreset.DOOM: {
                "enemy_accuracy": 1.8,
                "enemy_aggression": 2.0,
                "resource_drain": 1.6,
                "stardate_pressure": 1.5,
                "repair_speed": 0.5,
                "torpedo_scarcity": 1.5,
                "officer_ai_quality": 0.6,
                "morale_decay": 2.0,
            },
        }
        values = presets[preset]
        return cls(preset=preset, **values)

    def to_dict(self) -> dict:
        """Serializza la configurazione in dizionario"""
        return {
            "preset": self.preset.value,
            "enemy_accuracy": self.enemy_accuracy,
            "enemy_aggression": self.enemy_aggression,
            "resource_drain": self.resource_drain,
            "stardate_pressure": self.stardate_pressure,
            "repair_speed": self.repair_speed,
            "torpedo_scarcity": self.torpedo_scarcity,
            "officer_ai_quality": self.officer_ai_quality,
            "morale_decay": self.morale_decay,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "DifficultyConfig":
        """Deserializza da dizionario"""
        preset = DifficultyPreset(d["preset"])
        return cls(
            preset=preset,
            enemy_accuracy=d["enemy_accuracy"],
            enemy_aggression=d["enemy_aggression"],
            resource_drain=d["resource_drain"],
            stardate_pressure=d["stardate_pressure"],
            repair_speed=d["repair_speed"],
            torpedo_scarcity=d["torpedo_scarcity"],
            officer_ai_quality=d["officer_ai_quality"],
            morale_decay=d["morale_decay"],
        )
