"""Test per il modulo CommandParser — pattern matching, parametri, menu."""

import pytest

from src.engine.command_parser import (
    parse, CommandAction, ParsedCommand,
    needs_confirmation, get_contextual_menu,
    CONFIRM_REQUIRED,
)


class TestParseBasicCommands:
    """Test parsing comandi di base"""

    def test_empty_input(self):
        result = parse("")
        assert result.action == CommandAction.SHOW_MENU

    def test_unknown_command(self):
        result = parse("abracadabra")
        assert result.action == CommandAction.UNKNOWN
        assert result.confidence == 0.0

    def test_question_mark(self):
        result = parse("?")
        assert result.action == CommandAction.SHOW_MENU


class TestParseCombatCommands:
    """Test comandi combattimento"""

    def test_fire_phaser_italian(self):
        result = parse("spara faser 500")
        assert result.action == CommandAction.FIRE_PHASER
        assert result.params.get("energy") == 500

    def test_fire_phaser_english(self):
        result = parse("fire phaser 300")
        assert result.action == CommandAction.FIRE_PHASER

    def test_fire_torpedo_italian(self):
        result = parse("fuoco siluro")
        assert result.action == CommandAction.FIRE_TORPEDO

    def test_fire_torpedo_english(self):
        result = parse("fire torpedo")
        assert result.action == CommandAction.FIRE_TORPEDO

    def test_shields_max(self):
        result = parse("scudi al massimo")
        assert result.action == CommandAction.SHIELDS_MAX

    def test_shields_set(self):
        result = parse("scudi 75")
        assert result.action == CommandAction.SHIELDS_SET
        assert result.params.get("level") == 75


class TestParseNavigationCommands:
    """Test comandi navigazione"""

    def test_warp(self):
        result = parse("warp 3")
        assert result.action == CommandAction.NAVIGATE_WARP
        assert result.params.get("speed") == 3

    def test_impulse(self):
        result = parse("impulso 5 3")
        assert result.action == CommandAction.NAVIGATE_IMPULSE
        assert result.params.get("s_row") == 5
        assert result.params.get("s_col") == 3

    def test_scan(self):
        result = parse("scansione settore")
        assert result.action == CommandAction.SCAN


class TestParseInfoCommands:
    """Test comandi informazione"""

    def test_map(self):
        result = parse("mappa")
        assert result.action == CommandAction.SHOW_MAP

    def test_status(self):
        result = parse("stato nave")
        assert result.action == CommandAction.SHOW_STATUS

    def test_systems(self):
        result = parse("sistemi")
        assert result.action == CommandAction.SHOW_SYSTEMS

    def test_mission(self):
        result = parse("missione")
        assert result.action == CommandAction.SHOW_MISSION

    def test_captain_log_show(self):
        result = parse("diario")
        assert result.action == CommandAction.SHOW_CAPTAIN_LOG

    def test_captain_log_manual(self):
        result = parse("diario: Nota personale importante")
        assert result.action == CommandAction.CAPTAIN_LOG_MANUAL
        assert result.params.get("text") == "Nota personale importante"


class TestParseOfficerCommands:
    """Test comandi ufficiali"""

    def test_tactical_report(self):
        result = parse("rapporto tattico")
        assert result.action == CommandAction.OFFICER_TACTICAL

    def test_engineer_report(self):
        result = parse("rapporto ingegnere")
        assert result.action == CommandAction.OFFICER_ENGINEER

    def test_science_report(self):
        result = parse("rapporto scientifico")
        assert result.action == CommandAction.OFFICER_SCIENCE

    def test_medical_report(self):
        result = parse("rapporto medico")
        assert result.action == CommandAction.OFFICER_MEDICAL

    def test_crew_meeting(self):
        result = parse("riunione equipaggio")
        assert result.action == CommandAction.CREW_MEETING


class TestParseOtherCommands:
    """Test comandi vari"""

    def test_dock(self):
        result = parse("attracco base stellare")
        assert result.action == CommandAction.DOCK_STARBASE

    def test_repair(self):
        result = parse("ripara sensori")
        assert result.action == CommandAction.REPAIR_SYSTEM
        assert result.params.get("system") == "sensori"

    def test_export_log(self):
        result = parse("export log")
        assert result.action == CommandAction.EXPORT_LOG

    def test_export_log_italian_matches_diario_first(self):
        """Il pattern 'diario' ha priorita su 'esporta diario' nella lista"""
        result = parse("esporta il diario")
        # Il parser matcha 'diario' prima di 'esporta diario' (ordine pattern)
        assert result.action == CommandAction.SHOW_CAPTAIN_LOG

    def test_acknowledge(self):
        result = parse("acknowledge Worf")
        assert result.action == CommandAction.ACKNOWLEDGE_OFFICER


class TestQuitCommands:
    """Test comandi uscita"""

    def test_quit_italian(self):
        result = parse("esci")
        assert result.action == CommandAction.QUIT

    def test_quit_english(self):
        result = parse("quit")
        assert result.action == CommandAction.QUIT

    def test_exit(self):
        result = parse("exit")
        assert result.action == CommandAction.QUIT

    def test_save_and_quit_italian(self):
        result = parse("salva e esci")
        assert result.action == CommandAction.SAVE_AND_QUIT

    def test_save_and_quit_english(self):
        result = parse("save and quit")
        assert result.action == CommandAction.SAVE_AND_QUIT

    def test_save_quit_short(self):
        result = parse("salva ed esci")
        assert result.action == CommandAction.SAVE_AND_QUIT


class TestConfirmation:
    """Test sistema conferma"""

    def test_torpedo_needs_confirm(self):
        assert needs_confirmation(CommandAction.FIRE_TORPEDO) is True

    def test_crew_meeting_needs_confirm(self):
        assert needs_confirmation(CommandAction.CREW_MEETING) is True

    def test_quit_needs_confirm(self):
        assert needs_confirmation(CommandAction.QUIT) is True

    def test_save_and_quit_no_confirm(self):
        assert needs_confirmation(CommandAction.SAVE_AND_QUIT) is False

    def test_phaser_no_confirm(self):
        assert needs_confirmation(CommandAction.FIRE_PHASER) is False


class TestContextualMenu:
    """Test menu contestuali"""

    def test_combat_menu(self):
        menu = get_contextual_menu("COMBAT")
        commands = [cmd for cmd, _ in menu]
        assert any("faser" in cmd for cmd in commands)
        assert any("siluro" in cmd for cmd in commands)

    def test_navigation_menu(self):
        menu = get_contextual_menu("NAVIGATION")
        commands = [cmd for cmd, _ in menu]
        assert any("warp" in cmd for cmd in commands)
        assert any("scan" in cmd for cmd in commands)

    def test_universal_commands_present(self):
        for ctx in ("COMBAT", "NAVIGATION", "DOCKED", "EXPLORATION"):
            menu = get_contextual_menu(ctx)
            commands = [cmd for cmd, _ in menu]
            assert "?" in commands
            assert "esci" in commands
            assert "salva e esci" in commands

    def test_unknown_context_fallback(self):
        menu = get_contextual_menu("UNKNOWN_CONTEXT")
        assert len(menu) > 0  # fallback a NAVIGATION
