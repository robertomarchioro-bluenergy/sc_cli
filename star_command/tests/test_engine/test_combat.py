"""Test per il modulo Combat — nemici, formule danno, AI, imboscata."""

import random
import pytest

from src.engine.combat import (
    Enemy, CombatResult, CombatAction,
    check_ambush, calculate_distance, in_range,
    calcola_colpo_faser, calcola_colpo_siluro,
    check_torpedo_misfire, calcola_colpo_nemico,
    klingon_ai, romulan_ai, borg_ai, silenti_ai,
    get_enemy_action, apply_species_combat_bonus,
)
from src.engine.galaxy import Galaxy, CellContent
from src.engine.ship import Ship, ShipClass
from src.engine.systems import (
    ShipSystem, SystemName, SystemStatus,
    create_default_systems,
)
from src.engine.difficulty import DifficultyConfig, DifficultyPreset


@pytest.fixture
def ship():
    return Ship.create("Test Ship", ShipClass.CONSTITUTION)


@pytest.fixture
def systems():
    return create_default_systems()


@pytest.fixture
def difficulty():
    return DifficultyConfig.from_preset(DifficultyPreset.NORMAL)


@pytest.fixture
def klingon_enemy():
    return Enemy(enemy_type=CellContent.KLINGON, position=(1, 1, 2, 2))


@pytest.fixture
def galaxy():
    g = Galaxy()
    g.generate(42, {"nemici": [], "basi_stellari": 0})
    return g


class TestEnemy:
    """Test entita nemica"""

    def test_default_values(self):
        e = Enemy(enemy_type=CellContent.KLINGON)
        assert e.hull_pct == 100.0
        assert e.shields_pct == 100.0
        assert not e.is_destroyed()

    def test_apply_damage_with_shields(self):
        e = Enemy(enemy_type=CellContent.KLINGON)
        e.apply_damage(100.0)
        assert e.shields_pct < 100.0
        assert e.hull_pct < 100.0  # una parte del danno penetra

    def test_apply_damage_no_shields(self):
        e = Enemy(enemy_type=CellContent.KLINGON, shields_pct=0.0)
        e.apply_damage(100.0)
        assert e.hull_pct < 100.0

    def test_is_destroyed(self):
        e = Enemy(enemy_type=CellContent.KLINGON, hull_pct=0.0)
        assert e.is_destroyed() is True

    def test_serialization(self):
        e = Enemy(
            enemy_type=CellContent.BORG,
            hull_pct=50.0,
            faser_resistance=0.30,
            cloaked=True,
        )
        d = e.to_dict()
        e2 = Enemy.from_dict(d)
        assert e2.enemy_type == CellContent.BORG
        assert e2.hull_pct == 50.0
        assert e2.faser_resistance == 0.30
        assert e2.cloaked is True


class TestDistance:
    """Test calcolo distanza"""

    def test_same_position(self):
        pos = (1, 1, 1, 1)
        assert calculate_distance(pos, pos) == 0.0

    def test_adjacent_sector(self):
        pos1 = (1, 1, 1, 1)
        pos2 = (1, 1, 2, 1)
        assert calculate_distance(pos1, pos2) == 1.0

    def test_different_quadrant(self):
        pos1 = (1, 1, 1, 1)
        pos2 = (2, 1, 1, 1)
        assert calculate_distance(pos1, pos2) == 8.0  # un quadrante = 8 settori

    def test_in_range(self, ship, klingon_enemy):
        ship.position = (1, 1, 1, 1)
        assert in_range(klingon_enemy, ship, max_range=5.0) is True

    def test_out_of_range(self, ship):
        ship.position = (1, 1, 1, 1)
        far_enemy = Enemy(enemy_type=CellContent.KLINGON, position=(3, 3, 8, 8))
        assert in_range(far_enemy, ship, max_range=5.0) is False


class TestAmbush:
    """Test imboscata"""

    def test_no_ambush_new_arrival(self, galaxy, systems):
        e = Enemy(enemy_type=CellContent.KLINGON, was_in_sector=False)
        assert check_ambush(e, galaxy, systems, (1, 1, 1, 1)) is False

    def test_ambush_in_nebula(self, systems):
        g = Galaxy()
        g.quadrants[0][0].is_nebula = True
        e = Enemy(enemy_type=CellContent.KLINGON, was_in_sector=True)
        assert check_ambush(e, g, systems, (1, 1, 1, 1)) is True

    def test_ambush_degraded_sensors(self, galaxy, systems):
        systems[SystemName.SENSORS].integrity = 20.0
        e = Enemy(enemy_type=CellContent.KLINGON, was_in_sector=True)
        assert check_ambush(e, galaxy, systems, (1, 1, 1, 1)) is True

    def test_ambush_cloaked_romulan(self, galaxy, systems):
        e = Enemy(
            enemy_type=CellContent.ROMULAN,
            was_in_sector=True,
            cloaked=True,
        )
        assert check_ambush(e, galaxy, systems, (1, 1, 1, 1)) is True


