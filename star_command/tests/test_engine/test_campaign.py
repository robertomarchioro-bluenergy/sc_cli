"""Test per il modulo Campaign — caricamento YAML, stato, rifornimento."""

import json
import pytest
from pathlib import Path

from src.engine.campaign import (
    Campaign, CampaignState, MissionConfig, MissionObjective,
    AlternativeVictory, CampaignLoadError,
    save_campaign_state, load_campaign_state,
)
from src.engine.ship import Ship, ShipClass
from src.engine.systems import create_default_systems, RepairQueue
from src.engine.difficulty import DifficultyConfig, DifficultyPreset
from src.engine.captain_log import CaptainLog


CAMPAIGN_YAML = Path(__file__).parent.parent.parent / "src" / "config" / "campaigns" / "crisis_of_korvath.yaml"


class TestCampaignLoadYAML:
    """Test caricamento campagna da YAML"""

    @pytest.fixture
    def campaign(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        return c

    def test_load_nome(self, campaign):
        assert campaign.nome == "La Crisi di Korvath"

    def test_load_missions_count(self, campaign):
        assert len(campaign.missions) == 4

    def test_mission_m01(self, campaign):
        m = campaign.missions[0]
        assert m.id == "M01"
        assert m.nome == "Pattuglia di Frontiera"
        assert m.deadline_stardate == 2347.8
        assert len(m.obiettivi) == 1
        assert m.obiettivi[0].tipo == "distruggi_nemici"
        assert m.obiettivi[0].quantita == 3

    def test_mission_m04_special_officers(self, campaign):
        m = campaign.missions[3]
        assert m.id == "M04"
        assert "ambasciatore_vulcaniano" in m.consiglieri_speciali

    def test_mission_m04_alt_victory(self, campaign):
        m = campaign.missions[3]
        assert m.vittoria_alternativa is not None
        assert m.vittoria_alternativa.tipo == "diplomatica"

    def test_load_nonexistent_file(self):
        c = Campaign()
        with pytest.raises(CampaignLoadError):
            c.load_from_yaml("nonexistent.yaml")

    def test_prerequisites(self, campaign):
        assert campaign.missions[0].prerequisito is None
        assert campaign.missions[1].prerequisito == "M01_completata"


class TestCampaignFlow:
    """Test flusso missioni"""

    def test_get_mission_by_index(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        m = c.get_mission(0)
        assert m is not None
        assert m.id == "M01"

    def test_get_mission_out_of_range(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        assert c.get_mission(99) is None

    def test_get_next_mission_start(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        m = c.get_next_mission([])
        assert m.id == "M01"

    def test_get_next_mission_after_m01(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        m = c.get_next_mission(["M01"])
        assert m.id == "M02"

    def test_get_next_mission_skips_unmet_prereq(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        # Senza aver completato M01, M02 non e disponibile
        m = c.get_next_mission(["M02"])  # M02 completata ma non M01
        assert m.id == "M01"  # M01 non ha prereq

    def test_get_next_mission_all_done(self):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        m = c.get_next_mission(["M01", "M02", "M03", "M04"])
        assert m is None


class TestResupply:
    """Test rifornimento tra missioni"""

    @pytest.fixture
    def campaign_state(self):
        ship = Ship.create("Test", ShipClass.CONSTITUTION)
        ship.energy = 1000.0  # bassa
        ship.dilithium = 20   # basso
        ship.morale_pct = 60.0
        systems = create_default_systems()
        systems_list = list(systems.values())
        systems_list[0].integrity = 40.0  # un sistema degradato
        return CampaignState(
            nome_campagna="Test",
            captain_name="Kirk",
            ship=ship,
            systems=systems,
            repair_queue=RepairQueue(),
            difficulty=DifficultyConfig.from_preset(DifficultyPreset.NORMAL),
            captain_log=CaptainLog(),
        )

    def test_resupply_energy(self, campaign_state):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        old_energy = campaign_state.ship.energy
        msgs = c.apply_between_mission_resupply(campaign_state)
        assert campaign_state.ship.energy > old_energy

    def test_resupply_morale(self, campaign_state):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        old_morale = campaign_state.ship.morale_pct
        c.apply_between_mission_resupply(campaign_state)
        assert campaign_state.ship.morale_pct >= old_morale + 10.0

    def test_resupply_messages(self, campaign_state):
        c = Campaign()
        c.load_from_yaml(str(CAMPAIGN_YAML))
        msgs = c.apply_between_mission_resupply(campaign_state)
        assert len(msgs) > 0
        assert any("siluri" in m.lower() for m in msgs)


class TestCampaignStateSerialization:
    """Test salvataggio/caricamento stato"""

    def test_roundtrip(self, tmp_path, monkeypatch):
        import src.engine.campaign as camp_module
        monkeypatch.setattr(camp_module, "SAVE_DIR", tmp_path)

        ship = Ship.create("USS Test", ShipClass.CONSTITUTION)
        state = CampaignState(
            nome_campagna="Test Campaign",
            captain_name="Kirk",
            ship=ship,
            systems=create_default_systems(),
            repair_queue=RepairQueue(),
            difficulty=DifficultyConfig.from_preset(DifficultyPreset.NORMAL),
            captain_log=CaptainLog(),
            stardate=2348.0,
            missions_completed=["M01"],
        )

        save_campaign_state(state, slot="test_save")
        loaded = load_campaign_state(slot="test_save")

        assert loaded is not None
        assert loaded.nome_campagna == "Test Campaign"
        assert loaded.stardate == 2348.0
        assert loaded.missions_completed == ["M01"]
        assert loaded.ship.name == "USS Test"

    def test_load_nonexistent(self, tmp_path, monkeypatch):
        import src.engine.campaign as camp_module
        monkeypatch.setattr(camp_module, "SAVE_DIR", tmp_path)
        assert load_campaign_state(slot="nonexistent") is None


class TestMissionObjective:
    """Test obiettivi missione"""

    def test_serialization(self):
        obj = MissionObjective(
            tipo="distruggi_nemici",
            specie="klingon",
            quantita=3,
        )
        d = obj.to_dict()
        restored = MissionObjective.from_dict(d)
        assert restored.tipo == "distruggi_nemici"
        assert restored.quantita == 3
        assert restored.completed is False
