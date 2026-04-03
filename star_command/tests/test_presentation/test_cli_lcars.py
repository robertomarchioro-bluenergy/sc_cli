"""Test per il CLILcarsPresenter — rendering, output, metodi."""

import pytest
from io import StringIO

from rich.console import Console

from src.presentation.cli_lcars import CLILcarsPresenter, _bar, _context_style


@pytest.fixture
def console():
    """Console che scrive su buffer per catturare l'output"""
    return Console(file=StringIO(), force_terminal=True, width=120)


@pytest.fixture
def presenter(console):
    return CLILcarsPresenter(console)


def get_output(console: Console) -> str:
    """Estrae il testo scritto nel buffer della console"""
    console.file.seek(0)
    return console.file.read()


class TestBarHelper:
    """Test funzione helper _bar"""

    def test_full_bar(self):
        result = _bar(100, 100, "green", "red")
        assert "100%" in result

    def test_empty_bar(self):
        result = _bar(0, 100, "green", "red")
        assert "0%" in result

    def test_half_bar(self):
        result = _bar(50, 100, "green", "red")
        assert "50%" in result

    def test_zero_max(self):
        result = _bar(50, 0, "green", "red")
        assert "N/A" in result

    def test_custom_width(self):
        result = _bar(50, 100, "green", "red", width=10)
        assert "50%" in result


class TestContextStyle:
    """Test stile per contesto"""

    def test_combat_is_red(self):
        assert "red" in _context_style("COMBAT")

    def test_navigation_is_cyan(self):
        assert "cyan" in _context_style("NAVIGATION")

    def test_unknown_fallback(self):
        assert _context_style("UNKNOWN") == "white"


class TestRenderBridge:
    """Test rendering bridge"""

    def test_render_bridge_output(self, presenter, console):
        state = {
            "ship": {
                "name": "USS Enterprise",
                "ship_class": "Constitution",
                "hull_pct": 80.0,
                "shields_pct": 100.0,
                "energy": 4000,
                "energy_max": 5000,
                "torpedoes": 18,
                "torpedoes_max": 20,
                "dilithium": 90,
                "dilithium_max": 100,
                "crew": 420,
                "crew_max": 430,
                "morale_pct": 85.0,
                "position": [1, 1, 4, 4],
            },
            "stardate": 2347.15,
            "turn_number": 3,
            "context": "NAVIGATION",
            "mission_nome": "Pattuglia di Frontiera",
            "mission_obiettivo": "Elimina 3 Klingon",
            "deadline_stardate": 2347.8,
            "enemies": [],
        }
        presenter.render_bridge(state)
        output = get_output(console)
        assert "Enterprise" in output
        assert "LCARS" in output
        assert "2347.15" in output

    def test_render_bridge_with_enemies(self, presenter, console):
        state = {
            "ship": {
                "name": "USS Test",
                "ship_class": "Constitution",
                "hull_pct": 50.0,
                "shields_pct": 60.0,
                "energy": 2000,
                "energy_max": 5000,
                "torpedoes": 10,
                "torpedoes_max": 20,
                "dilithium": 50,
                "dilithium_max": 100,
                "crew": 400,
                "crew_max": 430,
                "morale_pct": 70.0,
                "position": [3, 4, 7, 2],
            },
            "stardate": 2347.5,
            "turn_number": 10,
            "context": "COMBAT",
            "mission_nome": "Test",
            "mission_obiettivo": "Test",
            "deadline_stardate": 2350.0,
            "enemies": [{"enemy_type": "K"}],
        }
        presenter.render_bridge(state)
        output = get_output(console)
        assert "NEMICI" in output


class TestShowOfficerMessage:
    """Test messaggi ufficiali"""

    def test_officer_message(self, presenter, console):
        presenter.show_officer_message("Worf", "tattico", "Consiglio attaccare!", 80.0)
        output = get_output(console)
        assert "Worf" in output
        assert "Consiglio attaccare!" in output


