"""
Sistema di combattimento a turni.
Formule colpo faser/siluro, AI nemica deterministica,
check imboscata e struttura del turno di combattimento.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum

from .ship import Ship
from .systems import ShipSystem, SystemName, SystemStatus
from .galaxy import Galaxy, CellContent
from .difficulty import DifficultyConfig


class GameEngineError(Exception):
    """Errore generico del motore di gioco"""
    pass


class CombatAction(Enum):
    """Azioni possibili per l'AI nemica"""
    ATTACK = "attacco"
    ADVANCE = "avanzamento"
    RETREAT = "ritirata"
    MANEUVER = "manovra"
    CLOAK_AND_WAIT = "occultamento"


@dataclass
class Enemy:
    """Entità nemica in combattimento"""
    enemy_type: CellContent
    hull_pct: float = 100.0
    shields_pct: float = 100.0
    position: tuple[int, int, int, int] = (1, 1, 1, 1)
    faser_resistance: float = 0.0  # Borg: resistenza adattiva ai faser (cap 0.90)
    cloaked: bool = False
    was_in_sector: bool = False    # era nel settore prima dell'ingresso del giocatore

    def is_destroyed(self) -> bool:
        return self.hull_pct <= 0.0

    def apply_damage(self, damage: float) -> None:
        """Applica danno: prima scudi, poi scafo"""
        if self.shields_pct > 0:
            shield_absorb = min(self.shields_pct, damage * 0.6)
            self.shields_pct -= shield_absorb
            remaining = damage - shield_absorb / 0.6 * 0.4 if shield_absorb > 0 else damage
            if remaining > 0:
                self.hull_pct = max(0.0, self.hull_pct - remaining * 0.5)
        else:
            self.hull_pct = max(0.0, self.hull_pct - damage * 0.5)

    def to_dict(self) -> dict:
        return {
            "enemy_type": self.enemy_type.value,
            "hull_pct": self.hull_pct,
            "shields_pct": self.shields_pct,
            "position": list(self.position),
            "faser_resistance": self.faser_resistance,
            "cloaked": self.cloaked,
            "was_in_sector": self.was_in_sector,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Enemy":
        return cls(
            enemy_type=CellContent(d["enemy_type"]),
            hull_pct=d["hull_pct"],
            shields_pct=d["shields_pct"],
            position=tuple(d["position"]),
            faser_resistance=d.get("faser_resistance", 0.0),
            cloaked=d.get("cloaked", False),
            was_in_sector=d.get("was_in_sector", False),
        )


@dataclass
class CombatResult:
    """Risultato di un'azione di combattimento"""
    hit: bool
    damage: float
    message: str
    critical: bool = False
    system_damaged: str | None = None


def check_ambush(
    enemy: Enemy,
    galaxy: Galaxy,
    systems: dict[SystemName, ShipSystem],
    ship_position: tuple[int, int, int, int],
) -> bool:
    """
    Verifica se il nemico può tendere un'imboscata.
    Condizioni: nemico era nel settore prima dell'ingresso AND
    (nebula OR sensori.integrity < 30 OR (romulano AND cloaking))
    """
    if not enemy.was_in_sector:
        return False

    q_row, q_col = ship_position[0], ship_position[1]

    # Condizione 1: nebula
    if galaxy.is_nebula(q_row, q_col):
        return True

    # Condizione 2: sensori degradati
    sensor_sys = systems.get(SystemName.SENSORS)
    if sensor_sys and sensor_sys.integrity < 30:
        return True

    # Condizione 3: Romulano con cloaking
    if enemy.enemy_type == CellContent.ROMULAN and enemy.cloaked:
        return True

    return False


def calculate_distance(
    pos1: tuple[int, int, int, int],
    pos2: tuple[int, int, int, int],
) -> float:
    """Calcola distanza tra due posizioni in settori (griglia 64x64)"""
    abs_r1 = (pos1[0] - 1) * 8 + (pos1[2] - 1)
    abs_c1 = (pos1[1] - 1) * 8 + (pos1[3] - 1)
    abs_r2 = (pos2[0] - 1) * 8 + (pos2[2] - 1)
    abs_c2 = (pos2[1] - 1) * 8 + (pos2[3] - 1)
    return ((abs_r1 - abs_r2) ** 2 + (abs_c1 - abs_c2) ** 2) ** 0.5


def in_range(enemy: Enemy, ship: Ship, max_range: float = 5.0) -> bool:
    """Verifica se il nemico è a portata di tiro"""
    dist = calculate_distance(enemy.position, ship.position)
    return dist <= max_range


def calcola_colpo_faser(
    energia_sparata: float,
    distanza: float,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    advice_followed: bool,
    difficulty: DifficultyConfig,
) -> tuple[bool, float]:
    """
    Calcola il risultato di un colpo faser.
    Restituisce (colpito: bool, danno: float)
    """
    targeting = systems.get(SystemName.TARGETING_COMPUTER)
    targeting_integrity = targeting.integrity if targeting else 50.0

    # Calcolo probabilità
    prob_hit = (
        0.90
        * (targeting_integrity / 100.0)
        * max(0.30, 1.0 - distanza * 0.10)
        * (ship.morale_pct / 100.0)
        * random.uniform(0.85, 1.15)
    )
    # Degrado computer di puntamento
    if targeting:
        prob_hit *= (1.0 - targeting.penalty)
    # Bonus computer Intrepid
    if ship.computer_bonus > 0:
        prob_hit *= (1.0 + ship.computer_bonus / 100.0)
    # Bonus se consiglio Tattico seguito
    if advice_followed:
        prob_hit *= 1.15

    prob_hit = min(0.99, max(0.01, prob_hit))
    colpito = random.random() < prob_hit

    if not colpito:
        return False, 0.0

    # Calcolo danno
    danno = (
        energia_sparata
        * 0.80
        * random.uniform(0.90, 1.10)
    )
    if advice_followed:
        danno *= 1.10

    return True, danno


def calcola_colpo_siluro(
    nemico_shields_pct: float,
    advice_followed: bool,
) -> float:
    """I siluri ignorano scudi al 30% (penetrazione fissa)"""
    scudi_effettivi = nemico_shields_pct * 0.70   # siluri penetrano 30% degli scudi
    danno_base = random.uniform(400.0, 600.0)
    danno = danno_base * (1.0 - scudi_effettivi / 100.0)
    if advice_followed:
        danno *= 1.10
    return danno


def check_torpedo_misfire(systems: dict[SystemName, ShipSystem]) -> bool:
    """
    Verifica se il lanciasiluri ha un misfiring.
    Sotto 50% → 10% probabilità misfiring; a 0% → OFFLINE
    """
    launcher = systems.get(SystemName.TORPEDO_LAUNCHER)
    if launcher is None:
        return True  # nessun lanciasiluri
    if launcher.status == SystemStatus.OFFLINE:
        return True  # offline
    if launcher.integrity < 50:
        return random.random() < 0.10
    return False


def calcola_colpo_nemico(
    enemy: Enemy,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    difficulty: DifficultyConfig,
) -> CombatResult:
    """Calcola il risultato di un attacco nemico"""
    distanza = calculate_distance(enemy.position, ship.position)

    # Precisione base nemica per tipo
    base_accuracy: dict[CellContent, float] = {
        CellContent.KLINGON: 0.70,
        CellContent.ROMULAN: 0.65,
        CellContent.BORG: 0.85,
        CellContent.SILENTI: 0.80,
    }
    accuracy = base_accuracy.get(enemy.enemy_type, 0.60) * difficulty.enemy_accuracy
    accuracy *= max(0.30, 1.0 - distanza * 0.08)

    hit = random.random() < accuracy
    if not hit:
        return CombatResult(
            hit=False,
            damage=0.0,
            message=f"{enemy.enemy_type.name} manca il bersaglio",
        )

    # Danno base per tipo nemico
    base_damage: dict[CellContent, float] = {
        CellContent.KLINGON: random.uniform(150, 300),
        CellContent.ROMULAN: random.uniform(120, 250),
        CellContent.BORG: random.uniform(250, 450),
        CellContent.SILENTI: random.uniform(200, 400),
    }
    raw_damage = base_damage.get(enemy.enemy_type, random.uniform(100, 200))

    # Scudi riducono il danno
    shield_gen = systems.get(SystemName.SHIELD_GENERATOR)
    shield_effectiveness = 1.0
    if shield_gen:
        shield_effectiveness = 1.0 - shield_gen.penalty
    damage_after_shields = raw_damage * (1.0 - ship.shields_pct / 100.0 * 0.8 * shield_effectiveness)

    # Verifica colpo critico (15% possibilità)
    critical = random.random() < 0.15
    system_damaged = None
    if critical:
        # Danno a sistema casuale
        damageable = [sn for sn in systems if systems[sn].integrity > 0]
        if damageable:
            target_sys = random.choice(damageable)
            crit_damage = random.uniform(10, 25)
            systems[target_sys].apply_damage(crit_damage)
            system_damaged = target_sys.value

    return CombatResult(
        hit=True,
        damage=damage_after_shields,
        message=f"{enemy.enemy_type.name} colpisce! Danno: {damage_after_shields:.0f}",
        critical=critical,
        system_damaged=system_damaged,
    )


# ── AI nemica deterministica ────────────────────────────────

def klingon_ai(nemico: Enemy, ship: Ship, systems: dict[SystemName, ShipSystem]) -> CombatAction:
    """Klingon: sempre aggressivi, non si ritirano mai"""
    if in_range(nemico, ship):
        return CombatAction.ATTACK
    return CombatAction.ADVANCE  # si avvicinano sempre


def romulan_ai(
    nemico: Enemy,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    galaxy: Galaxy,
) -> CombatAction:
    """Romulano: tattici, si ritirano sotto 30% scafo, usano nebule"""
    if nemico.hull_pct < 30:
        return CombatAction.RETREAT
    q_row, q_col = nemico.position[0], nemico.position[1]
    if galaxy.is_nebula(q_row, q_col) and not in_range(nemico, ship):
        return CombatAction.CLOAK_AND_WAIT  # tendono imboscate
    if in_range(nemico, ship):
        return CombatAction.ATTACK
    return CombatAction.MANEUVER


def borg_ai(
    nemico: Enemy,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    faser_hits_received: int,
) -> CombatAction:
    """Borg: adattano scudi ai faser dopo 2 colpi"""
    if faser_hits_received >= 2:
        nemico.faser_resistance = min(0.90, nemico.faser_resistance + 0.30)
    return CombatAction.ATTACK  # non si ritirano mai


def silenti_ai(
    nemico: Enemy,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    mission_id: str,
) -> CombatAction:
    """
    I Silenziosi: accerchiamento, non si ritirano, impulso annientamento.
    M01-M02: non appaiono in combattimento.
    M03+: attaccano con impulso annientamento.
    """
    if mission_id in ("M01", "M02"):
        return CombatAction.MANEUVER  # non combattono ancora
    # M03+: accerchiano e attaccano
    if in_range(nemico, ship):
        return CombatAction.ATTACK
    return CombatAction.ADVANCE


def get_enemy_action(
    nemico: Enemy,
    ship: Ship,
    systems: dict[SystemName, ShipSystem],
    galaxy: Galaxy,
    mission_id: str,
    faser_hits_on_enemy: int = 0,
) -> CombatAction:
    """Dispatcher per l'AI nemica basata sul tipo"""
    dispatch = {
        CellContent.KLINGON: lambda: klingon_ai(nemico, ship, systems),
        CellContent.ROMULAN: lambda: romulan_ai(nemico, ship, systems, galaxy),
        CellContent.BORG: lambda: borg_ai(nemico, ship, systems, faser_hits_on_enemy),
        CellContent.SILENTI: lambda: silenti_ai(nemico, ship, systems, mission_id),
    }
    action_fn = dispatch.get(nemico.enemy_type)
    if action_fn:
        return action_fn()
    return CombatAction.ATTACK


def apply_species_combat_bonus(
    damage: float,
    officer_species: str,
    is_retreat: bool = False,
) -> float:
    """Applica bonus/malus di specie al danno in combattimento"""
    bonuses: dict[str, float] = {
        "Klingon": 1.25,       # +25% danno
        "Andoriano": 1.15,     # +15% tattica posizionale
        "Betazoide": 0.90,     # -10% combat
        "Trill": 1.10,         # +10% a tutto
        "Umano": 1.05,         # +5% in situazioni nuove
    }
    modifier = bonuses.get(officer_species, 1.0)
    return damage * modifier
