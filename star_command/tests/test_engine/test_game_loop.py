"""Test per il modulo GameLoop — stato, contesto, advice, esecuzione comandi."""

import pytest

from src.engine.game_loop import (
    GameState, AdviceRecord,
    get_active_officer, check_advice_followed,
    check_end_conditions, execute_command,
    CONTEXT_OFFICER_MAP,
)
from src.engine.command_parser import CommandAction, ParsedCommand
from src.engine.ship import Ship, ShipClass
from src.engine.galaxy import Galaxy, CellContent
from src.engine.systems import create_default_systems, SystemName, RepairQueue
from src.engine.difficulty import DifficultyConfig, DifficultyPreset
from src.engine.captain_log import CaptainLog
from src.engine.combat import Enemy
from src.engine.campaign import MissionConfig, MissionObjective


@pytest.fixture
def mission():
    return MissionConfig(
        id="M01",
        nome="Test Mission",
        descrizione_narrativa="Test",
        obiettivo_testo="Test obiettivo",
        obiettivi=[MissionObjective(tipo="distruggi_nemici", specie="klingon", quantita=1)],
        deadline_stardate=2350.0,
        nemici=[],
        basi_stellari=0,
        seed_galassia=42,
        consiglieri_speciali=[],
        silenti_eventi=[],
    )


@pytest.fixture
def game_state(mission):
    ship = Ship.create("USS Test", ShipClass.CONSTITUTION)
    ship.position = (1, 1, 4, 4)
    galaxy = Galaxy()
    galaxy.generate(42, {"nemici": [], "basi_stellari": 0})
    return GameState(
        ship=ship,
        galaxy=galaxy,
        systems=create_default_systems(),
        repair_queue=RepairQueue(),
        difficulty=DifficultyConfig.from_preset(DifficultyPreset.NORMAL),
        captain_log=CaptainLog(),
        mission=mission,
        stardate=2347.1,
    )


class FakePresenter:
    """Presenter fittizio per i test"""

    def __init__(self):
        self.messages: list[str] = []
        self.bridge_rendered = False

    def render_bridge(self, game_state):
        self.bridge_rendered = True

    def show_officer_message(self, name, role, msg, trust):
        self.messages.append(f"[{role}] {name}: {msg}")

    def show_narrative_short(self, text, color):
        self.messages.append(text)

    def show_narrative_long(self, text, title):
        self.messages.append(f"{title}: {text}")

    def show_map_overlay(self, galaxy_state, ship_position):
        self.messages.append("MAP")

    def show_systems_overlay(self, systems_state, repair_queue):
        self.messages.append("SYSTEMS")

    def show_captain_log_overlay(self, entries):
        self.messages.append("LOG")

    def show_contextual_menu(self, context):
        self.messages.append(f"MENU:{context}")
        return ""

    def get_captain_input(self):
        return ""

    def show_confirm(self, message):
        return True


class TestGameState:
    """Test stato del gioco"""

    def test_initial_state(self, game_state):
        assert game_state.turn_number == 0
        assert game_state.stardate == 2347.1
        assert not game_state.is_over()

    def test_context_navigation(self, game_state):
        assert game_state.get_context() == "NAVIGATION"

    def test_context_combat(self, game_state):
        game_state.enemies_in_sector.append(
            Enemy(enemy_type=CellContent.KLINGON)
        )
        assert game_state.get_context() == "COMBAT"

    def test_context_docked(self, game_state):
        game_state.docked_at_starbase = True
        assert game_state.get_context() == "DOCKED"

    def test_context_after_loss(self, game_state):
        game_state.crew_casualties_last_turn = 5
        assert game_state.get_context() == "AFTER_LOSS"

    def test_context_exploration(self, game_state):
        game_state.anomaly_detected = True
        assert game_state.get_context() == "EXPLORATION"

    def test_context_diplomacy(self, game_state):
        game_state.diplomatic_contact = True
        assert game_state.get_context() == "DIPLOMACY"

    def test_is_over_ship_destroyed(self, game_state):
        game_state.ship.hull_pct = 0.0
        assert game_state.is_over() is True

    def test_is_over_deadline(self, game_state):
        game_state.stardate = 2351.0  # oltre deadline
        assert game_state.is_over() is True

    def test_is_over_completed(self, game_state):
        game_state.mission_completed = True
        assert game_state.is_over() is True

    def test_to_dict(self, game_state):
        d = game_state.to_dict()
        assert "ship" in d
        assert "systems" in d
        assert "context" in d
        assert d["stardate"] == 2347.1


