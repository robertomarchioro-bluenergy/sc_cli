"""Test per il modulo Ship — creazione nave, risorse, danno, serializzazione."""

import pytest

from src.engine.ship import Ship, ShipClass, ShipClassStats, SHIP_CLASS_STATS


class TestShipCreation:
    """Test creazione nave da classe"""

    def test_create_constitution(self):
        ship = Ship.create("USS Enterprise", ShipClass.CONSTITUTION)
        assert ship.name == "USS Enterprise"
        assert ship.ship_class == ShipClass.CONSTITUTION
        assert ship.hull_pct == 100.0
        assert ship.crew == 430
        assert ship.morale_modifier == 1.10

    def test_create_defiant(self):
        ship = Ship.create("USS Defiant", ShipClass.DEFIANT)
        assert ship.crew == 50
        assert ship.torpedo_modifier == 1.50
        assert ship.shield_modifier == 1.20
        # Siluri moltiplicati: 48 * 1.5 = 72
        assert ship.torpedoes == int(48 * 1.50)

    def test_create_intrepid(self):
        ship = Ship.create("USS Voyager", ShipClass.INTREPID)
        assert ship.sensor_range_modifier == 1.30
        assert ship.computer_bonus == 10
        # Energia: 4500 * 0.80 = 3600
        assert ship.energy_max == 4500 * 0.80

    def test_create_galaxy(self):
        ship = Ship.create("USS Enterprise-D", ShipClass.GALAXY)
        assert ship.low_maneuverability is True
        assert ship.crew == 1014

    def test_create_sovereign(self):
        ship = Ship.create("USS Enterprise-E", ShipClass.SOVEREIGN)
        assert ship.hull_resistance == 0.80

    def test_all_classes_exist(self):
        for sc in ShipClass:
            assert sc in SHIP_CLASS_STATS


class TestShipResources:
    """Test consumo e gestione risorse"""

    def test_consume_energy_success(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        initial = ship.energy
        assert ship.consume_energy(1000) is True
        assert ship.energy == initial - 1000

    def test_consume_energy_insufficient(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.energy = 100
        assert ship.consume_energy(200) is False
        assert ship.energy == 100  # invariato

    def test_consume_dilithium_success(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        initial = ship.dilithium
        assert ship.consume_dilithium(5) is True
        assert ship.dilithium == initial - 5

    def test_consume_dilithium_insufficient(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.dilithium = 0
        assert ship.consume_dilithium(1) is False

    def test_fire_torpedo_success(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        initial = ship.torpedoes
        assert ship.fire_torpedo() is True
        assert ship.torpedoes == initial - 1

    def test_fire_torpedo_empty(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.torpedoes = 0
        assert ship.fire_torpedo() is False


class TestShipDamage:
    """Test sistema danni e distruzione"""

    def test_apply_hull_damage(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        effective = ship.apply_hull_damage(30.0)
        assert effective == 30.0  # hull_resistance = 1.0
        assert ship.hull_pct == 70.0

    def test_apply_hull_damage_with_resistance(self):
        ship = Ship.create("Test", ShipClass.SOVEREIGN)
        # hull_resistance = 0.80
        effective = ship.apply_hull_damage(50.0)
        assert effective == 40.0
        assert ship.hull_pct == 60.0

    def test_hull_clamps_to_zero(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.apply_hull_damage(200.0)
        assert ship.hull_pct == 0.0

    def test_is_destroyed_hull(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        assert ship.is_destroyed() is False
        ship.hull_pct = 0.0
        assert ship.is_destroyed() is True

    def test_is_destroyed_crew(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.crew = 0
        assert ship.is_destroyed() is True


class TestShipCrew:
    """Test equipaggio e morale"""

    def test_lose_crew(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        lost = ship.lose_crew(10)
        assert lost == 10
        assert ship.crew == 420

    def test_lose_crew_capped(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.crew = 5
        lost = ship.lose_crew(10)
        assert lost == 5
        assert ship.crew == 0

    def test_adjust_morale_positive(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.morale_pct = 80.0
        ship.adjust_morale(10.0)
        assert ship.morale_pct == 90.0

    def test_adjust_morale_clamps(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.morale_pct = 95.0
        ship.adjust_morale(10.0)
        assert ship.morale_pct == 100.0
        ship.adjust_morale(-200.0)
        assert ship.morale_pct == 0.0


class TestShipSerialization:
    """Test serializzazione/deserializzazione"""

    def test_roundtrip(self):
        ship = Ship.create("USS Enterprise", ShipClass.CONSTITUTION)
        ship.position = (3, 4, 7, 2)
        ship.hull_pct = 75.0
        d = ship.to_dict()
        ship2 = Ship.from_dict(d)
        assert ship2.name == "USS Enterprise"
        assert ship2.ship_class == ShipClass.CONSTITUTION
        assert ship2.hull_pct == 75.0
        assert ship2.position == (3, 4, 7, 2)
        assert ship2.morale_modifier == ship.morale_modifier