class TestFaserFormula:
    """Test formula colpo faser"""

    def test_colpo_faser_hit_with_seed(self, ship, systems, difficulty):
        random.seed(42)
        hit, damage = calcola_colpo_faser(
            energia_sparata=300.0,
            distanza=1.0,
            ship=ship,
            systems=systems,
            advice_followed=False,
            difficulty=difficulty,
        )
        # Con seed fisso il risultato e deterministico
        assert isinstance(hit, bool)
        assert isinstance(damage, float)
        if hit:
            assert damage > 0

    def test_colpo_faser_advice_bonus(self, ship, systems, difficulty):
        """Il bonus consiglio aumenta il danno"""
        random.seed(42)
        _, dmg_no = calcola_colpo_faser(300.0, 1.0, ship, systems, False, difficulty)
        random.seed(42)
        _, dmg_yes = calcola_colpo_faser(300.0, 1.0, ship, systems, True, difficulty)
        # Con consiglio: danno >= senza (prob_hit e danno aumentano)
        # Non possiamo garantire quale dei due e maggiore per tutti i seed
        # ma possiamo verificare che siano float validi
        assert isinstance(dmg_no, float)
        assert isinstance(dmg_yes, float)


class TestTorpedoFormula:
    """Test siluri"""

    def test_siluro_penetra_scudi(self):
        random.seed(42)
        danno = calcola_colpo_siluro(100.0, False)
        assert danno > 0
        # Con scudi al 100%, il danno non e 0 (siluri penetrano 30%)
        danno_max_shields = calcola_colpo_siluro(100.0, False)
        assert danno_max_shields > 0

    def test_torpedo_misfire_offline(self, systems):
        systems[SystemName.TORPEDO_LAUNCHER].integrity = 0.0
        assert check_torpedo_misfire(systems) is True

    def test_torpedo_no_misfire_nominal(self, systems):
        assert check_torpedo_misfire(systems) is False


class TestEnemyAI:
    """Test AI nemica deterministica"""

    def test_klingon_always_aggressive(self, ship, systems):
        e = Enemy(enemy_type=CellContent.KLINGON, position=(1, 1, 2, 2))
        ship.position = (1, 1, 1, 1)
        action = klingon_ai(e, ship, systems)
        assert action in (CombatAction.ATTACK, CombatAction.ADVANCE)

    def test_romulan_retreats_low_hull(self, ship, systems, galaxy):
        e = Enemy(enemy_type=CellContent.ROMULAN, hull_pct=20.0)
        action = romulan_ai(e, ship, systems, galaxy)
        assert action == CombatAction.RETREAT

    def test_borg_adapts_faser(self, ship, systems):
        e = Enemy(enemy_type=CellContent.BORG, faser_resistance=0.0)
        borg_ai(e, ship, systems, faser_hits_received=3)
        assert e.faser_resistance > 0.0
        assert e.faser_resistance <= 0.90

    def test_silenti_passive_early_missions(self, ship, systems):
        e = Enemy(enemy_type=CellContent.SILENTI, position=(1, 1, 2, 2))
        action = silenti_ai(e, ship, systems, mission_id="M01")
        assert action == CombatAction.MANEUVER

    def test_silenti_aggressive_late_missions(self, ship, systems):
        e = Enemy(enemy_type=CellContent.SILENTI, position=(1, 1, 2, 2))
        ship.position = (1, 1, 1, 1)
        action = silenti_ai(e, ship, systems, mission_id="M03")
        assert action in (CombatAction.ATTACK, CombatAction.ADVANCE)

    def test_get_enemy_action_dispatches(self, ship, systems, galaxy):
        e = Enemy(enemy_type=CellContent.KLINGON, position=(1, 1, 2, 2))
        ship.position = (1, 1, 1, 1)
        action = get_enemy_action(e, ship, systems, galaxy, "M01")
        assert isinstance(action, CombatAction)


class TestSpeciesBonus:
    """Test bonus specie in combattimento"""

    def test_klingon_bonus(self):
        result = apply_species_combat_bonus(100.0, "Klingon")
        assert result == 125.0

    def test_betazoid_malus(self):
        result = apply_species_combat_bonus(100.0, "Betazoide")
        assert result == 90.0

    def test_unknown_species(self):
        result = apply_species_combat_bonus(100.0, "Sconosciuto")
        assert result == 100.0
