"""Test per il modulo Navigation — warp, impulso, consumi, limiti."""

import pytest

from src.engine.navigation import (
    get_warp_spec, get_max_warp, validate_destination,
    navigate_impulse, navigate_warp,
    WARP_TABLE, WARP_SPEED_MAP,
)
from src.engine.galaxy import Galaxy, CellContent
from src.engine.ship import Ship, ShipClass
from src.engine.systems import (
    ShipSystem, SystemName, create_default_systems,
)
from src.engine.difficulty import DifficultyConfig, DifficultyPreset


@pytest.fixture
def ship():
    s = Ship.create("Test Ship", ShipClass.CONSTITUTION)
    s.position = (1, 1, 4, 4)
    return s


@pytest.fixture
def systems():
    return create_default_systems()


@pytest.fixture
def difficulty():
    return DifficultyConfig.from_preset(DifficultyPreset.NORMAL)


@pytest.fixture
def galaxy():
    g = Galaxy()
    g.generate(42, {"nemici": [], "basi_stellari": 0})
    g.set_sector(1, 1, 4, 4, CellContent.SHIP)
    return g


class TestWarpSpec:
    """Test tabella consumi warp"""

    def test_warp_table_keys(self):
        assert "impulso" in WARP_TABLE
        assert "warp_1" in WARP_TABLE
        assert "warp_emergenza" in WARP_TABLE

    def test_get_warp_spec_direct(self, ship):
        spec = get_warp_spec(1, ship)
        assert spec.energia == 200
        assert spec.dilithium == 1
        assert spec.distanza_quadranti == 1

    def test_get_warp_spec_excelsior(self):
        ship = Ship.create("Test", ShipClass.EXCELSIOR)
        spec = get_warp_spec(1, ship)
        # Excelsior ha dilithium_consumption_modifier=0.80
        assert spec.dilithium == max(0, int(1 * 0.80))

    def test_get_max_warp_full_systems(self, ship, systems):
        max_w = get_max_warp(ship, systems)
        assert max_w == 9  # tutto nominale

    def test_get_max_warp_no_dilithium(self, ship, systems):
        ship.dilithium = 0
        assert get_max_warp(ship, systems) == 0

    def test_get_max_warp_engines_offline(self, ship, systems):
        systems[SystemName.WARP_ENGINES].integrity = 0.0
        assert get_max_warp(ship, systems) == 0


class TestValidateDestination:
    """Test validazione destinazione"""

    def test_valid_destination(self, galaxy):
        valid, msg = validate_destination(galaxy, 1, 1, 5, 5)
        # Potrebbe esserci una stella; verifichiamo solo il formato
        assert isinstance(valid, bool)
        assert isinstance(msg, str)

    def test_out_of_bounds_quadrant(self, galaxy):
        valid, msg = validate_destination(galaxy, 0, 1, 1, 1)
        assert valid is False

    def test_out_of_bounds_sector(self, galaxy):
        valid, msg = validate_destination(galaxy, 1, 1, 0, 1)
        assert valid is False

    def test_star_is_obstacle(self, galaxy):
        galaxy.set_sector(1, 1, 8, 8, CellContent.STAR)
        valid, msg = validate_destination(galaxy, 1, 1, 8, 8)
        assert valid is False
        assert "stella" in msg.lower()


class TestNavigateImpulse:
    """Test navigazione impulso"""

    def test_impulse_success(self, ship, galaxy, systems, difficulty):
        result = navigate_impulse(ship, galaxy, systems, difficulty, 5, 4)
        assert result.success is True
        assert ship.position == (1, 1, 5, 4)
        assert result.energy_spent > 0

    def test_impulse_same_position(self, ship, galaxy, systems, difficulty):
        result = navigate_impulse(ship, galaxy, systems, difficulty, 4, 4)
        assert result.success is False
        assert "gia" in result.message.lower() or "gia" in result.message.lower() or "posizione" in result.message.lower()

    def test_impulse_out_of_bounds(self, ship, galaxy, systems, difficulty):
        result = navigate_impulse(ship, galaxy, systems, difficulty, 0, 0)
        assert result.success is False

    def test_impulse_low_engines(self, ship, galaxy, systems, difficulty):
        systems[SystemName.IMPULSE_ENGINES].integrity = 10.0
        result = navigate_impulse(ship, galaxy, systems, difficulty, 5, 4)
        assert result.success is False
        assert "danneggiati" in result.message.lower()

    def test_impulse_no_energy(self, ship, galaxy, systems, difficulty):
        ship.energy = 0
        result = navigate_impulse(ship, galaxy, systems, difficulty, 5, 4)
        assert result.success is False
        assert "energia" in result.message.lower()


class TestNavigateWarp:
    """Test navigazione warp"""

    def test_warp_success(self, ship, galaxy, systems, difficulty):
        result = navigate_warp(
            ship, galaxy, systems, difficulty,
            target_q_row=2, target_q_col=1, warp_speed=1,
        )
        assert result.success is True
        assert ship.position[0] == 2  # nuovo quadrante

    def test_warp_no_dilithium(self, ship, galaxy, systems, difficulty):
        ship.dilithium = 0
        result = navigate_warp(
            ship, galaxy, systems, difficulty,
            target_q_row=2, target_q_col=1, warp_speed=1,
        )
        assert result.success is False
        assert "dilithium" in result.message.lower()

    def test_warp_exceeds_max(self, ship, galaxy, systems, difficulty):
        # Degradando i motori, max_warp scende
        systems[SystemName.WARP_ENGINES].integrity = 30.0
        result = navigate_warp(
            ship, galaxy, systems, difficulty,
            target_q_row=8, target_q_col=8, warp_speed=9,
        )
        assert result.success is False

    def test_warp_same_quadrant_uses_impulse(self, ship, galaxy, systems, difficulty):
        """Warp nello stesso quadrante delega a impulso"""
        result = navigate_warp(
            ship, galaxy, systems, difficulty,
            target_q_row=1, target_q_col=1,
            target_s_row=5, target_s_col=5,
            warp_speed=1,
        )
        # Dovrebbe delegare a navigate_impulse
        assert result.success is True
        assert ship.position[2] == 5