class TestShowNarrative:
    """Test messaggi narrativi"""

    def test_narrative_short(self, presenter, console):
        presenter.show_narrative_short("Scudi al massimo!", "cyan")
        output = get_output(console)
        assert "Scudi al massimo!" in output

    def test_narrative_long(self, presenter, console):
        presenter.show_narrative_long("Testo lungo del briefing", "BRIEFING")
        output = get_output(console)
        assert "BRIEFING" in output
        assert "Testo lungo" in output


class TestShowOverlays:
    """Test overlay (mappa, sistemi, diario)"""

    def test_systems_overlay(self, presenter, console):
        systems = {
            "sensori": {"name": "sensori", "integrity": 80.0},
            "motori_warp": {"name": "motori_warp", "integrity": 30.0},
        }
        presenter.show_systems_overlay(systems, [])
        output = get_output(console)
        assert "SISTEMI" in output
        assert "sensori" in output

    def test_captain_log_empty(self, presenter, console):
        presenter.show_captain_log_overlay([])
        output = get_output(console)
        assert "Nessuna" in output

    def test_captain_log_with_entries(self, presenter, console):
        entries = [
            {"stardate": 2347.1, "tipo": "NOTA", "testo": "Prima nota"},
            {"stardate": 2347.5, "tipo": "AUTO", "testo": "Entry automatica"},
        ]
        presenter.show_captain_log_overlay(entries)
        output = get_output(console)
        assert "DIARIO" in output
        assert "Prima nota" in output

    def test_map_overlay(self, presenter, console, monkeypatch):
        # Crea una galaxy minima per il test
        from src.engine.galaxy import Galaxy
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **kw: "")
        g = Galaxy()
        g.generate(42, {"nemici": [], "basi_stellari": 0})
        presenter.show_map_overlay(g.to_dict(), (1, 1, 4, 4))
        output = get_output(console)
        assert "MAPPA" in output
        assert "SETTORI" in output


class TestContextualMenu:
    """Test menu contestuale"""

    def test_shows_menu(self, presenter, console):
        presenter.show_contextual_menu("COMBAT")
        output = get_output(console)
        assert "COMANDI" in output
        assert "COMBAT" in output


class TestSpecialScreens:
    """Test schermate speciali"""

    def test_title_screen(self, presenter, console):
        presenter.show_title_screen()
        output = get_output(console)
        # L'ASCII art contiene i caratteri ma con escape ANSI in mezzo
        assert "strategia spaziale" in output or "Star Trek" in output

    def test_mission_briefing(self, presenter, console):
        mission = {
            "id": "M01",
            "nome": "Pattuglia di Frontiera",
            "descrizione_narrativa": "Ordini da Comando Flotta",
            "obiettivo_testo": "Elimina 3 Klingon",
            "deadline_stardate": 2347.8,
        }
        presenter.show_mission_briefing(mission)
        output = get_output(console)
        assert "BRIEFING" in output
        assert "Pattuglia" in output

    def test_game_over_victory(self, presenter, console):
        presenter.show_game_over("Missione completata!", victory=True)
        output = get_output(console)
        assert "COMPLETATA" in output

    def test_game_over_defeat(self, presenter, console):
        presenter.show_game_over("Nave distrutta", victory=False)
        output = get_output(console)
        assert "FALLITA" in output

    def test_resupply(self, presenter, console):
        msgs = ["Energia rifornita: 1000 -> 4000", "Siluri: nessun rifornimento"]
        presenter.show_resupply(msgs)
        output = get_output(console)
        assert "RIFORNIMENTO" in output


class TestConfirm:
    """Test conferma (non interattivo - testa solo che il metodo esista)"""

    def test_confirm_eof_returns_false(self, presenter, monkeypatch):
        """EOFError su input restituisce False"""
        monkeypatch.setattr("rich.prompt.Prompt.ask", lambda *a, **kw: (_ for _ in ()).throw(EOFError))
        assert presenter.show_confirm("Conferma?") is False