class TestContextOfficerMap:
    """Test mappatura contesto -> ufficiale"""

    def test_combat_maps_to_tattico(self):
        assert CONTEXT_OFFICER_MAP["COMBAT"] == "tattico"

    def test_navigation_maps_to_scientifico(self):
        assert CONTEXT_OFFICER_MAP["NAVIGATION"] == "scientifico"

    def test_docked_maps_to_ingegnere(self):
        assert CONTEXT_OFFICER_MAP["DOCKED"] == "ingegnere"

    def test_after_loss_maps_to_medico(self):
        assert CONTEXT_OFFICER_MAP["AFTER_LOSS"] == "medico"

    def test_diplomacy_maps_to_speciale(self):
        assert CONTEXT_OFFICER_MAP["DIPLOMACY"] == "speciale"


class TestAdviceFollowed:
    """Test verifica se il consiglio e stato seguito"""

    def test_no_advice(self):
        cmd = ParsedCommand(
            action=CommandAction.FIRE_PHASER,
            params={}, raw_text="spara faser", confidence=1.0,
        )
        assert check_advice_followed(cmd, None) is False

    def test_advice_followed(self):
        advice = AdviceRecord(
            officer_role="tattico",
            advice_text="Consiglio faser",
            action_suggested="FIRE_PHASER",
            turn_number=1,
        )
        cmd = ParsedCommand(
            action=CommandAction.FIRE_PHASER,
            params={}, raw_text="spara faser", confidence=1.0,
        )
        assert check_advice_followed(cmd, advice) is True

    def test_advice_not_followed(self):
        advice = AdviceRecord(
            officer_role="tattico",
            advice_text="Consiglio faser",
            action_suggested="FIRE_PHASER",
            turn_number=1,
        )
        cmd = ParsedCommand(
            action=CommandAction.NAVIGATE_WARP,
            params={}, raw_text="warp 3", confidence=1.0,
        )
        assert check_advice_followed(cmd, advice) is False


class TestEndConditions:
    """Test condizioni fine partita"""

    def test_hull_zero(self, game_state):
        game_state.ship.hull_pct = 0.0
        result = check_end_conditions(game_state)
        assert result is not None
        assert game_state.mission_failed is True

    def test_crew_zero(self, game_state):
        game_state.ship.crew = 0
        result = check_end_conditions(game_state)
        assert result is not None

    def test_deadline_exceeded(self, game_state):
        game_state.stardate = 2360.0
        result = check_end_conditions(game_state)
        assert result is not None
        assert "tempo" in result.lower() or "deadline" in result.lower() or "stardate" in result.lower()

    def test_all_objectives_completed(self, game_state):
        for obj in game_state.mission.obiettivi:
            obj.completed = True
        result = check_end_conditions(game_state)
        assert result is not None
        assert game_state.mission_completed is True

    def test_in_progress(self, game_state):
        result = check_end_conditions(game_state)
        assert result is None


class TestExecuteCommand:
    """Test esecuzione comandi base (non-combattimento)"""

    def test_show_map(self, game_state):
        presenter = FakePresenter()
        cmd = ParsedCommand(
            action=CommandAction.SHOW_MAP,
            params={}, raw_text="mappa", confidence=1.0,
        )
        execute_command(cmd, game_state, {}, presenter, game_state.difficulty)
        assert "MAP" in presenter.messages

    def test_show_status(self, game_state):
        presenter = FakePresenter()
        cmd = ParsedCommand(
            action=CommandAction.SHOW_STATUS,
            params={}, raw_text="stato", confidence=1.0,
        )
        execute_command(cmd, game_state, {}, presenter, game_state.difficulty)
        assert presenter.bridge_rendered

    def test_show_systems(self, game_state):
        presenter = FakePresenter()
        cmd = ParsedCommand(
            action=CommandAction.SHOW_SYSTEMS,
            params={}, raw_text="sistemi", confidence=1.0,
        )
        execute_command(cmd, game_state, {}, presenter, game_state.difficulty)
        assert "SYSTEMS" in presenter.messages

    def test_shields_max(self, game_state):
        presenter = FakePresenter()
        game_state.ship.shields_pct = 50.0
        cmd = ParsedCommand(
            action=CommandAction.SHIELDS_MAX,
            params={}, raw_text="scudi max", confidence=1.0,
        )
        execute_command(cmd, game_state, {}, presenter, game_state.difficulty)
        assert game_state.ship.shields_pct == 100.0

    def test_unknown_shows_menu(self, game_state):
        presenter = FakePresenter()
        cmd = ParsedCommand(
            action=CommandAction.UNKNOWN,
            params={}, raw_text="xyz", confidence=0.0,
        )
        execute_command(cmd, game_state, {}, presenter, game_state.difficulty)
        assert any("MENU" in m for m in presenter.messages)
