"""
Modello della nave del giocatore.
Ogni classe nave ha stats base e modificatori unici che influenzano
combattimento, navigazione e morale dell'equipaggio.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ShipClass(Enum):
    """Classi nave disponibili"""
    CONSTITUTION = "Constitution"
    CONSTITUTION_REFIT = "Constitution Refit"
    GALAXY = "Galaxy"
    SOVEREIGN = "Sovereign"
    DEFIANT = "Defiant"
    INTREPID = "Intrepid"
    EXCELSIOR = "Excelsior"


@dataclass
class ShipClassStats:
    """Stats base per una classe nave"""
    crew: int
    energy: float
    shields: float
    torpedoes: int
    dilithium: int
    # Modificatori speciali
    morale_modifier: float = 1.0
    low_maneuverability: bool = False
    hull_resistance: float = 1.0        # moltiplicatore danno ricevuto (< 1.0 = più resistente)
    torpedo_modifier: float = 1.0
    shield_modifier: float = 1.0
    sensor_range_modifier: float = 1.0
    computer_bonus: int = 0
    energy_modifier: float = 1.0
    dilithium_consumption_modifier: float = 1.0


# Stats base per ogni classe nave
SHIP_CLASS_STATS: dict[ShipClass, ShipClassStats] = {
    ShipClass.CONSTITUTION: ShipClassStats(
        crew=430, energy=5000, shields=100, torpedoes=20, dilithium=100,
        morale_modifier=1.10,
    ),
    ShipClass.CONSTITUTION_REFIT: ShipClassStats(
        crew=430, energy=5500, shields=110, torpedoes=22, dilithium=110,
        morale_modifier=1.10,
    ),
    ShipClass.GALAXY: ShipClassStats(
        crew=1014, energy=8000, shields=150, torpedoes=35, dilithium=200,
        low_maneuverability=True,
    ),
    ShipClass.SOVEREIGN: ShipClassStats(
        crew=855, energy=7500, shields=140, torpedoes=40, dilithium=180,
        hull_resistance=0.80,
    ),
    ShipClass.DEFIANT: ShipClassStats(
        crew=50, energy=3000, shields=80, torpedoes=48, dilithium=60,
        torpedo_modifier=1.50, shield_modifier=1.20,
    ),
    ShipClass.INTREPID: ShipClassStats(
        crew=141, energy=4500, shields=120, torpedoes=25, dilithium=130,
        sensor_range_modifier=1.30, computer_bonus=10, energy_modifier=0.80,
    ),
    ShipClass.EXCELSIOR: ShipClassStats(
        crew=750, energy=6000, shields=120, torpedoes=30, dilithium=150,
        dilithium_consumption_modifier=0.80,
    ),
}


@dataclass
class Ship:
    """Nave del giocatore con stato corrente"""
    name: str                                    # nome scelto dal giocatore
    ship_class: ShipClass
    energy: float                                # 0–max_energia (pool condiviso)
    energy_max: float
    dilithium: int                               # 0–max_dilithium
    dilithium_max: int
    torpedoes: int                               # 0–max_siluri
    torpedoes_max: int
    shields_pct: float                           # 0–100%
    hull_pct: float                              # 0–100%
    crew: int                                    # 0–max_equipaggio
    crew_max: int
    morale_pct: float                            # 0–100%
    position: tuple[int, int, int, int] = (1, 1, 1, 1)  # (q_row, q_col, s_row, s_col)
    # Modificatori dalla classe nave
    low_maneuverability: bool = False
    hull_resistance: float = 1.0
    torpedo_modifier: float = 1.0
    shield_modifier: float = 1.0
    sensor_range_modifier: float = 1.0
    computer_bonus: int = 0
    dilithium_consumption_modifier: float = 1.0
    morale_modifier: float = 1.0

    @classmethod
    def create(cls, name: str, ship_class: ShipClass) -> "Ship":
        """Crea nave con stats base dalla classe + modificatori"""
        stats = SHIP_CLASS_STATS[ship_class]
        energy_max = stats.energy * stats.energy_modifier
        shields_base = stats.shields * stats.shield_modifier
        torpedoes = int(stats.torpedoes * stats.torpedo_modifier)

        return cls(
            name=name,
            ship_class=ship_class,
            energy=energy_max,
            energy_max=energy_max,
            dilithium=stats.dilithium,
            dilithium_max=stats.dilithium,
            torpedoes=torpedoes,
            torpedoes_max=torpedoes,
            shields_pct=shields_base,
            hull_pct=100.0,
            crew=stats.crew,
            crew_max=stats.crew,
            morale_pct=min(100.0, 85.0 * stats.morale_modifier),
            low_maneuverability=stats.low_maneuverability,
            hull_resistance=stats.hull_resistance,
            torpedo_modifier=stats.torpedo_modifier,
            shield_modifier=stats.shield_modifier,
            sensor_range_modifier=stats.sensor_range_modifier,
            computer_bonus=stats.computer_bonus,
            dilithium_consumption_modifier=stats.dilithium_consumption_modifier,
            morale_modifier=stats.morale_modifier,
        )

    def apply_hull_damage(self, raw_damage_pct: float) -> float:
        """Applica danno allo scafo considerando la resistenza. Ritorna danno effettivo."""
        effective = raw_damage_pct * self.hull_resistance
        self.hull_pct = max(0.0, self.hull_pct - effective)
        return effective

    def consume_energy(self, amount: float) -> bool:
        """Consuma energia. Ritorna False se insufficiente."""
        if self.energy < amount:
            return False
        self.energy -= amount
        return True

    def consume_dilithium(self, amount: int) -> bool:
        """Consuma dilithium. Ritorna False se insufficiente."""
        if self.dilithium < amount:
            return False
        self.dilithium -= amount
        return True

    def fire_torpedo(self) -> bool:
        """Lancia un siluro. Ritorna False se esauriti."""
        if self.torpedoes <= 0:
            return False
        self.torpedoes -= 1
        return True

    def lose_crew(self, count: int) -> int:
        """Perde membri dell'equipaggio. Ritorna il numero effettivo perso."""
        actual = min(count, self.crew)
        self.crew -= actual
        return actual

    def adjust_morale(self, delta: float) -> None:
        """Modifica il morale dell'equipaggio"""
        self.morale_pct = max(0.0, min(100.0, self.morale_pct + delta))

    def is_destroyed(self) -> bool:
        """Verifica se la nave è distrutta"""
        return self.hull_pct <= 0.0 or self.crew <= 0

    def to_dict(self) -> dict:
        """Serializza la nave"""
        return {
            "name": self.name,
            "ship_class": self.ship_class.value,
            "energy": self.energy,
            "energy_max": self.energy_max,
            "dilithium": self.dilithium,
            "dilithium_max": self.dilithium_max,
            "torpedoes": self.torpedoes,
            "torpedoes_max": self.torpedoes_max,
            "shields_pct": self.shields_pct,
            "hull_pct": self.hull_pct,
            "crew": self.crew,
            "crew_max": self.crew_max,
            "morale_pct": self.morale_pct,
            "position": list(self.position),
            "low_maneuverability": self.low_maneuverability,
            "hull_resistance": self.hull_resistance,
            "torpedo_modifier": self.torpedo_modifier,
            "shield_modifier": self.shield_modifier,
            "sensor_range_modifier": self.sensor_range_modifier,
            "computer_bonus": self.computer_bonus,
            "dilithium_consumption_modifier": self.dilithium_consumption_modifier,
            "morale_modifier": self.morale_modifier,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Ship":
        """Deserializza la nave"""
        return cls(
            name=d["name"],
            ship_class=ShipClass(d["ship_class"]),
            energy=d["energy"],
            energy_max=d["energy_max"],
            dilithium=d["dilithium"],
            dilithium_max=d["dilithium_max"],
            torpedoes=d["torpedoes"],
            torpedoes_max=d["torpedoes_max"],
            shields_pct=d["shields_pct"],
            hull_pct=d["hull_pct"],
            crew=d["crew"],
            crew_max=d["crew_max"],
            morale_pct=d["morale_pct"],
            position=tuple(d["position"]),
            low_maneuverability=d.get("low_maneuverability", False),
            hull_resistance=d.get("hull_resistance", 1.0),
            torpedo_modifier=d.get("torpedo_modifier", 1.0),
            shield_modifier=d.get("shield_modifier", 1.0),
            sensor_range_modifier=d.get("sensor_range_modifier", 1.0),
            computer_bonus=d.get("computer_bonus", 0),
            dilithium_consumption_modifier=d.get("dilithium_consumption_modifier", 1.0),
            morale_modifier=d.get("morale_modifier", 1.0),
        )
